# 掃市規則範本（Templates）

本文件列出內建掃市規則範本。  
特色：

- **可在「設定」啟用／停用**
- **可調 lookback（約 1–90 日，各規則有上下限）**
- **以籌碼／價量為主，不包含短線新聞衝擊**
- 新增範本時，請同步更新本表與 `app/rules/templates.py`

執行時只有 **enabled=true** 的規則會進入掃市。

## 範本總表

| ID | 名稱 | 用途 | 預設 | 預設 lookback | lookback 範圍 |
|----|------|------|------|---------------|---------------|
| `trust_top_buy` | 投信買超排行 | 當日投信買超最積極名單 | **ON** | 1 | 1 |
| `trust_streak` | 投信連買 | 投信連續淨買超 | **ON** | 3 | 1–90 |
| `foreign_trust_align` | 外資投信同向買超 | 外資＋投信同日偏多 | **ON** | 1 | 1 |
| `foreign_top_buy` | 外資買超排行 | 當日外資買超主力 | **ON** | 1 | 1 |
| `foreign_streak` | 外資連買 | 外資連續淨買超 | **ON** | 3 | 1–90 |
| `trust_foreign_diverge` | 投信獨買／外資賣超 | 意見分歧對照 | **ON** | 1 | 1 |
| `dual_top_overlap` | 外資投信雙榜重疊 | 雙排行交集 | **ON** | 1 | 1 |
| `institutional_turn` | 三大法人翻多 | 由賣轉買轉折 | **ON** | 5 | 3–90 |
| `trust_cum_buy` | 投信累計買超 | N 日累計買超 | **OFF** | 20 | 5–90 |
| `foreign_cum_buy` | 外資累計買超 | N 日累計買超 | **OFF** | 20 | 5–90 |
| `crowded_trust_fade` | 投信買超過熱警示 | 擁擠度／減碼參考 | **OFF** | 10 | 5–90 |
| `total_streak` | 三大法人連買 | 合計連續淨買超 | **OFF** | 3 | 1–90 |

> 長 lookback（例如 20–90）需要先 `backfill` 足夠歷史日，否則條件不易觸發。

## 各規則說明

### 預設開啟（ON）

#### trust_top_buy
- **目的**：快速看到當日投信買超排行。
- **條件**：`trust_net` 達門檻後取 Top K。
- **為何預設 ON**：核心籌碼掃市起點。

#### trust_streak
- **目的**：找投信「持續」買超，不只單日爆量。
- **條件**：連續 lookback 日 `trust_net > 0`。
- **為何預設 ON**：中短線認養觀察常用。

#### foreign_trust_align
- **目的**：外資與投信同向，降低單一法人噪音。
- **條件**：外資淨買超且投信淨買超（投信達半門檻）。
- **為何預設 ON**：共振訊號。

#### foreign_top_buy / foreign_streak
- **目的**：補齊外資視角（AI 規則構想常見項目）。
- **為何預設 ON**：與投信規則對稱，便於對照。

#### trust_foreign_diverge
- **目的**：投信買、外資賣的分歧名單。
- **為何預設 ON**：作參考對照，不是直接看空。

#### dual_top_overlap
- **目的**：同時擠進外資與投信買超排行。
- **為何預設 ON**：高關注交集。

#### institutional_turn
- **目的**：近 lookback 日由賣轉買的態度轉折。
- **為何預設 ON**：非新聞、純籌碼轉折。

### 預設關閉（OFF）

#### trust_cum_buy / foreign_cum_buy
- **目的**：看 5–90 日累計買超，偏波段。
- **為何預設 OFF**：需要較完整歷史；門檻與視窗較敏感，建議手動開啟。

#### crowded_trust_fade
- **目的**：連續多日進投信排行的過熱警示（偏減碼／迴避參考）。
- **為何預設 OFF**：反向規則，避免與偏多規則混淆。

#### total_streak
- **目的**：三大法人合計連買。
- **為何預設 OFF**：與 trust/foreign streak 重疊度高，可選用。

## 如何開關／調天數

1. UI：**設定 → 掃市規則範本**（勾選啟用、改 lookback、儲存）
2. API：
   - `GET /settings/rules`
   - `PUT /settings/rules` body: `{ "rules": [{ "rule_id": "trust_streak", "enabled": true, "lookback_days": 10 }] }`

## 新增範本時請做

1. 在 `app/rules/templates.py` 加 `RuleTemplate`（含 purpose、default_enabled、lookback 範圍）
2. 在 `app/rules/engine.py` 實作掃描邏輯
3. 更新本文件表格與說明
4. （可選）於 AI `rule-ideas` 提示中避免與新 ID 重複

## 不做什麼

- 不依短線新聞／輿情自動加減碼
- AI 規則構想（`rule-ideas`）不會自動變成啟用範本；需人工挑選後再實作進 templates
