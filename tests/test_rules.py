import datetime as dt
import unittest

from app.db import Base, SessionLocal, engine
from app.models import InstitutionalDaily
from app.rules.engine import format_digest, scan_trust_rules
from app.config import Settings


class RuleEngineTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        day = dt.date(2026, 9, 11)
        self.day = day
        # three days of trust buys for 2330
        for offset, net in [(2, 500000), (1, 400000), (0, 300000)]:
            self.db.add(
                InstitutionalDaily(
                    trade_date=day - dt.timedelta(days=offset),
                    market="twse",
                    code="2330",
                    name="台積電",
                    trust_net=net,
                    foreign_net=100000,
                    total_net=net + 100000,
                )
            )
        # one-day top buy only
        self.db.add(
            InstitutionalDaily(
                trade_date=day,
                market="tpex",
                code="6223",
                name="旺矽",
                trust_net=900000,
                foreign_net=-1000,
                total_net=899000,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_scan_rules(self):
        settings = Settings(
            trust_top_k=5,
            trust_streak_days=3,
            trust_min_net_lots=200,
        )
        hits = scan_trust_rules(self.db, self.day, settings=settings)
        rule_ids = {h.rule_id for h in hits}
        self.assertIn("trust_top_buy", rule_ids)
        self.assertIn("trust_streak", rule_ids)
        subject, body = format_digest(hits, self.day)
        self.assertIn("法人掃市", subject)
        self.assertIn("免責", body)


if __name__ == "__main__":
    unittest.main()
