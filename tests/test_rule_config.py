import datetime as dt
import unittest

from app.models import InstitutionalDaily
from app.rules.engine import scan_trust_rules
from app.rules.templates import RULE_TEMPLATES
from app.services.rule_config import list_rule_settings, update_rule_settings
from app.config import Settings
from tests.db_utils import make_test_session


class RuleConfigTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.db = make_test_session()
        self.day = dt.date(2026, 9, 11)
        for offset, trust, foreign in [
            (2, 100000, 50000),
            (1, 120000, 60000),
            (0, 150000, 70000),
        ]:
            self.db.add(
                InstitutionalDaily(
                    trade_date=self.day - dt.timedelta(days=offset),
                    market="twse",
                    code="2330",
                    name="台積電",
                    trust_net=trust,
                    foreign_net=foreign,
                    total_net=trust + foreign,
                )
            )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_templates_seeded(self):
        rows = list_rule_settings(self.db)
        self.assertEqual(len(rows), len(RULE_TEMPLATES))
        by_id = {r["id"]: r for r in rows}
        self.assertTrue(by_id["trust_top_buy"]["enabled"])
        self.assertFalse(by_id["trust_cum_buy"]["enabled"])
        self.assertEqual(by_id["trust_streak"]["lookback_days"], 3)

    def test_disable_rule(self):
        update_rule_settings(
            self.db,
            [
                {"rule_id": "trust_streak", "enabled": False, "lookback_days": 3},
                {"rule_id": "foreign_streak", "enabled": False, "lookback_days": 3},
                {"rule_id": "total_streak", "enabled": False, "lookback_days": 3},
                {"rule_id": "institutional_turn", "enabled": False, "lookback_days": 5},
                {"rule_id": "foreign_top_buy", "enabled": False, "lookback_days": 1},
                {"rule_id": "foreign_trust_align", "enabled": False, "lookback_days": 1},
                {"rule_id": "trust_foreign_diverge", "enabled": False, "lookback_days": 1},
                {"rule_id": "dual_top_overlap", "enabled": False, "lookback_days": 1},
            ],
        )
        settings = Settings(
            trust_top_k=5,
            trust_min_net_lots=50,
            alert_cooldown_days=0,
            exclude_non_equity=False,
        )
        hits = scan_trust_rules(self.db, self.day, settings=settings)
        ids = {h.rule_id for h in hits}
        self.assertIn("trust_top_buy", ids)
        self.assertNotIn("trust_streak", ids)


if __name__ == "__main__":
    unittest.main()
