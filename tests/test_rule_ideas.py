import datetime as dt
import unittest

from app.models import InstitutionalDaily
from app.services.rule_ideas import generate_rule_ideas, ideas_as_dict
from tests.db_utils import make_test_session


class RuleIdeasTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.db = make_test_session()
        self.day = dt.date(2026, 9, 11)
        self.db.add(
            InstitutionalDaily(
                trade_date=self.day,
                market="twse",
                code="2330",
                name="台積電",
                trust_net=500000,
                foreign_net=100000,
                total_net=600000,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_fallback_ideas(self):
        rows = generate_rule_ideas(self.db, self.day, use_ai=False)
        self.assertGreaterEqual(len(rows), 5)
        payload = ideas_as_dict(rows)
        self.assertTrue(any(item["idea_id"] == "trust_buy_price_up" for item in payload))
        self.assertTrue(all(item["title"] for item in payload))


if __name__ == "__main__":
    unittest.main()
