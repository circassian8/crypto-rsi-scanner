"""Provider-readiness status metadata must remain inside the secret boundary."""

from crypto_rsi_scanner.event_alpha.artifacts import schema_v1


def test_live_authorization_status_is_closed_safe_metadata() -> None:
    schema = schema_v1.get_schema("provider_readiness_v1")
    provider = {
        "provider": "provider-a",
        "configured": False,
        "live_call_allowed": False,
    }

    for status in (
        "absent",
        "missing_configuration",
        "not_defined",
        "not_required",
        "present",
    ):
        status_row = dict(provider, live_authorization_status=status)
        assert schema_v1.validate_row_against_schema(status_row, schema) == []


def test_live_authorization_status_still_rejects_a_secret_value() -> None:
    schema = schema_v1.get_schema("provider_readiness_v1")
    leaked = {
        "provider": "provider-a",
        "configured": False,
        "live_call_allowed": False,
        "live_authorization_status": "plain-text-provider-authorization-token",
    }

    errors = schema_v1.validate_row_against_schema(leaked, schema)
    assert "secret_field_unredacted:live_authorization_status" in errors
    assert any(
        error.startswith("invalid_enum:live_authorization_status")
        for error in errors
    )


def test_live_authorization_status_requires_exact_canonical_spelling() -> None:
    schema = schema_v1.get_schema("provider_readiness_v1")

    for status in (" present", "present ", "PRESENT"):
        errors = schema_v1.validate_row_against_schema(
            {
                "provider": "provider-a",
                "configured": False,
                "live_call_allowed": False,
                "live_authorization_status": status,
            },
            schema,
        )
        assert "secret_field_unredacted:live_authorization_status" in errors
        assert any(
            error.startswith("invalid_enum:live_authorization_status")
            for error in errors
        )
