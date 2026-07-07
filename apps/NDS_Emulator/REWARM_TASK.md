# Work Order - Re-warm NDS_Emulator Agentic Cache With A Stricter Rubric

**Owner:** Antigravity agent using `warm-agentic-cache`.
**App:** `NDS_Emulator` alias `SuperNDS`, app id `com.emulator.nds.super.game.console.handheld`, `semantic_mode = game_emulator`.
**Date:** 2026-07.

---

## 1. Why Re-warm

The current warm pass, especially in **BR_PT**, labeled AI results too loosely. Broad/category/IP keywords leaked into the Main Shortlist:

- **199** keywords were labeled `feature_intent -> Feature Keywords` at confidence `1.0`, including generic/bare-category terms (`emulator`, `games`, `gba`, `snes`, `videogame`), device attributes (`tilt`/`inclinacao`, `portable`/`portatil`), and broad retro variants (`gba retro`, `boy gba`, `games retro`, `gaming emulator`).
- **38** keywords that the subagent itself recognized as IP (`classic_ip_intent`) were still placed into `Consider Keywords` instead of `Dropped`; 14 leaked through, including `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug`, `crash`, `goku`, and `pokedex`.

This is a cache-labeling problem at the AI layer, not a pipeline bug. The root fix is to re-warm with the stricter rubric in section 4.

Deterministic guardrails have already been added: `classic_ip_intent` now drops, publisher brands are in `risky_ip_terms`, and the functional-anchor rule blocks brand + filler terms. This re-warm cleans cache content; deterministic guardrails remain the safety net for future runs.

---

## 2. Scope

Bumping `ruleset_version` changes the `context_hash` for every market of this app. Re-warm every market you plan to run after the bump.

| Market | Source CSV |
|---|---|
| BR_PT | `apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv` |
| MX_ES | `apps/NDS_Emulator/Input/072026/NDS Emulator_MX_ES.csv` |
| ID_ID | `apps/NDS_Emulator/Input/072026/NDS Emulator_ID_ID.csv` |
| IN_HI | `apps/NDS_Emulator/Input/072026/NDS Emulator_IN_HI.csv` |
| US_EN | `apps/NDS_Emulator/Input/072026/NDS Emulator_US_EN.csv` |

If you only re-warm a subset, any unwarmed market you later run will fail with cache-only `AIKeywordClassifierError`.

---

## 3. Step 0 - Bump `ruleset_version`

In `apps/NDS_Emulator/app_config.py`, add one top-level key in `APP_CONFIG` near `"market"` / `"semantic_mode"`:

```python
    "ruleset_version": "2026-07-strict-v1",
```

This orphans all old cache rows by changing `context_hash`, so `find-misses` reports all keywords as missing and forces classification from scratch under the new rubric. Old cache rows are not deleted; they remain under the old hash and can be recovered.

After the bump and before re-warm is complete, the pipeline will fail cache-only. That is expected.

---

## 4. Stricter Rubric

Apply this rubric when classifying. Always ground decisions in the app's real `intent_core_terms`, `feature_terms`, and `style_terms`.

### `semantic_bucket` Decision Rules

1. **`Dropped` for every specific game IP. Never use `Consider` for IP.**

   Any game title, franchise, character, or series: `mario`, `super mario`, `zelda`, `pokemon`, `pokedex`, `pokemon fire red`, `gta`, `grand theft auto`, `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug`, `sonic`, `crash`, `goku`, `dragon ball`, `metroid`, `kirby`, `fifa`, `pes`.

   Use `semantic_bucket: "Dropped"`, `decision_rule: "ai_classic_ip"` or legacy `classic_ip_intent`.

2. **`Dropped` for competitor, accessory, publisher, or store brands.**

   Competitor emulator apps (`vgbanext`, `drastic`, `citra`), controller brands (`gamesir`), publishers (`rockstar`, `rockstargames`, `2k`, `konami`, `capcom`), and stores (`google play`).

   Use `decision_rule: "ai_competitor"` or `ai_classic_ip` for publisher/game-IP.

3. **`Core Intent Final` only for core app search intent.**

   Use this only when the query matches `intent_core_terms`: `nds/ds emulator`, `nintendo ds emulator`, `supernds`, `retro/console/game/multi/all-in-one emulator`.

   Use `decision_rule: "ai_core_intent"`.

4. **`Feature Keywords` only for concrete supported features or specific supported systems.**

   Concrete features: `controller/gamepad skins`, `custom buttons`, `save/load state`, `cheat codes`, `dual screen`, `rom scanner/downloader`, `bluetooth controller`, `touch controls`.

   Specific systems with emulator/ROM/play intent: `gba emulator`, `snes emulator`, `n64 emulator`, `psp emulator`, `nds roms`, `ds games`.

   Use `decision_rule: "ai_feature"`. Do not use Feature for generic terms or device attributes.

5. **`Broad Expansion` for related but generic/bare-category terms.**

   Examples: `emulator`, `emulador`, `games`, `jogos`, `videogame`, bare `gba`/`snes`/`nes`, `gaming emulator`, `retro games`, `games retro`, `gba retro`, `boy gba`, `retro console`, `portable`, `portatil`, `tilt`, `inclinacao`, `arcade`.

   Use `decision_rule: "ai_broad_expansion"`.

