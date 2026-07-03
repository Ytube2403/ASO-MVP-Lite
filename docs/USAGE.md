# ASO MVP Usage Guide

Tai lieu nay la huong dan thao tac hien hanh cho nguoi chay pipeline. Spec chi tiet nam o `docs/ASO_Keyword_Planner_v4_5.md`; file nay chi tap trung vao dung thu tu van hanh.

## 1. Chuan bi mot app

Moi app can co:

- `apps/<AppName>/app_config.py`: identity, market, semantic groups, filters, scoring/risk policy.
- `apps/<AppName>/App_Profile.json`: live metadata va competitor profile.
- CSV keyword dau vao tu AppTweak/SensorTower, dat theo market ro rang, vi du `NDS Emulator_BR_PT.csv`.

Neu sua brand/risk lists nhu `risky_ip_terms`, `risky_platform_terms`, `competitor_brands`, `platform_affiliation_terms`, chay lai pipeline la co hieu luc ngay. Khong can warm lai cache AI.

Chi bump top-level `ruleset_version` khi prompt/rubric agentic thay doi va ban muon phan loai lai `AISemanticBucket`/`AIDecisionRule` cu. Sau khi bump, phai warm lai cac market se chay pipeline.

## 2. Dat CSV vao dung cho

Khuyen nghi de CSV trong:

```text
apps/<AppName>/Input/<MMYYYY>/<AppName>_<MARKET>.csv
```

Vi du:

```text
apps/NDS_Emulator/Input/072026/NDS Emulator_BR_PT.csv
```

Co the truyen CSV tu bat ky duong dan nao cho `run_aso_filter.py`; orchestrator se archive input vao app folder.

## 3. Kiem tra agentic cache truoc khi chay

Runtime pipeline la cache-only: runner khong goi AI/translation network. Truoc khi chay pipeline that, kiem tra cache:

```powershell
python tools/warm_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

Neu output la `PASS ... 0 missing`, co the chay pipeline.

Neu fail vi thieu intent hoac `english_gloss`, warm cache theo thu tu:

```powershell
python tools/warm_cache_helper.py find-misses --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET> --output .cache/<app>_<market>_missing.json
python tools/warm_cache_helper.py prepare-batches --misses .cache/<app>_<market>_missing.json --output-dir .cache/agentic_batches
```

Sau do dung Antigravity/Codex/subagent de phan loai tung batch theo `.agents/skills/warm-agentic-cache/SKILL.md`, roi luu ket qua:

```powershell
python tools/warm_cache_helper.py save-results --app <AppName> --batch <batch_path> --results <result_path> --market <MARKET>
python tools/warm_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

Chi chay pipeline sau khi `verify-cache` pass.

## 4. Kiem tra metadata/ads suitability cache

Sau agentic cache, pipeline con co post-candidate gate rieng cho `MetadataEligible`/`AdsEligible`. Gate nay khong thay the relevancy: no chi tra loi cau hoi "keyword nay co dang dung trong metadata/ads khong?". Vi du `arcade`, `pizza`, `moonlight`, `turbospeed` co the lien quan den feature nhung qua rong khi dung mot minh, nen se vao `ResearchOnly`. Cac atomic platform terms nhu `nds`, `ds`, `gba` duoc giu neu nam trong config keep list.

Kiem tra cache suitability neu app/market co broad single-token hoac feature ambiguous:

```powershell
python tools/suitability_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

Neu fail, tao batch cho subagent audit:

```powershell
python tools/suitability_cache_helper.py find-misses --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET> --output .cache/<app>_<market>_suitability_missing.json
python tools/suitability_cache_helper.py prepare-batches --misses .cache/<app>_<market>_suitability_missing.json --output-dir .cache/suitability_batches
```

Subagent result phai co cac field `keyword`, `suitability_bucket`, `metadata_eligible`, `ads_eligible`, `research_only`, `confidence`, `decision_rule`, `reason`. Luu va verify lai:

```powershell
python tools/suitability_cache_helper.py save-results --app <AppName> --batch <batch_path> --results <result_path> --market <MARKET>
python tools/suitability_cache_helper.py verify-cache --app <AppName> --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --market <MARKET>
```

Ghi chu: deterministic rule van thang subagent. Risk/drop/language/manual-review khong duoc rescue; single-token block terms van bi `SINGLE_TOKEN_TOO_BROAD`; single-token keep terms van duoc eligible.

## 5. Chay pipeline

Uu tien orchestrator trung tam tu root repo:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName>
```

Che do interactive:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName> --interactive
```

Neu CSV name du de resolve app, co the bo `--app`. Khi app co alias de nham, nen truyen `--app` ro rang.

## 6. Review workbook output

Sau khi chay xong, mo workbook trong `apps/<AppName>/Output/<MMYYYY>/`.

Can review toi thieu:

- `00_Project_Memory`: app/profile/config snapshot dung cho audit.
- `01_Main_Keyword_Shortlist`: danh sach metadata-safe target 40 theo utility + diversity, chi gom row `MetadataEligible=True`.
- `04_Dropped_Audit`: keyword bi loai va ly do drop.
- `06_All_Candidates`: audit cot `PreAIRule`, `AISemanticBucket`, `AIDecisionRule`, `AIReason`, `AIEnglishGloss`, `MetadataEligible`, `AdsEligible`, `ResearchOnly`, `SuitabilityRule`, `SuitabilityReason`.
- `13_Top_By_Volume`: keyword sach co volume cao de kiem tra nhanh co bi bo sot.
- `14_Not_Selected_Audit`: xem reason `SINGLE_TOKEN_TOO_BROAD` hoac `SUITABILITY_RESEARCH_ONLY` de audit keyword lien quan nhung khong nen dung metadata/ads.
- `15_Selector_Quality_Log` neu co: canh bao selector/backfill.

Voi game/emulator apps, can chu y keyword IP/game/franchise/brand. Cac tu nhu `mortal kombat`, `naruto`, `resident evil`, `pac man`, `metal slug` chi nen nam trong Dropped Audit, khong vao shortlist/feature sheets.

## 7. Khi nao can chay lai

- Sua `app_config.py` risk/brand/noise/feature/core terms: chay lai pipeline; cache AI khong can warm lai.
- Sua `App_Profile.json`: chay lai pipeline; neu profile anh huong context agentic va verify-cache bao miss thi warm them.
- Bump `ruleset_version`: warm lai moi market can chay, roi moi run pipeline.
- Sua `metadata_suitability.single_token_policy.keep_terms`/`block_terms`: chay lai pipeline. Neu verify suitability bao miss vi context hash doi, warm lai suitability audit cho market do.
- CSV moi hoac market moi: verify-cache truoc; neu miss thi warm cache.

## 8. Lenh batch

Dung manifest:

```powershell
python run_aso_batch.py --manifest path\to\manifest.json
```

Batch runner van tuan thu cache-only. Neu market nao con miss, job do fail-fast; warm cache cho market do roi chay lai.
