# WORK ORDER — Re-warm NDS_Emulator agentic cache with a STRICTER rubric

**Giao cho:** agent Antigravity (chạy skill `warm-agentic-cache`).
**App:** `NDS_Emulator` (alias `SuperNDS`, id `com.emulator.nds.super.game.console.handheld`), `semantic_mode = game_emulator`.
**Ngày:** 2026-07.

---

## 1. Vì sao phải re-warm

Lần warm hiện tại (rõ nhất ở **BR_PT**) gán nhãn AI **quá lỏng**, khiến từ khoá broad/IP lọt vào Main Shortlist:

- **199** keyword bị gán `feature_intent → Feature Keywords` (conf 1.0), kể cả từ generic/bare-category (`emulator`, `games`, `gba`, `snes`, `videogame`), thuộc tính thiết bị (`tilt`/`inclinação`, `portable`/`portátil`), và biến thể retro chung chung (`gba retro`, `boy gba`, `games retro`, `gaming emulator`).
- **38** keyword mà subagent **tự nhận diện là IP** (`classic_ip_intent`) lại bị xếp `Consider Keywords` thay vì `Dropped` → 14 cái lọt (mortal kombat, naruto, resident evil, pac man, metal slug, crash, goku, pokedex...).

Đây là **lỗi gán nhãn ở tầng cache (AI)**, không phải bug pipeline. Cách sửa tận gốc = re-warm với rubric chặt hơn ở Mục 4.

> Lưu ý: phần code deterministic đã được vá bổ trợ (guardrail): IP-tag `classic_ip_intent` giờ bị drop, publisher brands vào `risky_ip_terms`, và luật "functional anchor" chặn brand + từ đệm. Re-warm này làm sạch nội dung cache; guardrail giữ vai trò lưới an toàn cho các lần sau.

---

## 2. Phạm vi

Bump `ruleset_version` (Mục 3) đổi `context_hash` cho **mọi market** của app, nên **tất cả market phải được re-warm lại** trước khi chạy pipeline:

| Market | CSV nguồn |
|---|---|
| BR_PT | `apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv` |
| MX_ES | `apps/NDS_Emulator/Input/072026/NDS Emulator_MX_ES.csv` |
| ID_ID | `apps/NDS_Emulator/Input/072026/NDS Emulator_ID_ID.csv` |
| IN_HI | `apps/NDS_Emulator/Input/072026/NDS Emulator_IN_HI.csv` |
| US_EN | `apps/NDS_Emulator/Input/072026/NDS Emulator_US_EN.csv` |

> Nếu chỉ muốn re-warm một phần, vẫn phải re-warm mọi market bạn định **chạy pipeline** sau khi bump (market chưa warm sẽ báo lỗi `AIKeywordClassifierError` cache-only).

---

## 3. BƯỚC 0 — Bump ruleset_version (làm trước tiên, đúng 1 lần)

Trong `apps/NDS_Emulator/app_config.py`, thêm 1 khoá top-level vào `APP_CONFIG` (đặt cạnh `"market"` / `"semantic_mode"`):

```python
    "ruleset_version": "2026-07-strict-v1",
```

Việc này orphan toàn bộ cache cũ (đổi `context_hash`), nên `find-misses` sẽ báo **toàn bộ keyword là missing** → được phân loại lại từ đầu bằng rubric mới. Cache cũ không bị xoá (vẫn nằm dưới hash cũ, có thể phục hồi).

> ⚠️ Sau khi bump mà **chưa** re-warm xong thì pipeline sẽ lỗi cache-only — đây là hành vi đúng, cứ tiếp tục các bước dưới.

---

## 4. RUBRIC CHẶT HƠN — phần quan trọng nhất

Áp dụng khi phân loại (bổ sung/siết lại rubric trong `.agents/skills/warm-agentic-cache/SKILL.md`). Luôn ground theo `intent_core_terms`/`feature_terms`/`style_terms` thật của app.

### semantic_bucket — luật quyết định (theo thứ tự ưu tiên)

