from __future__ import annotations

import argparse
import json

from app.db import SessionLocal, init_db
from app.services.backfill import backfill_range
from app.services.pipeline import run_daily_pipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="twstock-radar")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Ingest + scan + notify for a trade date")
    run_parser.add_argument("--date", help="YYYY-MM-DD or YYYYMMDD (default: today)")
    run_parser.add_argument(
        "--no-notify", action="store_true", help="Skip notification channels"
    )

    backfill_parser = sub.add_parser(
        "backfill", help="Ingest a date range (optional rules; notify off by default)"
    )
    backfill_parser.add_argument(
        "--from", dest="date_from", required=True, help="Start date YYYY-MM-DD"
    )
    backfill_parser.add_argument(
        "--to", dest="date_to", help="End date YYYY-MM-DD (default: today)"
    )
    backfill_parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Only ingest, skip rule scan",
    )
    backfill_parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notifications for each day (default: off)",
    )
    backfill_parser.add_argument(
        "--sleep",
        type=float,
        default=None,
        help="Seconds between days (default: BACKFILL_SLEEP_SECONDS)",
    )

    sub.add_parser("init-db", help="Create database tables")

    args = parser.parse_args(argv)
    if args.command == "init-db":
        init_db()
        print("database initialized")
        return

    if args.command == "run":
        init_db()
        db = SessionLocal()
        try:
            result = run_daily_pipeline(
                db, trade_date=args.date, notify=not args.no_notify
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            db.close()
        return

    if args.command == "backfill":
        init_db()
        db = SessionLocal()
        try:
            result = backfill_range(
                db,
                start=args.date_from,
                end=args.date_to,
                notify=args.notify,
                run_rules=not args.ingest_only,
                sleep_seconds=args.sleep,
            )
            # Keep CLI output readable for long ranges.
            summary = {k: v for k, v in result.items() if k != "results"}
            summary["sample"] = result["results"][:3]
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        finally:
            db.close()


if __name__ == "__main__":
    main()
