# Huong dan cau truc file ASO Keyword Filter v4.5

## Root

### `run_aso_filter.py`
Entrypoint chinh. Script parse locale, resolve alias qua `shared/app_registry.py`, archive CSV vao `apps/<AppName>/Input/<MMYYYY>/`, chay runner va ghi workbook vao `apps/<AppName>/Output/<MMYYYY>/`.

### `run_aso_batch.py`
Wrapper tuong thich cho `tools/run_aso_batch.py`. Chay nhieu locale tu JSON manifest; mac dinh toi da 2 job song song.

### `export_master_keywords.py`
Wrapper tuong thich cho `tools/export_master_keywords.py`. Quet input va workbook output cua app, tim sheet theo suffix `Dropped_Audit`, loai hard-drop va ghi workbook tong hop vao `data/master_keywords/`.

### `Sync.bat`
Cong cu pull, status va push mot cham cho nguoi dung Windows.

## `apps/`

Moi app co workspace rieng:

```text
apps/<AppName>/
|-- app_config.py
|-- App_Profile.json
|-- PROJECT_MEMORY.md
|-- Input/<MMYYYY>/
|-- Output/<MMYYYY>/
`-- runner Python
```

App da dang ky:

- `apps/AR_Filter/`
- `apps/Control_Widget/`
- `apps/ElectricGun/`
- `apps/Emoji_Battery_Icon_Customize/`
- `apps/FunVid/`
- `apps/Game_Emulator/`
- `apps/NDS_Emulator/`
- `apps/Prank_Sounds/`
- `apps/App_Template/`

`AR_Filter` va `Control_Widget` van dung runner `*_v4_3.py`. `Game_Emulator` dung runner `run_game_emulator_v4_4.py`. `ElectricGun`, `Emoji_Battery_Icon_Customize`, `FunVid`, `NDS_Emulator`, `Prank_Sounds` va `App_Template` dung `run_pipeline.py`.
Seed filename `FunVid_100_Keywords_<locale>.csv` va `FunVid_AnimalFace_<locale>.csv` cung duoc route ve app `FunVid` qua registry alias.

## `shared/`

- `shared/paths.py`: nguon path tap trung cho `apps`, `docs`, `data` va `data/master_keywords`.
- `shared/app_registry.py`: map alias app chinh xac toi folder, runner va config.
- `shared/effective_config.py`: load effective app config giong runtime, gom ca legacy runner config va `FILTER_POLICY`.
- `shared/locale_parser.py`: parser locale dung chung cho orchestrator, exporter, tracker va batch.
- `shared/language_detector.py`: nhan dien ngon ngu theo market policy.
- `shared/agentic_keyword_classifier.py`: classifier/cache-only runtime dung provider `antigravity_subagent`; runner fail-fast neu thieu cache.
- `shared/ai_keyword_classifier.py`: shim tuong thich, re-export sang `agentic_keyword_classifier`.
- `shared/en_gloss_resolver.py`: resolve cot `EN` tu CSV hoac `AIEnglishGloss`, khong goi translation network.
- `shared/keyword_filter/`: matcher precompiled, hard filter, classifier, validator, audit, cache atomic, truncation hardening complete-token aware va `shortlist.py` cho main keyword shortlist chung `target 40 utility + diversity` (dedup theo utility, semantic cluster diversity qua Jaccard similarity, safe-backfill co kiem tra day du score/relevancy/demand). `scoring.py` con co `safe_reach_ceiling` (reach ceiling percentile 95 chong outlier competitor/irrelevant) va `dampen_stacked_relevancy` (cap RelevancyScore cho keyword nhoi tu khoa nhung demand yeu). `report_export.py::write_quality_log_sheet` xuat canh bao selector (`SAFE_POOL_EXHAUSTED`) ra sheet `15_Selector_Quality_Log`. Xem section 36 trong `ASO_Keyword_Planner_v4_5.md`.
- `shared/text_dedup.py`: dedup Unicode cho `01_Main_Keyword_Shortlist`.
- `shared/profile_service.py`: custom/generated profile cache va stale fallback.
- `shared/project_memory.py`: doc `app_config.py` va `App_Profile.json` de render Project Memory cho Dashboard, workbook va `PROJECT_MEMORY.md`.

## `tools/`

- `tools/run_aso_batch.py`: batch implementation.
- `tools/export_master_keywords.py`: Master Keywords exporter implementation.
- `tools/warm_cache_helper.py`: workflow chinh thuc cho agentic cache toan du an: `find-misses`, `prepare-batches`, `save-results`, `verify-cache`.
- `tools/generate_funvid_csv.py`, `tools/generate_animalface_csv.py`, `tools/generate_100_keywords_csv.py`: tao seed CSV mau cho app FunVid.

Wrapper tai root duoc giu de cac lenh cu van chay.

## `.agents/`

- `.agents/skills/aso-keyword-research/SKILL.md`: skill noi bo huong dan Agent mo rong seed keyword set theo app, dua tren config/profile, competitor research, local search behavior va web research. Skill nay phuc vu buoc nghien cuu dau vao, khong thay the pipeline/filter runner.
- `.agents/skills/aso-keyword-research/agents/openai.yaml`: metadata UI toi thieu cho skill, gom display name, short description va default prompt.

Validation hien tai: parser cuc bo pass; skill khong con `file:///`, `search_web`, mismatch giua folder va skill name. `quick_validate.py` cua skill-creator can module Python `yaml`/`PyYAML`; neu moi truong chua cai PyYAML thi validator chuan se khong chay duoc, nhung cac rule form chinh da duoc kiem bang script cuc bo.