1. **`Dropped` cho MỌI game IP cụ thể** (KHÔNG bao giờ để `Consider`).
   Bất kỳ tên tựa game / franchise / nhân vật / series nào: `mario`, `super mario`, `zelda`, `pokemon` (+ `pokedex`, `pokemon fire red`...), `gta`/`grand theft auto`, `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug`, `sonic`, `crash`, `goku`/`dragon ball`, `metroid`, `kirby`, `fifa`, `pes`...
   → `semantic_bucket: "Dropped"`, `decision_rule: "ai_classic_ip"` (hoặc `classic_ip_intent` nếu cần giữ nhãn legacy).

2. **`Dropped` cho brand đối thủ / phụ kiện / nhà phát hành**: app giả lập đối thủ (`vgbanext`, `drastic`, `citra`...), brand tay cầm (`gamesir`), publisher (`rockstar`/`rockstargames`, `2k`, `konami`, `capcom`...), store (`google play`).
   → `decision_rule: "ai_competitor"` (hoặc `ai_classic_ip` cho publisher/game-IP).

3. **`Core Intent Final`** — CHỈ khi khớp `intent_core_terms` (ý định lõi): các biến thể `nds/ds emulator`, `nintendo ds emulator`, `supernds`, `retro/console/game/multi/all-in-one emulator`.
   → `decision_rule: "ai_core_intent"`.

4. **`Feature Keywords`** — CHỈ khi nêu **tính năng CỤ THỂ** có trong `feature_terms`: `controller/gamepad skins`, `custom buttons`, `save/load state`, `cheat codes`, `dual screen`, `rom scanner/downloader`, `bluetooth controller`, `touch controls`, hoặc **hệ máy cụ thể** (`gba emulator`, `snes emulator`, `n64 emulator`, `psp emulator`, `nds roms`, `ds games`).
   → `decision_rule: "ai_feature"`.
   **KHÔNG** dùng Feature cho từ generic hay thuộc tính thiết bị.

5. **`Broad Expansion`** — từ liên quan nhưng **generic/bare-category/không nêu tính năng cụ thể**:
   `emulator`/`emulador`, `games`/`jogos`, `videogame`, bare `gba`/`snes`/`nes`, `gaming emulator`, `retro games`, `games retro`, `gba retro`, `boy gba`, `retro console`, `portable`/`portátil`, `tilt`/`inclinação`, `arcade`.
   → `decision_rule: "ai_broad_expansion"`.
   Đây là chỗ hứng phần lớn 199 nhãn `feature_intent` sai trước đây.

6. **`Style Keywords`** — khớp `style_terms`: `retro`, `nostalgia`, `classic`, `vintage`, `8-bit`/`16-bit`, `oldschool`, `90s`, `childhood`.
   → `decision_rule: "ai_style"`.

7. **`Language Mismatch Audit`** (`ai_lang_mismatch`) cho nội dung sai ngôn ngữ market; **`Manual Review`** (`ai_manual_review`) khi thực sự mơ hồ; **`Consider Keywords`** chỉ cho trường hợp trung tính không rơi vào nhóm nào ở trên — **tuyệt đối không dùng Consider để "né" việc drop IP**.

### DO / DON'T (ví dụ từ chính data lỗi)

| Keyword | SAI (hiện tại) | ĐÚNG (rubric mới) |
|---|---|---|
| `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug` | Consider / `classic_ip_intent` | **Dropped** / `ai_classic_ip` |
| `tilt` (`inclinação`), `portable` (`portátil`) | Feature | **Broad Expansion** / `ai_broad_expansion` |
| bare `emulator`, `games`, `gba`, `videogame` | Feature | **Broad Expansion** |
| `gaming emulator`, `gba retro`, `boy gba`, `games retro` | Feature | **Broad Expansion** |
| `gamesir`, `vgbanext`, `rockstargames` | Feature | **Dropped** / `ai_competitor` |
| `gba emulator`, `snes emulator`, `save state`, `controller skins` | Feature ✅ | **Feature Keywords** (giữ nguyên) |
| `nds emulator`, `retro games emulator` | Core ✅ | **Core Intent Final** (giữ nguyên) |

