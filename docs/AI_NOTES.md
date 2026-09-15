# AI 分析註記（操作指令／參考價）

本文件說明 AI 層如何產生**清楚訊號**與**客觀參考價**。  
所有輸出僅供觀察，**不構成投資建議**。

## 資料流

```text
RuleHit（規則命中）
   └─ PriceBand（近十日 OHLCV → 客觀 buy/sell/stop）
         └─ xAI（理由 + action_command + action_plan）
               └─ 風險覆寫／價格 clamp
                     └─ AiInsight（DB）→ UI / 通知
```

相關程式：

| 檔案 | 職責 |
|------|------|
| `app/services/price_bands.py` | 客觀價格帶與參考價（非 LLM） |
| `app/services/ai_analysis.py` | Prompt、指令正規化、風險覆寫、寫入 DB |
| `app/models/entities.py` → `AiInsight` | 持久化欄位 |
| `web/src/pages/AiPage.tsx` | 操作指令／參考價展示 |

## 操作指令（action_command）

| 指令 | 含義 |
|------|------|
| `BUY` | 可偏多進場（需有上檔空間、非追高） |
| `WAIT_PULLBACK` | 看好但等回檔到 `buy_ref` |
| `HOLD` | 持有／觀望，暫不新做 |
| `REDUCE` | 減碼、降低曝險 |
| `SELL` | 偏空了結／出場 |
| `AVOID` | 避開不碰 |
| `BREAKOUT_WATCH` | 等突破區間高點再評估 |

實作約束（`_normalize_action_command` + quant overlays）：

- 模型若回傳未知字串，會對應到固定集合。
- `risk_level=high` 時禁止直接 `BUY`（改 `WAIT_PULLBACK`）。
- `risk_level=avoid` 強制 `AVOID`。
- 已近區間上緣（`range_position ≥ 0.95`）時，`BUY` 會降為 `BREAKOUT_WATCH`。
- 上檔／下檔比（upside/downside）&lt; 0.8 時，不給 `BUY`。

## 客觀參考價

先由行情計算（`price_bands._objective_refs`）：

| 欄位 | 怎麼來 | 用途 |
|------|--------|------|
| `buy_ref` | MA5 與「低點–收盤中點」較低者，夾在區間內 | 回檔承接參考 |
| `sell_ref` | 近十日最高 | 減碼／壓力參考 |
| `stop_ref` | 近十日最低 × 0.985（必要時退回最低） | 防守／失效參考 |

模型可微調這三個價，但 `ai_analysis` 會把結果 **clamp** 回 `watch_low`～`watch_high`，避免空想目標價。

## action_plan

2–4 步短指令，例如：

1. 回檔到 `buy_ref` 再分批評估  
2. 跌破 `stop_ref` 停看／減碼  
3. 反彈到 `sell_ref` 減碼  

若模型沒給 plan，會用 `_default_action_plan` 帶入指令與三個參考價。

## 環境變數

```bash
AI_ENABLED=true
XAI_API_KEY=...
AI_MODEL=grok-4.5
AI_MAX_HITS=15          # 每次最多分析幾檔（每檔一卡）
AI_PREFER_UPSIDE=true   # 先挑上檔／下檔比較佳者
```

## 怎麼重跑

```bash
# 已有規則命中時，只重跑 AI
twstock-radar analyze --date 2026-09-11

# 或 UI：AI 觀察 → 執行 AI 分析
# API：POST /ai/analyze?trade_date=2026-09-11
```

舊的 AiInsight 列若沒有 `buy_ref`／`action_command`，重跑 analyze 會覆蓋更新。

## 設計取捨（Notes）

1. **先規則、後 AI**：AI 不掃全市場原始表，只解讀已命中檔，成本與可控性較好。  
2. **價格以量化為主**：LLM 負責措辭與指令選擇，不負責發明價位。  
3. **風險優先於積極**：即使風格偏成長，追高／報酬風險比差仍會降級指令。  
4. **每檔一卡**：同一代碼多條規則時，依優先序與上檔空間只留一則，避免洗版。  
5. **免責**：通知與 UI 皆標示「非投資建議」；`action_command` 是觀察備忘，不是下單指令。