## `tracker/`

- `tracker/run_dashboard.py`: Flask API, web launcher va API `GET /api/setup/<app_name>` cho tab Setup.
- `tracker/db_manager.py`: SQLite schema va query.
- `tracker/data_scanner.py`: quet CSV trong `apps/*/Input/`.
- `tracker/static/`: SPA HTML, CSS va JavaScript, gom tab `Setup` de xem app identity, keyword setup, competitor setup, drop policy, overrides va warnings.

Database `tracker/keyword_tracker.db` la file local va khong commit len Git.

## `docs/`

- `docs/ASO_Keyword_Planner_v4_5.md`: dac ta logic pipeline v4.5, gom quota shortlist moi, sheet `13_Top_By_Volume`, app `FunVid` va agentic cache-only.
- `apps/Game_Emulator/AGENTIC_CACHE_WORKFLOW.md`: huong dan flow cache-only moi cho Game Emulator, thay cho cac script scratch.
- `docs/SETUP_WINDOWS.md`: checklist phan mem, extension, Python packages va cach kiem tra moi truong Windows.
- `docs/App_Config_Template.py`: template config.
- `docs/App_Profile_Template.json`: template profile.
- `docs/english_words_10k.txt`: whitelist tieng Anh.
- `docs/DESIGN.md`: design system cua dashboard.
- `.env.example`: template bien moi truong local neu can cho tooling phu; runner ASO khong doc API key AI runtime.

## `data/`

- `data/google_play_country_language_map.xlsx`: mapping quoc gia va ngon ngu.
- `data/master_keywords/`: workbook Master Keywords generated, khong commit len Git.

## `tests/`

Regression test cho registry, parser locale, hard filter, truncation false positive, dedup, EN gloss resolver, profile, project memory, exporter va batch runner.
`tests/test_ai_keyword_classifier.py` bao phu cache-only hit/miss, canonical duplicate reuse va pre-AI skip/preserve rule.
`tests/test_en_gloss_resolver.py` bao phu uu tien cot `EN`, fallback `AIEnglishGloss` va fail-fast khi keyword non-English thieu gloss.
`tests/test_warm_cache_helper.py` bao phu effective config, batch contract va validation result cua agentic cache.

## `releases/`

Chua zip package local. File zip bi ignore de repository source gon nhe.

## File setup tai root

- `requirements.txt`: danh sach Python packages cho moi truong pipeline day du.
- `.vscode/extensions.json`: de xuat extension VS Code cho Python, Pylance va CSV.
