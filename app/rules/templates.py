"""Built-in scan-rule templates (chip/flow based; no short-term news).

Each template documents purpose and default on/off. Runtime enablement and
lookback (1–90+ days) are stored in RuleConfig and edited from Settings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RuleTemplate:
    id: str
    name: str
    purpose: str
    logic: str
    default_enabled: bool
    default_lookback_days: int
    min_lookback_days: int = 1
    max_lookback_days: int = 90
    category: str = "chip"  # chip | turn | caution
    needs_price: bool = False
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# Keep IDs stable — they are persisted in rule_hits / rule_configs.
RULE_TEMPLATES: tuple[RuleTemplate, ...] = (
    RuleTemplate(
        id="trust_top_buy",
        name="投信買超排行",
        purpose="找出當日投信買超最積極的股票，作為籌碼流入觀察名單。",
        logic="當日 trust_net（張）≥ 門檻，依買超排序取 Top K。",
        default_enabled=True,
        default_lookback_days=1,
        max_lookback_days=1,
        category="chip",
        notes="單日排行；lookback 固定 1 日。",
    ),
    RuleTemplate(
        id="trust_streak",
        name="投信連買",
        purpose="捕捉投信連續多日淨買超的中短線認養訊號。",
        logic="由交易日起回溯，trust_net>0 的連續天數 ≥ lookback（可 1–90）。",
        default_enabled=True,
        default_lookback_days=3,
        min_lookback_days=1,
        max_lookback_days=90,
        category="chip",
        notes="建議先 backfill 足夠歷史日，lookback 才有意義。",
    ),
    RuleTemplate(
        id="foreign_trust_align",
        name="外資投信同向買超",
        purpose="外資與投信同日偏多，降低單一法人噪音。",
        logic="foreign_net>0 且 trust_net>0，且投信買超達門檻一半。",
        default_enabled=True,
        default_lookback_days=1,
        max_lookback_days=1,
        category="chip",
    ),
    RuleTemplate(
        id="foreign_top_buy",
        name="外資買超排行",
        purpose="觀察外資當日主力買超標的（AI 常見補強規則）。",
        logic="當日外資（含外資自營）淨買超 ≥ 門檻，取 Top K。",
        default_enabled=True,
        default_lookback_days=1,
        max_lookback_days=1,
        category="chip",
    ),
    RuleTemplate(
        id="foreign_streak",
        name="外資連買",
        purpose="追蹤外資連續淨買超，偏中短線資金方向。",
        logic="外資淨買超連續天數 ≥ lookback（1–90）。",
        default_enabled=True,
        default_lookback_days=3,
        min_lookback_days=1,
        max_lookback_days=90,
        category="chip",
    ),
    RuleTemplate(
        id="trust_foreign_diverge",
        name="投信獨買／外資賣超",
        purpose="找本土投信與外資意見分歧的標的，作對照參考。",
        logic="trust_net>門檻 且 foreign_net<0。",
        default_enabled=True,
        default_lookback_days=1,
        max_lookback_days=1,
        category="chip",
        notes="非看空訊號；僅標記分歧。",
    ),
    RuleTemplate(
        id="dual_top_overlap",
        name="外資投信雙榜重疊",
        purpose="同時出現在外資與投信買超排行的交集名單。",
        logic="同時進入當日外資 Top K 與投信 Top K。",
        default_enabled=True,
        default_lookback_days=1,
        max_lookback_days=1,
        category="chip",
    ),
    RuleTemplate(
        id="institutional_turn",
        name="三大法人翻多",
        purpose="觀察法人由賣轉買的態度轉折（非新聞驅動）。",
        logic="回顧 lookback 日前半偏賣、最近交易日 total_net>0 且 trust_net>0。",
        default_enabled=True,
        default_lookback_days=5,
        min_lookback_days=3,
        max_lookback_days=90,
        category="turn",
        notes="需要至少 lookback 日歷史資料。",
    ),
    RuleTemplate(
        id="trust_cum_buy",
        name="投信累計買超",
        purpose="看 lookback 窗口內投信累計淨買超是否達標（適合 5–60 日）。",
        logic="近 lookback 日 trust_net 加總（張）≥ 門檻 × lookback/3。",
        default_enabled=False,
        default_lookback_days=20,
        min_lookback_days=5,
        max_lookback_days=90,
        category="chip",
        notes="預設關閉；長窗需較完整 backfill。",
    ),
    RuleTemplate(
        id="foreign_cum_buy",
        name="外資累計買超",
        purpose="看 lookback 窗口內外資累計淨買超是否達標。",
        logic="近 lookback 日外資淨買超加總（張）≥ 門檻 × lookback/3。",
        default_enabled=False,
        default_lookback_days=20,
        min_lookback_days=5,
        max_lookback_days=90,
        category="chip",
        notes="預設關閉。",
    ),
    RuleTemplate(
        id="crowded_trust_fade",
        name="投信買超過熱（警示）",
        purpose="連續多日出現在投信買超排行，作過熱／減碼觀察（反向參考）。",
        logic="近 lookback 日中，有 ≥ ceil(lookback*0.6) 日進入投信買超 Top K。",
        default_enabled=False,
        default_lookback_days=10,
        min_lookback_days=5,
        max_lookback_days=90,
        category="caution",
        notes="預設關閉；不是買訊，是擁擠度警示。",
    ),
    RuleTemplate(
        id="total_streak",
        name="三大法人連買",
        purpose="三大法人合計連續淨買超，偏資金共振。",
        logic="total_net>0 連續天數 ≥ lookback。",
        default_enabled=False,
        default_lookback_days=3,
        min_lookback_days=1,
        max_lookback_days=90,
        category="chip",
        notes="預設關閉。",
    ),
)

TEMPLATES_BY_ID = {t.id: t for t in RULE_TEMPLATES}


def list_templates() -> list[dict[str, Any]]:
    return [t.as_dict() for t in RULE_TEMPLATES]


def get_template(rule_id: str) -> RuleTemplate | None:
    return TEMPLATES_BY_ID.get(rule_id)
