"""Maintenance CLI command handlers."""

from __future__ import annotations

from ._scanner_bindings import bind_scanner_globals

MAINTENANCE_COMMAND_GROUP = "maintenance"


def handle(args) -> bool:
    bind_scanner_globals(globals())
    if args.status:
        status()
        return True
    if args.backup_db:
        backup_db()
        return True
    if args.verify_restore is not None:
        verify_restore(args.verify_restore or None)
        return True
    if args.maintenance:
        maintenance()
        return True
    if args.rotate_logs:
        rotate_logs()
        return True
    if args.launchd_status:
        launchd_status()
        return True
    if args.install_maintenance_agent:
        install_maintenance_agent()
        return True
    if args.restart_listener:
        restart_listener()
        return True
    if args.universe_audit:
        universe_audit()
        return True
    if args.refresh_universe_audit:
        refresh_universe_audit(top_n=args.top_n, verbose=args.verbose)
        return True
    if args.listen:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        config.validate()
        telegram.listen()
        return True
    return False