### Các field khác (giữ như SKILL.md, quan trọng nhất là ngôn ngữ)
- `detected_language`: ISO thường (`pt`, `es`, `id`, `hi`, `en`).
- `language_group`: `PRIMARY`/`SECONDARY`/`MIXED`/`FOREIGN`/`UNKNOWN` theo `market_language_policy`. Primary + 1 từ mượn tiếng Anh (brand/console/tech) = `MIXED`, không phải `FOREIGN`.
- `english_gloss`: bản dịch ngắn tự nhiên; bắt buộc khi `detected_language != en`.
- `confidence`: 0.85–0.95 cho case rõ; 0.55–0.75 cho mơ hồ.

---

## 5. Các lệnh chạy — lặp cho TỪNG market

Chạy vòng lặp skill `warm-agentic-cache` cho mỗi market trong Mục 2. Ví dụ với `BR_PT` (đổi `<MARKET>` và tên CSV cho các market còn lại):

```powershell
# 5.1 Tìm keyword thiếu (sau khi đã bump ruleset_version -> sẽ là TẤT CẢ)
#     Dùng --output tường minh để bước 5.2 tham chiếu đúng file.
python tools/warm_cache_helper.py find-misses --app NDS_Emulator `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT `
  --output .cache/nds_BR_PT_missing.json

# 5.2 Chia batch (200 kw/batch)
python tools/warm_cache_helper.py prepare-batches `
  --misses .cache/nds_BR_PT_missing.json --output-dir .cache/batches/nds_BR_PT

# 5.3 Với MỖI batch: spawn 1 subagent, đọc batch_path, phân loại theo RUBRIC Mục 4,
#     ghi ra result_path đúng schema (không in gì khác).

# 5.4 Lưu kết quả (lặp cho từng batch)
python tools/warm_cache_helper.py save-results --app NDS_Emulator `
  --batch <batch_path> --results <result_path> --market BR_PT

# 5.5 Nghiệm thu: phải in "PASS ... 0 missing"
python tools/warm_cache_helper.py verify-cache --app NDS_Emulator `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT

# 5.6 Chạy pipeline thật
python apps/NDS_Emulator/run_pipeline.py `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT `
  --output apps/NDS_Emulator/Output/SuperNDS_BR-PT_Output.xlsx
```

Định dạng batch/result JSON: xem `.agents/skills/warm-agentic-cache/SKILL.md` (mục "Batch JSON shape" / "Result JSON shape"). `save-results` sẽ validate enum + đảm bảo mọi keyword được phân loại đúng 1 lần trước khi ghi SQLite.

---

## 6. Nghiệm thu (Definition of Done)

Với mỗi market:
- [ ] `verify-cache` in `PASS ... 0 missing` (exit 0).
- [ ] Pipeline chạy xong, xuất Excel.

Kiểm tra chất lượng trên sheet `01_Main_Keyword_Shortlist` (ít nhất market BR_PT):
- [ ] **Không còn** tên tựa game/IP (`mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug`...) ở bất kỳ sheet nào ngoài `04_Dropped_Audit`.
- [ ] **Không còn** từ generic/thuộc tính (`tilt`/`inclinação`, `portable`/`portátil`, bare `emulator`/`games`/`gba`, `gba retro`, `boy gba`) nằm trong `02_Feature_Keywords` — chúng phải ở `Broad Expansion`.
- [ ] `01_Main_Keyword_Shortlist` phần đầu là các từ Core Intent thật (nds/ds emulator, retro game emulator...), không bị broad/IP chiếm chỗ.

Đối chiếu nhanh bằng cache (tuỳ chọn):
```powershell
python - <<'PY'
import sqlite3
con=sqlite3.connect('.cache/agentic_keyword_analysis.sqlite3')
app='com.emulator.nds.super.game.console.handheld'
for m in ('BR_PT','MX_ES','ID_ID','IN_HI','US_EN'):
    n=con.execute("SELECT COUNT(*) FROM ai_keyword_analysis WHERE app_id=? AND market=? AND semantic_bucket='Feature Keywords'",(app,m)).fetchone()[0]
    ip=con.execute("SELECT COUNT(*) FROM ai_keyword_analysis WHERE app_id=? AND market=? AND decision_rule IN ('classic_ip_intent','ip_intent','franchise_intent','ai_classic_ip') AND semantic_bucket!='Dropped'",(app,m)).fetchone()[0]
    print(m, 'Feature:',n,'| IP-not-dropped:',ip,'(kỳ vọng IP-not-dropped = 0)')
PY
```
