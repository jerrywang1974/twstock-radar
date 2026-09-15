import datetime as dt
import json
import unittest
from unittest import mock

from app.config import Settings
from app.rules.engine import Hit
from app.services.ai_analysis import analyze_hits
from app.services.price_bands import PriceBand
from tests.db_utils import make_test_session


class AiAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.engine, self.db = make_test_session()
        self.day = dt.date(2026, 9, 11)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_disabled_returns_empty(self):
        settings = Settings(ai_enabled=False, xai_api_key="x")
        hits = [
            Hit(
                trade_date=self.day,
                code="2330",
                name="台積電",
                rule_id="trust_streak",
                reason="投信連買 3 日",
                suggested_action="buy_bias",
                metrics={"streak": 3},
            )
        ]
        self.assertEqual(analyze_hits(self.db, hits, settings=settings), [])

    @mock.patch("app.services.ai_analysis.compute_price_band")
    @mock.patch("app.services.ai_analysis._call_xai")
    def test_analyze_persists_insight(self, call_xai, price_band):
        call_xai.return_value = json.dumps(
            {
                "rationale": "投信連買且價格站上五日線。",
                "action_command": "WAIT_PULLBACK",
                "action_plan": "1) 回檔到 880 再接\n2) 跌破 847 停看\n3) 反彈 920 減碼",
                "action_bias": "watch",
                "risk_level": "medium",
                "growth_score": 6,
                "growth_thesis": "法人連買",
                "avoid_reason": "",
                "risks": "大盤轉弱",
                "buy_ref": 880,
                "sell_ref": 920,
                "stop_ref": 847,
            },
            ensure_ascii=False,
        )
        price_band.return_value = PriceBand(
            last_close=900.0,
            ma5=890.0,
            ma20=880.0,
            watch_low=860.0,
            watch_high=920.0,
            upside_pct=2.22,
            downside_pct=4.44,
            ma5_bias_pct=1.12,
            range_position=0.67,
            buy_ref=880.0,
            sell_ref=920.0,
            stop_ref=847.0,
            source="mock",
        )
        settings = Settings(
            ai_enabled=True,
            xai_api_key="test-key",
            ai_model="grok-4.5",
            ai_max_hits=5,
        )
        hits = [
            Hit(
                trade_date=self.day,
                code="2330",
                name="台積電",
                rule_id="trust_streak",
                reason="投信連買 3 日",
                suggested_action="buy_bias",
                metrics={"streak": 3},
            )
        ]
        rows = analyze_hits(self.db, hits, settings=settings)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].code, "2330")
        self.assertIn("投信連買", rows[0].rationale)
        self.assertEqual(rows[0].action_command, "WAIT_PULLBACK")
        self.assertEqual(rows[0].buy_ref, 880.0)
        self.assertEqual(rows[0].sell_ref, 920.0)
        self.assertEqual(rows[0].stop_ref, 847.0)
        self.assertEqual(rows[0].watch_low, 860.0)
        self.assertEqual(rows[0].watch_high, 920.0)
        self.assertEqual(rows[0].last_close, 900.0)


if __name__ == "__main__":
    unittest.main()
