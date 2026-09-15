from __future__ import annotations

import argparse
import json

import datetime as dt

from app.db import SessionLocal, init_db
from app.services.ai_analysis import analyze_trade_date, insights_as_dict
from app.services.backfill import backfill_range
from app.services.pipeline import run_daily_pipeline
from app.services.rule_ideas import generate_rule_ideas, ideas_as_dict


def _parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    text = value.strip()
    if "-" in text:
        return dt.datetime.strptime(text[:10], "%Y-%m-%d").date()
    return dt.datetime.strptime(text, "%Y%m%d").date()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="twstock-radar")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Ingest + scan + notify for a trade date")
    run_parser.add_argument("--date", help="YYYY-MM-DD or YYYYMMDD (default: today)")
    run_parser.add_argument(
        "--no-notify", action="store_true", help="Skip notification channels"
    )

    analyze_parser = sub.add_parser(
        "analyze", help="Run AI analysis on existing rule hits for a trade date"
    )
    analyze_parser.add_argument(
        "--date",
        required=True,
        help="YYYY-MM-DD or YYYYMMDD",
    )

    ideas_parser = sub.add_parser(
        "rule-ideas",
        help="Generate AI rule ideas for reference (does not enable them)",
    )
    ideas_parser.add_argument("--date", required=True, help="YYYY-MM-DD or YYYYMMDD")
    ideas_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Use built-in fallback ideas only",
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

    if args.command == "analyze":
        init_db()
        day = _parse_date(args.date)
        assert day is not None
        db = SessionLocal()
        try:
            insights = analyze_trade_date(db, day)
            print(
                json.dumps(
                    {
                        "trade_date": day.isoformat(),
                        "count": len(insights),
                        "insights": insights_as_dict(insights),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            db.close()
        return

    if args.command == "rule-ideas":
        init_db()
        day = _parse_date(args.date)
        assert day is not None
        db = SessionLocal()
        try:
            ideas = generate_rule_ideas(db, day, use_ai=not args.no_ai)
            print(
                json.dumps(
                    {
                        "trade_date": day.isoformat(),
                        "count": len(ideas),
                        "ideas": ideas_as_dict(ideas),
                        "note": "reference only; not auto-enabled",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
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
