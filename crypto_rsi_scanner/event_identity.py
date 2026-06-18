"""Shared asset-identity matching for Event Alpha research paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


COMMON_WORD_SYMBOLS = {
    "AI",
    "ALT",
    "API",
    "ARK",
    "ATOM",
    "BAN",
    "BAND",
    "BAT",
    "BIT",
    "BLUR",
    "BOND",
    "CASH",
    "CITY",
    "COW",
    "CREAM",
    "CROWN",
    "DASH",
    "DENT",
    "DODO",
    "DUSK",
    "FARM",
    "FEAR",
    "FIL",
    "FLUX",
    "FORTH",
    "GAS",
    "GODS",
    "HIGH",
    "HIVE",
    "HOOK",
    "HYPE",
    "ICE",
    "JASMY",
    "JOE",
    "JUST",
    "KEY",
    "LAYER",
    "MAGIC",
    "MASK",
    "MOBILE",
    "MOVE",
    "NEAR",
    "NMR",
    "OM",
    "ONE",
    "PEOPLE",
    "PRIME",
    "PROM",
    "PUMP",
    "RARE",
    "REAL",
    "ROSE",
    "SAFE",
    "SAND",
    "SPELL",
    "SUPER",
    "SUSHI",
    "TRUMP",
    "UMA",
    "USUAL",
    "WING",
}

STRENGTH_STRONG = "strong"
STRENGTH_WEAK = "weak"
STRENGTH_REJECTED = "rejected"
STRENGTH_NONE = "none"


@dataclass(frozen=True)
class AssetIdentity:
    symbol: str = ""
    coin_id: str | None = None
    project_name: str | None = None
    aliases: tuple[str, ...] = ()
    contract_addresses: tuple[str, ...] = ()
    is_common_word_symbol: bool = False
    identity_terms: tuple[str, ...] = ()

    @property
    def normalized_symbol(self) -> str:
        return str(self.symbol or "").strip().upper()

    @property
    def terms(self) -> tuple[str, ...]:
        values: list[str] = []
        for value in (
            self.coin_id,
            self.project_name,
            *(self.aliases or ()),
            *(self.identity_terms or ()),
        ):
            text = str(value or "").strip()
            if text:
                values.append(text)
        coin_id = str(self.coin_id or "").strip()
        if coin_id and "-" in coin_id:
            values.append(coin_id.replace("-", " "))
        return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class IdentityEvidence:
    strong_content: tuple[str, ...] = ()
    llm_quotes: tuple[str, ...] = ()
    url: str | None = None
    metadata: tuple[str, ...] = ()
    source_origin: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityMatchResult:
    matched: bool
    strength: str
    reason: str | None
    evidence_field: str | None = None
    evidence_text: str | None = None


def match_asset_identity(identity: AssetIdentity, evidence: IdentityEvidence) -> IdentityMatchResult:
    """Match an asset identity against field-strength-aware evidence.

    Strong content and quote evidence can prove identity. Source-origin and
    URL-query-only matches are explicitly rejected so publisher names and search
    URLs cannot satisfy symbol identity.
    """
    symbol = identity.normalized_symbol
    if not symbol and not identity.terms and not identity.contract_addresses:
        return _none()
    is_common = identity.is_common_word_symbol or symbol in COMMON_WORD_SYMBOLS
    strong_texts = _texts(evidence.strong_content)
    strong_blob = " ".join(strong_texts)
    strong_lower = strong_blob.casefold()
    url = str(evidence.url or "")

    for address in identity.contract_addresses:
        clean = str(address or "").strip()
        if not clean:
            continue
        if clean.casefold() in strong_lower:
            return _strong("identity_match_contract", "strong_content", _snippet_for(clean, strong_texts))
        if contract_in_url_path(url, clean):
            return _strong("identity_match_contract", "url_path_contract", clean)

    if symbol:
        if pair_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_pair", "strong_content", _snippet_for(symbol, strong_texts))
        if dollar_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_strong", "strong_content", _snippet_for(symbol, strong_texts))
        if case_sensitive_symbol_in_text(strong_blob, symbol):
            return _strong("identity_match_strong", "strong_content", _snippet_for(symbol, strong_texts))
        if token_context_in_text(_clean_text(strong_blob), symbol):
            return _strong("identity_match_token_context", "strong_content", _snippet_for(symbol, strong_texts))

    for term in identity.terms:
        normalized = _clean_text(term)
        if not normalized or len(normalized) < 3:
            continue
        if _term_in_clean_text(normalized, _clean_text(strong_blob)):
            reason = "identity_match_project" if identity.project_name and normalized == _clean_text(identity.project_name) else "identity_match_alias"
            return _strong(reason, "strong_content", _snippet_for(term, strong_texts))

    for quote in _texts(evidence.llm_quotes):
        quote_result = _quote_mentions_identity(identity, quote, is_common=is_common)
        if quote_result:
            return _strong("identity_quote_validated", "llm_quote", quote)

    if is_common and symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])", _clean_text(strong_blob)):
        return IdentityMatchResult(
            matched=False,
            strength=STRENGTH_REJECTED,
            reason="common_word_identity_rejected",
            evidence_field="strong_content",
            evidence_text=_snippet_for(symbol, strong_texts),
        )

    origin_text = _clean_text(" ".join(_texts(evidence.source_origin)))
    if _identity_in_clean_text(identity, origin_text, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_source_origin_rejected", "source_origin")

    metadata_text = _clean_text(" ".join(_texts(evidence.metadata)))
    if _identity_in_clean_text(identity, metadata_text, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_source_origin_rejected", "metadata")

    if _identity_in_url_only(identity, url, symbol=symbol):
        return IdentityMatchResult(False, STRENGTH_REJECTED, "identity_url_only_rejected", "weak_url")

    return _none()


def validated_llm_identity_quotes(payload: object, source_texts: Iterable[object]) -> tuple[str, ...]:
    """Return extraction quotes that appear verbatim in source text."""
    if not isinstance(payload, dict):
        return ()
    extraction = payload.get("llm_extraction")
    if not isinstance(extraction, dict):
        return ()
    source_text = " ".join(str(item or "") for item in source_texts)
    out: list[str] = []
    for key in ("crypto_asset_mentions", "external_catalysts", "false_positive_terms"):
        rows = extraction.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            for quote in row.get("evidence_quotes") or ():
                text = str(quote.get("text") if isinstance(quote, dict) else quote or "").strip()
                if text and text in source_text:
                    out.append(text)
    return tuple(dict.fromkeys(out))


def contract_in_url_path(source_url: str, address: str) -> bool:
    if not source_url or not address or not looks_contract_address(address):
        return False
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return False
    address_l = address.casefold()
    if address_l in (parsed.query or "").casefold():
        return False
    return address_l in (parsed.path or "").casefold()


def looks_contract_address(address: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", str(address or "").strip()))


def pair_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?:[-_/]?)USDT(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None


def dollar_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9])\${re.escape(symbol)}(?![A-Za-z0-9])", text, flags=re.IGNORECASE) is not None


def case_sensitive_symbol_in_text(text: str, symbol: str) -> bool:
    if not symbol:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(symbol)}(?![A-Za-z0-9])", text) is not None


def token_context_in_text(clean_text: str, symbol: str) -> bool:
    if not symbol:
        return False
    lower = symbol.casefold()
    return any(
        phrase in clean_text
        for phrase in (
            f"{lower} token",
            f"{lower} coin",
            f"{lower} crypto",
            f"token {lower}",
            f"coin {lower}",
        )
    )


def _quote_mentions_identity(identity: AssetIdentity, quote: str, *, is_common: bool) -> bool:
    if not quote:
        return False
    symbol = identity.normalized_symbol
    if symbol and (
        pair_symbol_in_text(quote, symbol)
        or dollar_symbol_in_text(quote, symbol)
        or case_sensitive_symbol_in_text(quote, symbol)
        or token_context_in_text(_clean_text(quote), symbol)
    ):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and len(normalized) >= 3 and _term_in_clean_text(normalized, _clean_text(quote)):
            return True
    if is_common:
        return False
    return bool(symbol and symbol.casefold() in quote.casefold())


def _identity_in_url_only(identity: AssetIdentity, source_url: str, *, symbol: str) -> bool:
    if not source_url:
        return False
    text = _clean_text(source_url)
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?:usdt)?(?![a-z0-9])", text):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and _term_in_clean_text(normalized, text):
            return True
    for address in identity.contract_addresses:
        if str(address or "").casefold() in source_url.casefold() and not contract_in_url_path(source_url, str(address)):
            return True
    return False


def _identity_in_clean_text(identity: AssetIdentity, text: str, *, symbol: str) -> bool:
    if not text:
        return False
    if symbol and re.search(rf"(?<![a-z0-9]){re.escape(symbol.casefold())}(?![a-z0-9])", text):
        return True
    for term in identity.terms:
        normalized = _clean_text(term)
        if normalized and _term_in_clean_text(normalized, text):
            return True
    return False


def _term_in_clean_text(term: str, clean_text: str) -> bool:
    if not term or not clean_text:
        return False
    if " " in term:
        return term in clean_text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", clean_text) is not None


def _clean_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _texts(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(str(value or "").strip() for value in values if str(value or "").strip())


def _snippet_for(term: object, texts: Iterable[str]) -> str | None:
    needle = str(term or "").strip()
    if not needle:
        return None
    for text in texts:
        idx = text.casefold().find(needle.casefold())
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(text), idx + len(needle) + 40)
            return text[start:end].strip()
    for text in texts:
        if text:
            return text[:120].strip()
    return None


def _strong(reason: str, field: str, text: str | None) -> IdentityMatchResult:
    return IdentityMatchResult(True, STRENGTH_STRONG, reason, field, text)


def _none() -> IdentityMatchResult:
    return IdentityMatchResult(False, STRENGTH_NONE, None, None, None)
