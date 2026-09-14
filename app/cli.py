from __future__ import annotations

import argparse
import json

from app.db import SessionLocal, init_db
from app.services.pipeline import run_daily_pipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="twstock-radar")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Ingest + scan + notify for a trade date")
    run_parser.add_argument("--date", help="YYYY-MM-DD or YYYYMMDD (default: today)")
    run_parser.add_argument(
        "--no-notify", action="store_true", help="Skip notification channels"
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


if __name__ == "__main__":
    main()
