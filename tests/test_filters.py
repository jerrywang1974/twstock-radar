import datetime as dt
import unittest

from app.config import Settings
from app.db import Base, SessionLocal, engine
from app.models import InstitutionalDaily, RuleHit
from app.rules.engine import scan_trust_rules
from app.services.filters import is_tradable_equity


class FilterTest(unittest.TestCase):
    def test_equity_codes(self):
        settings = Settings(exclude_non_equity=True)
        self.assertTrue(is_tradable_equity("2330", settings))
        self.assertFalse(is_tradable_equity("0050", settings))
        self.assertFalse(is_tradable_equity("700001", settings))

    def test_disable_filter(self):
        settings = Settings(exclude_non_equity=False)
        self.assertTrue(is_tradable_equity("0050", settings))


class CooldownTest(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.day = dt.date(2026, 9, 11)
        for offset, net in [(2, 500000), (1, 400000), (0, 300000)]:
            self.db.add(
                InstitutionalDaily(
                    trade_date=self.day - dt.timedelta(days=offset),
                    market="twse",
                    code="2330",
                    name="台積電",
                    trust_net=net,
                    foreign_net=100000,
                    total_net=net + 100000,
                )
            )
        # ETF should be filtered out of scan
        self.db.add(
            InstitutionalDaily(
                trade_date=self.day,
                market="twse",
                code="0050",
                name="元大台灣50",
                trust_net=9_000_000,
                foreign_net=1_000_000,
                total_net=10_000_000,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_scan_excludes_etf(self):
        settings = Settings(
            trust_top_k=10,
            trust_streak_days=3,
            trust_min_net_lots=200,
            alert_cooldown_days=0,
            exclude_non_equity=True,
        )
        hits = scan_trust_rules(self.db, self.day, settings=settings)
        codes = {h.code for h in hits}
        self.assertIn("2330", codes)
        self.assertNotIn("0050", codes)

    def test_cooldown_suppresses_repeat(self):
        self.db.add(
            RuleHit(
                trade_date=self.day - dt.timedelta(days=1),
                code="2330",
                name="台積電",
                rule_id="trust_streak",
                reason="prior",
                suggested_action="buy_bias",
                metrics_json="{}",
            )
        )
        self.db.commit()
        settings = Settings(
            trust_top_k=10,
            trust_streak_days=3,
            trust_min_net_lots=200,
            alert_cooldown_days=3,
            exclude_non_equity=True,
        )
        hits = scan_trust_rules(self.db, self.day, settings=settings)
        streak_hits = [h for h in hits if h.rule_id == "trust_streak" and h.code == "2330"]
        self.assertEqual(streak_hits, [])


if __name__ == "__main__":
    unittest.main()