6. **`Style Keywords` for style terms.**

   Examples: `retro`, `nostalgia`, `classic`, `vintage`, `8-bit`, `16-bit`, `oldschool`, `90s`, `childhood`.

   Use `decision_rule: "ai_style"`.

7. **Language and ambiguity rules.**

   Use `Language Mismatch Audit` (`ai_lang_mismatch`) for wrong-market language. Use `Manual Review` (`ai_manual_review`) only for truly ambiguous cases. Use `Consider Keywords` only for neutral terms that do not fit any earlier group. Never use Consider to avoid dropping IP.

### Examples From The Bad Cache

| Keyword | Wrong Current Label | Correct New Label |
|---|---|---|
| `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug` | Consider / `classic_ip_intent` | `Dropped` / `ai_classic_ip` |
| `tilt`, `inclinacao`, `portable`, `portatil` | Feature | `Broad Expansion` / `ai_broad_expansion` |
| bare `emulator`, `games`, `gba`, `videogame` | Feature | `Broad Expansion` |
| `gaming emulator`, `gba retro`, `boy gba`, `games retro` | Feature | `Broad Expansion` |
| `gamesir`, `vgbanext`, `rockstargames` | Feature | `Dropped` / `ai_competitor` |
| `gba emulator`, `snes emulator`, `save state`, `controller skins` | Feature | `Feature Keywords` |
| `nds emulator`, `retro games emulator` | Core | `Core Intent Final` |

### Other Required Fields

- `detected_language`: lowercase ISO code, such as `pt`, `es`, `id`, `hi`, `en`.
- `language_group`: `PRIMARY`, `SECONDARY`, `MIXED`, `FOREIGN`, or `UNKNOWN` based on `market_language_policy`. Primary language plus one borrowed English brand/console/tech term is `MIXED`, not `FOREIGN`.
- `english_gloss`: short natural English translation; required when `detected_language != en`.
- `confidence`: 0.85-0.95 for clear cases, 0.55-0.75 for genuinely ambiguous cases.

---

## 5. Commands For Each Market

Repeat the `warm-agentic-cache` loop for every market in section 2. Example for `BR_PT`; change `<MARKET>` and CSV name for the other markets.

```powershell
python tools/warm_cache_helper.py find-misses --app NDS_Emulator `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT `
  --output .cache/nds_BR_PT_missing.json

python tools/warm_cache_helper.py prepare-batches `
  --misses .cache/nds_BR_PT_missing.json --output-dir .cache/batches/nds_BR_PT

# For each batch: spawn one subagent, read batch_path, classify with section 4,
# and write only valid JSON to result_path.

python tools/warm_cache_helper.py save-results --app NDS_Emulator `
  --batch <batch_path> --results <result_path> --market BR_PT

python tools/warm_cache_helper.py verify-cache --app NDS_Emulator `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT

python apps/NDS_Emulator/run_pipeline.py `
  --csv "apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv" --market BR_PT `
  --output apps/NDS_Emulator/Output/SuperNDS_BR-PT_Output.xlsx
```

Batch/result JSON shapes are documented in `.agents/skills/warm-agentic-cache/SKILL.md`. `save-results` validates enums and ensures every keyword is classified exactly once before writing SQLite.

---

## 6. Definition Of Done

For each market:

- [ ] `verify-cache` prints `PASS ... 0 missing` and exits 0.
- [ ] The pipeline completes and exports Excel.

Quality checks on `01_Main_Keyword_Shortlist`, at least for BR_PT:

- [ ] No game title/IP such as `mortal kombat`, `naruto`, `resident evil`, `pac man`, or `metal slug` appears anywhere outside `04_Dropped_Audit`.
- [ ] Generic/device-attribute terms such as `tilt`, `inclinacao`, `portable`, `portatil`, bare `emulator`/`games`/`gba`, `gba retro`, and `boy gba` no longer appear in `02_Feature_Keywords`; they should be `Broad Expansion`.
- [ ] The top of `01_Main_Keyword_Shortlist` contains real Core Intent terms such as NDS/DS emulator and retro game emulator, not broad/IP terms.

Optional cache spot-check:

```powershell
python - <<'PY'
import sqlite3
con = sqlite3.connect('.cache/agentic_keyword_analysis.sqlite3')
app = 'com.emulator.nds.super.game.console.handheld'
for m in ('BR_PT', 'MX_ES', 'ID_ID', 'IN_HI', 'US_EN'):
    n = con.execute("SELECT COUNT(*) FROM ai_keyword_analysis WHERE app_id=? AND market=? AND semantic_bucket='Feature Keywords'", (app, m)).fetchone()[0]
    ip = con.execute("SELECT COUNT(*) FROM ai_keyword_analysis WHERE app_id=? AND market=? AND decision_rule IN ('classic_ip_intent','ip_intent','franchise_intent','ai_classic_ip') AND semantic_bucket!='Dropped'", (app, m)).fetchone()[0]
    print(m, 'Feature:', n, '| IP-not-dropped:', ip, '(expected IP-not-dropped = 0)')
PY
```
