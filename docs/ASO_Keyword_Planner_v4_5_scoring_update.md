# ASO Keyword Planner v4.5 — Scoring & Tooling Update

`FILTER_LOGIC_VERSION = v4.5_logreach_rubric_relevancy`

Bản cập nhật này gộp vào release 4.5, tập trung vào **cách chấm điểm** (Volume, Relevancy, BalancedScore), **độ gọn của output**, **bộ skill điều phối**, và các guardrail mới quanh risk/cache. Selection cache bị làm mới do logic chấm điểm đổi. Cache phân loại AI (`agentic_keyword_analysis.sqlite3`) chỉ cần re-warm khi app config bump `ruleset_version`; riêng brand/risk list vẫn là deterministic filter và có hiệu lực ngay mỗi lần chạy.

## 1. Scoring — điểm chính

### VolumeN: chuẩn hóa log trên Reach thật
Reach tăng theo cấp số nhân với Volume (đo thực nghiệm trên 15.7k keyword: `Reach ≈ exp(0.15·Volume)`, R²≈0.72). Cách cũ chuẩn hóa reach tuyến tính (`reach/ceiling`) nghiền >95% keyword về ~0.
- Mới: `VolumeN = log1p(reach) / log1p(reach_reference)` (mặc định `reach_reference = 100000`, cấu hình trong `volume_score_policy`).
- `mode: "reach_linear"` khôi phục hành vi cũ; `reach_reference: 0` dùng ceiling theo dataset.
- Loại penalty `−0.15` cho low-volume (log đã tự dập; `low_tier_score_cap` vẫn là sàn nhiễu duy nhất).

### BalancedScore: bỏ KEIN
KEI là hàm của Volume & Difficulty (collinear) → bỏ, dồn trọng số sang Relevancy.
- Trọng số mới: VolumeN 0.35, DifficultyN 0.15, **RelevancyScore 0.30**, CurrentRankN 0.10, ExpansionValue 0.10 (tổng = 1.0).
- `resolve_balanced_weights()` tự migrate config cũ (còn `KEIN > 0`) sang scheme mới; config không có KEIN được tôn trọng (per-app tunable).

### RelevancyScore: rubric có thang từ phân loại AI
Điểm relevancy nay ưu tiên **rubric deterministic** suy từ cache AI (thay cho float cảm tính):
```
base(AISemanticBucket) − (1 − AIConfidence)·0.15 + language_adjust   (clamp 0..1)
  Core 0.90 | Feature 0.70 | Broad 0.55 | Consider/Style 0.45 | ...
  language: PRIMARY 0 | SECONDARY −0.05 | MIXED −0.05 | UNKNOWN −0.10 | FOREIGN → 0
```
- `RelevancyScore = max(lexical, rubric)`: rubric là chính cho keyword đã phân loại AI; **lexical vẫn cần** làm bộ chấm cho keyword không qua AI (English/deterministic, `AISemanticBucket` rỗng) và mang `CompetitorBoost`.
- "0.90 vs 0.85" nay truy được về tiêu chí (language/confidence), không còn cảm tính; đổi trọng số/base không cần warm lại subagent.

## 2. Output workbook — chế độ lean/full
`shared/report_builder.py` + `output_mode` trong config.
- `lean` (mặc định): giữ các sheet cần thao tác (README, Project Memory, Main Shortlist, các sheet curated, Report Summary, All Candidates); lược các sheet audit/derived (04, 07–15) vốn chỉ là view lọc/sort của `06_All_Candidates`.
- `full`: xuất đầy đủ như trước. Override per-app: `report_output.keep_extra` / `drop_extra`.

## 3. warm-cache tooling (`tools/warm_cache_helper.py`)
- `save-results`: fill gloss-only không ghi đè phân loại tốt; chuẩn hóa hoa/thường + alias cho `semantic_bucket`/`language_group`.
- Gom toàn bộ lỗi thay vì dừng ở lỗi đầu; `--partial` lưu phần hợp lệ + ghi `<batch>_remaining.json` để re-spawn phần lỗi; `--source` (hoặc `$AGENTIC_SUBAGENT_SOURCE`).
- `AIKeywordClassifier._update_english_gloss()` (patch gloss có mục tiêu).
- `ruleset_version`: top-level app config key dùng để invalidate cache semantic khi prompt/rubric agentic đổi. Risk/brand lists không nằm trong context hash vì `classifier.py` hard-filter lại mỗi run.

## 4. Risk guardrails
- `classifier.py` chỉ cho core override với risky/platform term khi term đó là declared-safe trong core/feature vocabulary và keyword có functional anchor riêng. Generic token như `game`, `games`, `play`, `app`, `free` không tự cứu brand.
- `platform_affiliation_terms` không có core override; các phrase kiểu official/affiliation/brand-claim vẫn bị xử lý theo `platform_affiliation_action`.
- AI-recognized classic game IP dùng `AIDecisionRule` như `classic_ip_intent`, `ip_intent`, `franchise_intent`, `ai_classic_ip`; nếu không có override hợp lệ thì classifier áp dụng `risky_ip_action` và ghi rule `ai_classic_ip`.

## 5. Skills điều phối (`.agents/skills/`)
- `run-pipeline-aso`: chạy pipeline đầu-cuối (resolve app → preflight profile/config → warm cache bằng subagent → verify → filter → report).
- `create-profile`: tạo `App_Profile.json` chuẩn schema 2.0, validate bằng `build_project_memory_for_app`.
- `warm-agentic-cache`, `aso-keyword-research`: bổ sung "Execution contract" (MUST/NEVER) + "Definition of done" để tăng tuân thủ.

## 6. Tests
- Mới: `tests/test_scoring_upgrades.py` (log-reach, resolve_balanced_weights, rubric), `tests/test_report_builder.py`, `tests/test_warm_cache_helper.py` (mở rộng).
- Cập nhật `tests/test_volume_score.py` sang ngữ nghĩa log-reach.

## Ghi chú migrate
- App có quy mô reach khác biệt nên chỉnh `reach_reference` trong `volume_score_policy`.
- Selection cache cũ sẽ được tính lại (do `FILTER_LOGIC_VERSION` đổi) — đúng và mong muốn.
- Agentic cache cũ vẫn dùng được nếu `ruleset_version` không đổi. Khi bump `ruleset_version`, chạy lại `warm_cache_helper` cho các market cần pipeline; row cũ không bị xóa, chỉ không còn match context hash mới.
- Dead code runner cũ như `apply_volume_penalty` đã được dọn; phần tùy chọn còn lại là rubric v2 (`positioning_fit`/`specificity` từ subagent) nếu sau này muốn mở rộng.
