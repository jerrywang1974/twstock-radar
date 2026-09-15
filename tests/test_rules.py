import datetime as dt
import unittest

from app.config import Settings
from app.models import InstitutionalDaily
from app.rules.engine import format_digest, scan_trust_rules
from tests.db_utils import make_test_session


class RuleEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.db = make_test_session()
        day = dt.date(2026, 9, 11)
        self.day = day
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
        self.engine.dispose()

    def test_scan_rules(self):
        settings = Settings(
            trust_top_k=5,
            trust_streak_days=3,
            trust_min_net_lots=200,
            alert_cooldown_days=0,
            exclude_non_equity=False,
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
