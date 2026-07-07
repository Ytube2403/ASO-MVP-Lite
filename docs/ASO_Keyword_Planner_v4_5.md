# ASO Keyword Planner

**Version:** 4.5
**Former name:** ASO Keyword Master Pipeline - Universal Template
**Current name:** ASO Keyword Planner
**Purpose:** Filter, score, classify, audit, and export ASO keyword shortlists per app, market, language, and metadata platform.
**Use cases:** Google Play keyword research, App Store keyword planning, metadata QA, ASO testing, UA keyword review, and keyword research audit.

This is the complete v4.5 specification for ASO-MVP. Keep this file as the single complete planner spec. Operational quick-start notes may live in `docs/USAGE.md`, but the full decision contract belongs here.

The beginner HTML guide `docs/ASO_Antigravity_Beginner_Guide.html` is intentionally excluded from English-only cleanup and can remain in its original language.

---

## 0. Core Philosophy

ASO Keyword Planner is not just a keyword filter. Its goal is to produce a **keyword decision workbook**:

- which keywords are safe enough to use now;
- which keywords are worth keeping for consideration;
- which keywords are useful only as supporting research;
- which keywords require manual or subagent audit;
- which keywords must be dropped.

The pipeline must avoid three common failures:

1. **Over-optimizing for score.**
   A high Volume or high BalancedScore keyword can still be too broad, risky, or weak for metadata.

2. **Over-dropping risky-but-relevant language.**
   Some platform-style terms can be relevant when the app genuinely supports that platform or feature. Risk rules must be strict, but not blind.

3. **Letting the wrong market language into primary metadata.**
   Keywords outside the market language should not enter the main shortlist just because they score well. Valid secondary or mixed-language behavior should be handled explicitly.

Core rule:

```text
A top keyword is not merely the highest-scoring keyword.
A top keyword must be usable, relevant, market-appropriate, metadata-safe, platform-safe, and risk-aware.
```

---

## 0.1 Input CSV Specifications

The input CSV must be predictable enough for the pipeline to normalize, score, and audit without hidden assumptions.

### 0.1.1 File Format And Encoding

- Encoding must be `UTF-8` or `UTF-8 with BOM` (`utf-8-sig`).
- Delimiter must be a comma.
- Keyword text must preserve local-language characters and diacritics.
- Empty keyword rows are ignored.
- Runtime must not require Excel-specific formatting.

### 0.1.2 File Naming And Storage

Recommended filename:

```text
<AppName>_<COUNTRY>_<LANGUAGE>.csv
```

Examples:

```text
ARFilter_US_EN.csv
ControlWidget_BR_PT.csv
NDS Emulator_ID_ID.csv
```

Recommended app input folder:

```text
apps/<AppName>/Input/<MMYYYY>/<file>.csv
```

Examples:

```text
apps/AR_Filter/Input/052026/ARFilter_US_EN.csv
apps/NDS_Emulator/Input/072026/NDS Emulator_ID_ID.csv
```

The root orchestrator may accept CSVs from another path, but it should archive or report the app output under the registered app workspace.

### 0.1.3 Required And Optional Columns

| Column | Type | Required | Meaning And Fallback |
|---|---|---:|---|
| `Keyword` | text | yes | Keyword to evaluate. Empty rows are skipped. |
| `Volume` | integer | no | Current search volume. Missing or invalid values become `0`. |
| `Max. Volume` / `Max Volume` | integer | no | Maximum historical search volume. Missing values fall back to `Volume`. |
| `MaximumReach` / `Maximum Reach` | integer/float | no | Estimated maximum impressions or reach. Preferred for traffic normalization when present. |
| `Difficulty` | integer | no | Keyword difficulty from `0` to `100`. Missing values become `0`. |
| `KEI` | float | no | Keyword efficiency index. Kept for audit; not part of the default v4.5 BalancedScore. |
| `Rank` / `CurrentRank` | text/integer | no | Current app rank. Missing values become `Unranked`. |
| `EN` | text | no | English gloss supplied by the source CSV. Used before AI cache gloss. |

### 0.1.4 Automatic Type Normalization

During ingestion:

1. Numeric fields are coerced safely.
2. Missing numeric values become `0`.
3. Missing `Max. Volume` falls back to `Volume`.
4. Missing rank becomes `Unranked`.
5. Duplicate or equivalent column names are normalized to canonical names.
6. Keyword text is normalized without destroying meaningful local characters.

---

## 1. Final Output

The default output is one Excel workbook:

```text
ASO_Keyword_Planner_<AppName>_<Market>.xlsx
```

The workbook is the single source of truth for the run: shortlist, feature/style groups, dropped rows, audit trail, scoring, suitability, and setup context.

### 1.1 Required Workbook Sheets

| Sheet | Purpose | Notes |
|---|---|---|
| `00_README_CONFIG` | Run summary, app, market, config snapshot, run time | Required |
| `00_Project_Memory` | App/profile/config setup summary | Required when project memory is available |
| `01_Main_Keyword_Shortlist` | Main metadata-safe shortlist | Target 40 rows |
| `02_Feature_Keywords` | Feature/type/function keywords | Usually up to 30 rows |
| `03_Style_Keywords` | Style/theme/visual keywords | Usually up to 30 rows |
| `04_Dropped_Audit` | Dropped keywords and drop reasons | No row limit |
| `05_Report_Summary` | Aggregate report | Required |
| `06_All_Candidates` | Full candidate audit table | Required |
| `13_Top_By_Volume` | Clean high-volume opportunity view | Usually 30 rows |
| `14_Not_Selected_Audit` | Safe or research-only rows not selected into main shortlist | Required when selector audit is available |
| `15_Selector_Quality_Log` | Selector quality warnings | Required when quality log exists |

### 1.2 Conditional Sheets

Create these only when relevant data exists, or create an empty sheet with `NO_DATA` when a stable workbook schema is desired:

| Sheet | Purpose |
|---|---|
| `07_Language_Mismatch` | Keywords outside market language policy |
| `08_Generic_Style_Reserve` | Broad style keywords held for research |
| `09_Manual_Review` | Rows requiring human decision |
| `10_Top_By_Score` | Top candidates by BalancedScore for audit |
| `11_Secondary_Language` | Accepted secondary-language research pool |
| app-specific topic sheets | Curated app/domain views |

### 1.3 No Default Loose CSV Package

Do not export many loose CSV/Markdown files by default:

```text
01_Main_Keyword_Shortlist.csv
02_Feature_Keywords.csv
03_Style_Keywords.csv
04_Dropped_Keywords_Audit.csv
05_ASO_Report.md
```

Export extra CSV/Markdown files only when the user explicitly requests them or config enables:

```text
export_csv_package = True
export_markdown_report = True
```

### 1.4 Workbook Formatting Standard

Every table sheet should have:

- frozen header row;
- filters enabled;
- readable column widths;
- wrapped text for long reason fields;
- numeric formatting for Volume, Difficulty, Rank, and scores;
- reason columns explaining the decision;
- `Section` on shortlist sheets;
- `QuotaStatus`, `FillSource`, or `FillReason` when fallback/backfill is used;
- audit columns sufficient to explain every keep/drop/research-only decision.

---

## 2. Main Shortlist Structure v4.5

`01_Main_Keyword_Shortlist` is no longer a rigid bucket-quota file or a pure `BalancedScore` ranking. It is a target-40 metadata-safe shortlist selected by utility and diversity.

```text
Main metadata shortlist = target 40 utility + diversity
Section = audit/planning annotation
```

Default conceptual sections:

```text
Core Intent Final 25
Feature Keywords  5
Broad Expansion   5
Consider Keywords 5
```

These are planning targets, not blind filler quotas. If one section lacks safe high-quality rows, the selector can backfill with other metadata-safe rows.

### 2.1 Core / High Intent Keywords

Core keywords are closest to the app's primary search intent.

Requirements:

- directly related to the app's core function;
- safe for the app category and market;
- not a competitor brand;
- not foreign to the market policy;
- not a generic style-only phrase;
- metadata suitable.

Examples for a control-widget app:

```text
control panel
control widget
custom control panel
quick settings
notification panel
quick panel
volume control widget
shortcut widget
custom quick settings
control center themes
```

### 2.2 Broad Expansion Keywords

Broad Expansion keywords are related to the category or user job, but less direct than core intent.

They are useful for semantic coverage and growth research, but they must still be plausibly relevant and metadata safe.

Acceptable examples:

```text
custom widget
color widgets
widget themes
custom themes
theme packs
cute widget
```

Weak examples that should be limited or sent to research:

```text
beauty theme
simple theme
stunning themes
themes wallpaper
diy theme pack
```

### 2.3 Consider Keywords

Consider Keywords are plausible, useful, or high-signal rows that need extra review before being promoted into core metadata.

They can include:

- platform-style terms;
- valid secondary-language terms;
- strong mixed-language rows;
- keywords with risk-sensitive wording;
- high-volume rows excluded by diversity or quality constraints;
- keywords that are relevant but not yet specific enough for metadata.

Consider is one quality-ranked review pool. It is not a place to hide bad IP/competitor/off-topic rows.

Priority order:

```text
1. RelevancyScore
2. VolumeN
3. BalancedScore
4. CurrentRankN
5. KEI
6. lower Difficulty
```

---

## 3. Pipeline Steps

| Step | Name | Input | Output | Purpose |
|---:|---|---|---|---|
| 1 | Data ingestion | raw CSV | normalized DataFrame | Read, normalize, and type-coerce data |
| 2 | Hard filter | normalized DataFrame | candidates + dropped rows | Remove hard noise, competitor brands, wrong intent, broken phrases |
| 3 | Language policy | candidates | language fields | Decide primary/secondary/mixed/foreign/unknown |
| 4 | Naturalness filter | candidates | naturalness flags | Detect keyword stuffing, broken phrases, bad truncation |
| 5 | Relevancy scoring | candidates | `RelevancyScore` | Score app relevance |
| 6 | Balanced scoring | scored candidates | `BalancedScore` | Combine demand, difficulty, rank, relevancy, expansion |
| 7 | Bucket classification | scored candidates | semantic sections | Classify Core, Feature, Broad, Consider, Reserve, Drop |
| 8 | Suitability gate | candidates | metadata/ads suitability | Decide metadata/ads eligibility and research-only status |
| 9 | Diversity selector | eligible candidates | shortlist | Build target-40 safe diverse shortlist |
| 10 | Export/report | output tables | workbook | Export workbook and audit report |

Runtime order must include the cache-only agentic and suitability prerequisites described in later sections.

---

## 4. APP_CONFIG Universal Contract

Every app should expose a full `APP_CONFIG` in `apps/<AppName>/app_config.py`.

Minimal shape:

```python
APP_CONFIG = {
    "app_id": "com.yourcompany.yourapp",
    "app_name": "Your App Name",
    "category": "Widget",
    "category_slug": "widget",
    "market": "US_EN",
    "platform_mode": "google_play",
    "semantic_mode": "general",
    "ruleset_version": "v4.5",

    "market_language_policy": {
        "enabled": True,
        "required": True,
        "primary_languages": ["en"],
        "secondary_languages": [],
        "optional_secondary_languages": [],
        "mixed_allowed": True,
        "primary_language_action": "keep",
        "secondary_language_action": "consider",
        "optional_secondary_action": "audit_or_consider",
        "foreign_language_action": "drop_to_audit",
        "unknown_language_action": "manual_review",
    },

    "intent_core_terms": [],
    "intent_core_words": [],
    "feature_terms": [],
    "style_terms": [],
    "visual_terms": [],

    "competitor_brands": [],
    "noise_terms": [],
    "typo_blacklist": [],
    "irrelevant_intent_terms": [],
    "risky_ip_terms": [],
    "risky_platform_terms": [],
    "platform_affiliation_terms": [],

    "risk_policy": {
        "competitor_brand_action": "drop",
        "risky_ip_action": "drop",
        "risky_platform_action": "consider",
        "platform_affiliation_action": "drop",
        "style_only_action": "reserve",
        "core_intent_override": True,
    },

    "keyword_quota": {
        "main_file": {
            "target_count": 40,
            "core_intent": 25,
            "feature_keywords": 5,
            "broad_expansion": 5,
            "consider": 5,
        }
    },

    "metadata_suitability": {
        "enabled": True,
        "audit_min_volume": 5,
        "fail_on_missing_audit": True,
        "single_token_policy": {
            "enabled": True,
            "default_action": "research_only",
            "keep_terms": [],
            "block_terms": [],
        },
    },

    "user_overrides": {
        "force_keep_terms": [],
        "force_drop_terms": [],
        "suitability_keep_terms": [],
    },
}
```

The template in `docs/App_Config_Template.py` is the most detailed editable reference.

---

## 5. Market Language Policy

Language detection and grouping live in `shared/language_detector.py`.

### 5.1 Mandatory Rules

- The market's primary language is the only default language for main metadata.
- Secondary language is allowed only when configured.
- Mixed language can be normal search behavior, especially local language plus English tech terms.
- Foreign language should not enter the main shortlist.
- Unknown language should go to Manual Review unless a deterministic app rule clearly resolves it.

### 5.2 Secondary Language Is Not Language Bleed

A secondary-language keyword can be legitimate in multilingual markets. It should not be treated as a bug simply because it is not the primary language.

Examples:

- Spanish terms in `US_EN` can be research/consider when configured.
- English loanwords in `ID_ID`, `BR_PT`, or `PH_FIL` can be normal app-store behavior.
- Local-language phrases with English platform terms are often `MIXED`, not `FOREIGN`.

### 5.3 Language Group Handling

| Group | Meaning | Default handling |
|---|---|---|
| `PRIMARY` | Primary market language | Normal scoring and classification |
| `SECONDARY` | Configured secondary language | Usually `Consider Keywords` |
| `MIXED` | Accepted code-switching or loanword mix | Normal bucket if market allows mixed language |
| `FOREIGN` | Outside market language policy | `Language Mismatch Audit` |
| `UNKNOWN` | Detection confidence too weak | `Manual Review` |

### 5.4 Output Language Fields

Relevant columns:

```text
DetectedLanguage
LanguageGroup
LanguageReason
AIEnglishGloss
EN
```

### 5.5 Market Language Examples

```python
"US_EN": {"primary_languages": ["en"], "secondary_languages": ["es"], "mixed_allowed": True}
"BR_PT": {"primary_languages": ["pt"], "secondary_languages": ["en"], "mixed_allowed": True}
"ID_ID": {"primary_languages": ["id"], "secondary_languages": ["en"], "mixed_allowed": True}
"VI_VI": {"primary_languages": ["vi"], "secondary_languages": ["en"], "mixed_allowed": True}
```

---

## 6. Rule Precedence

The system must apply rules in a stable order.

Recommended precedence:

```text
1. force_drop / competitor / hard risk
2. broken/truncated/naturalness hard failures
3. foreign-language hard handling
4. irrelevant intent
5. core-intent override where allowed
6. risk policy
7. secondary/mixed language handling
8. scoring and bucket classification
9. metadata/ads suitability
10. shortlist selector
11. user-facing workbook export
```

### 6.1 Rules That Cannot Be Overridden By AI

AI/subagent output cannot rescue:

- competitor brand drops;
- platform affiliation/official-brand claims;
- force-drop user overrides;
- hard irrelevant intents;
- language mismatch rows that policy sends to audit/drop;
- severe naturalness or broken phrase failures;
- deterministic metadata unsuitability.

### 6.2 Core Intent Override Does Not Rescue Competitor Brands

Core override exists to avoid over-dropping valid app-platform terms, not to allow competitor or official-brand claims.

Valid core override requires:

1. the risky/platform term is declared safe by the app vocabulary;
2. the keyword has a separate functional anchor;
3. the row is not a competitor/affiliation/force-drop row.

Generic words such as `game`, `games`, `play`, `app`, and `free` cannot rescue a risky brand term.

---

## 7. Hard Filter Rules

### 7.1 Auto Drop

Auto-drop examples:

- competitor app brands;
- exact competitor package/title terms;
- official/affiliation claims;
- unrelated app categories;
- copyrighted game/IP/franchise names when the app is an emulator or generic utility;
- adult, gambling, malware, or policy-dangerous queries;
- broken/truncated prefixes with no clear anchor;
- impossible or nonsensical phrases;
- user-configured force-drop terms.

### 7.2 Do Not Auto Drop

Do not automatically drop:

- valid secondary-language terms;
- valid mixed-language local search phrases;
- app-supported platform terms with functional anchors;
- low-volume terms solely because Volume is low;
- word-order permutations when `auto_merge_token_bag = False`;
- complete tokens that look like prefixes but are real words, such as `emoji`, `icon`, `sound`, `filter`, `widget`.

---

## 8. Core Intent Override

Core intent override is a deterministic safety valve.

It can move a risky/platform row from hard drop to consider only when the row clearly names a supported app intent and has a functional anchor.

For emulator apps:

- `nds emulator` can be valid if NDS emulation is the app's declared core.
- `psp emulator` can be valid if PSP support is declared.
- `nintendo switch` remains risky/off-scope if Switch is not supported or is an affiliation/platform claim.
- `mario`, `pokemon`, `naruto`, `metal slug`, and similar game/franchise IPs should drop unless the app is explicitly licensed for them.

---

## 9. Relevancy Scoring

`RelevancyScore` estimates how closely a keyword matches this app.

Signals:

- exact core intent terms;
- feature terms;
- style/visual terms;
- app profile metadata;
- competitor overlap signals where relevant;
- AI semantic bucket and confidence;
- language group;
- negative risk/irrelevance signals.

### 9.1 High Score Examples

High score rows:

- name the app category directly;
- include a supported core platform/function;
- match app-owned feature terms;
- use the right market language;
- avoid competitor/IP risk.

### 9.2 Medium Score Examples

Medium score rows:

- are category-adjacent;
- match style or use-case language;
- need review before metadata;
- may be better as Broad Expansion or Consider.

### 9.3 Low Score Examples

Low score rows:

- are foreign-language mismatch;
- are generic style words;
- are unrelated to the app type;
- are risky IP/competitor rows;
- are too ambiguous for acquisition.

---

## 10. Balanced Score And Normalization

Scoring source of truth is `shared/keyword_filter/scoring.py`.

### 10.1 Required Normalization

#### VolumeN

`VolumeN` uses log-reach normalization:

```text
VolumeN = log1p(reach) / log1p(reach_reference)
```

When `reach_reference = 0`, the engine computes a safe reach ceiling from non-competitor/non-irrelevant rows.

#### DifficultyN

Lower difficulty is better:

```text
DifficultyN = 1 - (Difficulty / 100)
```

Clamp to `[0, 1]`.

#### KEIN

KEIN is retained for audit but removed from the default v4.5 BalancedScore because it is collinear with Volume and Difficulty.

#### CurrentRankN

Ranking signal rewards existing traction. `Unranked` receives the lowest rank signal.

#### ExpansionValue

ExpansionValue rewards useful semantic expansion that is not redundant with core terms.

Default conceptual weights:

```text
VolumeN        0.35
DifficultyN    0.15
RelevancyScore 0.30
CurrentRankN   0.10
ExpansionValue 0.10
```

`resolve_balanced_weights()` migrates old configs that still include KEIN.

---

## 11. Bucket Classification

Primary buckets:

| Bucket | Meaning |
|---|---|
| `Core Intent Final` | Direct app/core search intent |
| `Feature Keywords` | Concrete feature, function, supported platform, or app capability |
| `System Keywords` | System-level or platform-level functional term |
| `Broad Expansion` | Related but broader category/use-case term |
| `Consider Keywords` | Potentially useful but needs review |
| `Style Keywords` | Style/theme/emotional/visual intent |
| `Generic Style Reserve` | Broad style terms kept for research only |
| `Game Keywords` | Game/content-related row for game/emulator contexts |
| `Language Mismatch Audit` | Wrong language for the market policy |
| `Manual Review` | Ambiguous row requiring human review |
| `Dropped` | Not usable for this app/run |

Bucket classification is not the final metadata decision. Suitability and selector gates still apply afterward.

---

## 12. Quota Fallback Policy

The main shortlist target is 40, but quality wins over blindly filling.

Fallback is allowed only from metadata-safe candidates that pass:

- risk/language/naturalness gates;
- metadata suitability;
- quality floor;
- demand floor;
- diversity constraints.

If safe rows are exhausted, do not fill with weak or risky rows. Record a quality warning in `15_Selector_Quality_Log`.

---

## 13. Word Overlap And Deduplication

`shared/text_dedup.py` provides Unicode `NFKC` + `casefold()` normalization and locale-aware stemming.

Main shortlist dedup:

- applies to `01_Main_Keyword_Shortlist`;
- keeps the representative with stronger utility;
- records merged variants in `MergedVariants`;
- does not force feature/style/topic sheets to dedup against the main list.

Word-order permutations are preserved when token-bag auto-merge is disabled.

---

## 14. Metadata Assignment By Platform

### 14.1 Google Play Mode

Google Play metadata planning should prioritize:

- app title / short description: strongest, safest core intent;
- full description: broader feature and style coverage;
- ads keywords: only `AdsEligible=True` rows;
- avoid competitor/IP/policy-risk rows.

### 14.2 App Store Mode

App Store mode may require:

- title/subtitle keyword planning;
- keyword field packing;
- plural/singular normalization;
- tighter character budgeting.

The current pipeline primarily targets Google Play, but the platform-mode contract should not assume Google Play forever.

### 14.3 Example For Control Widget

Good Google Play metadata candidates:

```text
control panel
quick settings
notification panel
control center themes
volume control widget
```

Weak or research-only candidates:

```text
simple theme
beauty theme
ios official control center
```

---

## 15. Feature / Type Sheet

`02_Feature_Keywords` groups concrete features and supported app capabilities.

Examples:

- controller mapping;
- save state;
- fast forward;
- notification panel customization;
- control widget;
- face filter;
- prank sound mode.

Feature rows still need risk and suitability review before use in metadata.

---

## 16. Style Sheet

`03_Style_Keywords` groups style/theme/visual/emotional terms.

Examples:

- retro;
- cute;
- realistic;
- funny;
- aesthetic;
- nostalgic;
- prank.

Style-only keywords should not dominate the main shortlist. Broad style words often belong in `Generic Style Reserve`.

---

## 17. User Override Layer

User overrides should be explicit and limited.

Common override groups:

```python
"user_overrides": {
    "force_keep_terms": [],
    "force_drop_terms": [],
    "suitability_keep_terms": [],
}
```

Rules:

- `force_drop_terms` wins over normal scoring.
- `force_keep_terms` can keep a row for audit, but cannot rescue severe policy/risk blocks unless code explicitly allows it.
- `suitability_keep_terms` approves exact phrases for metadata suitability after deterministic risk/language gates pass.

---

## 18. Control Widget APP_CONFIG Example

Illustrative vocabulary:

```python
"intent_core_terms": [
    "control widget",
    "control panel",
    "quick settings",
    "notification panel",
    "control center",
],
"feature_terms": [
    "volume control",
    "brightness control",
    "wifi toggle",
    "bluetooth toggle",
    "flashlight shortcut",
    "screen recorder",
],
"style_terms": [
    "cute",
    "aesthetic",
    "transparent",
    "colorful",
],
"competitor_brands": [],
"platform_affiliation_terms": [
    "official ios",
    "apple control center",
],
```

This section is illustrative. App-specific configs should live in each app folder and follow `docs/App_Config_Template.py`.

---

## 19. Prompt / Run Contract

Normal execution should use the central orchestrator:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName>
```

Interactive mode:

```powershell
python run_aso_filter.py --csv "apps/<AppName>/Input/<MMYYYY>/<file>.csv" --app <AppName> --interactive
```

App runners are cache-only. Do not call a runner directly on a fresh CSV unless cache has been verified.

### APP_CONFIG

Before running, confirm:

- app exists in `shared/app_registry.py`;
- `app_config.py` exposes `APP_CONFIG`;
- `App_Profile.json` exists or generated profile status is acceptable;
- market can be inferred or is provided explicitly.

### Required Execution Order

```text
resolve app/market/csv
-> profile/config preflight
-> verify agentic cache
-> warm agentic cache if needed
-> run pipeline
-> warm suitability cache if exported candidate pool reports misses
-> rerun pipeline
-> review workbook
```

### Chat Preview

When reporting to the user, include:

- app and market;
- raw keyword count;
- clean candidate count;
- main shortlist count;
- output workbook path;
- any cache or suitability misses handled.

---

## 20. Required Report

### 20.1 Summary

Include:

- app name;
- market;
- input file;
- output workbook;
- raw keyword count;
- candidate count;
- shortlist count.

### 20.2 Language Summary

Include counts by:

```text
PRIMARY
SECONDARY
MIXED
FOREIGN
UNKNOWN
```

### 20.3 Naturalness Summary

Summarize:

- broken/truncated rows;
- suspicious keyword stuffing;
- weird phrase patterns;
- manual-review language.

### 20.4 Rule Precedence Summary

Summarize major hard drops:

- competitor;
- IP/franchise;
- language mismatch;
- irrelevant intent;
- naturalness;
- force-drop.

### 20.5 Top Decisions

Highlight:

- top selected rows;
- high-volume rows not selected;
- research-only rows that look tempting;
- rows blocked by suitability.

### 20.7 Quota Fallback Review

If target rows were not filled, explain:

- which quality gates exhausted the safe pool;
- whether cluster cap blocked rows;
- whether suitability cache is pending;
- whether demand floor filtered weak rows.

### 20.8 Workbook Sheet Index

The workbook should include a sheet index or README so users can navigate it without external docs.

---

## 21. Troubleshooting

### Problem: Main shortlist has too many broad style keywords

Fix:

- reduce style-only eligibility;
- increase style reserve behavior;
- inspect `Generic Style Reserve`;
- tune style terms and quality floors.

### Problem: iOS / iPhone keywords are all dropped

Fix:

- separate platform-style terms from affiliation terms;
- keep official/affiliation claims hard-dropped;
- allow safe platform-style phrases only when the app truly supports that visual/use case.

### Problem: Secondary-language keywords are flagged as language bleed

Fix:

- update `market_language_policy.secondary_languages`;
- allow mixed language where local behavior supports it;
- verify `LanguageGroup` in `06_All_Candidates`.

### Problem: Foreign language enters main output

Fix:

- check market policy;
- ensure `FOREIGN` maps to `Language Mismatch Audit`;
- verify shortlist selector respects language gates.

### Problem: Feature / Style sheets are too long

Fix:

- cap sheet sizes;
- dedup per sheet;
- prioritize utility and relevance.

### Problem: Core keyword is removed by word overlap

Fix:

- inspect `MergedVariants`;
- adjust dedup token rules;
- check whether the removed row has lower utility than the retained representative.

### Problem: Not enough quota rows

Fix:

- inspect `15_Selector_Quality_Log`;
- inspect `14_Not_Selected_Audit`;
- verify demand floors and suitability cache;
- do not fill with unsafe rows just to hit count.

---

## 22. Short Rules To Remember

1. Score is not enough.
2. Risk gates win.
3. Language policy matters.
4. Suitability decides metadata/ads usability.
5. Main shortlist must be metadata-safe.
6. Broad or feature-related does not automatically mean ad-eligible.
7. Cache-only runtime prevents hidden AI calls.
8. Workbook audit columns must explain every important decision.

---

## 23. Content Added In v3.2

### P0 - Mandatory Additions

- Single workbook as the default output.
- Required audit sheets.
- Explicit language policy.
- Rule precedence.
- Main shortlist sectioning.

### P2 - Default Output Change

The default changed from many loose files to a single workbook.

### P1 - Important Additions

- Better quota fallback.
- Better report summary.
- Stronger workbook audit columns.

---

## 24. v3.3 Update - Global Text-Level Dedup

### 24.1 Reason

Earlier runs could output near-duplicate rows across the main shortlist and topic sheets.

### 24.2 Scope

Dedup applies most strictly to the main shortlist. Other sheets can preserve useful variants for research.

### 24.3 Text-Level Dedup Rules

Use normalized text, stemming, stopword handling, and configurable token-bag behavior.

### 24.5 Required Dedup Log

Dedup decisions should be auditable through:

```text
MergedVariants
DedupReason
RepresentativeKeyword
```

### 24.6 Quota After Dedup

#### Sheet 01 - Main Keyword Shortlist

Selector can backfill after dedup, but only with safe rows.

#### Sheet 02, Sheet 03, And Topic Sheets

Feature/style/topic sheets can keep variants that are useful for research, even when the main shortlist dedups them.

---

## 25. v3.5 Update - Universal Pipeline Updates

### 25.1 Nonlinear Search Popularity

Search popularity should use log or percentile normalization to avoid one outlier dominating the score.

### 25.2 Hybrid Language Detection Heuristic

Language detection must account for code-switching, local slang, brand/tech loanwords, and market-specific spelling.

### 25.3 Generic Relevancy Tightening

Generic keywords require stronger anchors before entering metadata.

### 25.4 Tie-Breaker Sorting Logic

When scores are close, prefer:

```text
higher RelevancyScore
higher VolumeN
higher BalancedScore
better rank signal
higher KEI
lower Difficulty
```

---

## 26. v3.5 Update - Shared Language And Keyword Filter Logic

### 26.1 Shared Modules

Shared logic belongs under:

```text
shared/language_detector.py
shared/keyword_filter/
shared/text_dedup.py
```

### 26.2 Language Bucket Policy

Language bucket policy is centralized and should not be reimplemented per app.

### 26.3 Naturalness v3.5

Naturalness detects:

- broken prefixes;
- stuffing;
- unnatural phrase order;
- repeated tokens;
- dangling modifiers.

### 26.4 Noise, Irrelevant, And Scoring

Noise and irrelevant terms should be filtered before scoring wherever possible.

### 26.5 Selection Cache

Selection metadata should be auditable and reproducible.

### 26.6 Related Tests

Regression tests should cover language grouping, hard filters, dedup, scoring, and selector behavior.

---

## 27. v3.6 History - Multilingual Text Dedup

Multilingual dedup added:

- Unicode normalization;
- locale-aware stemming;
- diacritic-aware comparisons;
- market-specific token handling;
- preservation of meaningful local variants.

---

## 28. v4.0 Update - Platform And Scale Hardening

### 28.1 Shared Hard-Filter Package

Hard filters moved into shared modules so app runners do not drift.

### 28.2 Hard-Filter Policy

Hard-filter policy must be deterministic and auditable.

### 28.3 App-Specific Config And Registry

Apps must be resolved through `shared/app_registry.py`, not guessed from folder names.

### 28.4 Scoped Cache And Locale Parser

Cache context is scoped by app, market, config, profile, and ruleset where appropriate.

Filename parsing supports app prefix plus locale suffix.

### 28.5 Indexed Near-Duplicate Clustering

Dedup should scale to larger keyword sets using indexed comparisons rather than brute force where possible.

### 28.6 Shared EN Gloss Resolver

`shared/en_gloss_resolver.py` resolves English gloss from CSV or cache. It does not call translation providers at runtime.

### 28.7 Shared Profile Service

`shared/profile_service.py` handles:

- custom `App_Profile.json`;
- generated profile cache;
- stale fallback;
- empty fetch failure.

### 28.8 Batch Runner

Batch runner source of truth:

```text
tools/run_aso_batch.py
```

### 28.9 Downstream And Workbook Audit

Downstream consumers should use workbook audit columns instead of reverse-engineering decisions.

### 28.10 v4.0 Tests

Tests should cover registry, locale parsing, cache scoping, profile fallback, and shared runner contracts.

---

## 29. v4.1 Update - Low-Volume Keywords, Preserved Permutations, Swapped Locale Logic

### 29.1 Accept Low-Volume Keywords

Low Volume (`Volume <= 5`) is not an automatic drop. Low-volume rows can still be useful when strongly relevant.

### 29.2 Preserve Word-Order Permutations

When `auto_merge_token_bag = False`, word-order variants remain separate:

```text
game emulator
emulator game
```

### 29.3 Swapped Locale Parser Logic

Locale parser should handle country/language order mistakes where possible and fail clearly when ambiguous.

### 29.4 App Config Updates

Apps should expose enough market policy and semantic vocabulary for shared modules to work consistently.

### 29.5 System-Wide Truncation Hardening

Complete tokens must not be dropped as broken prefixes. Examples:

```text
emoji
icon
sound
filter
widget
```

---

## 30. Deprecated API Classifier Sections Removed

Old runtime API classifier sections are no longer active. The active design is cache-only:

```text
find-misses -> prepare-batches -> subagents -> save-results -> verify-cache -> run pipeline
```

---

## 32. v4.3 Update - Consider Keywords By Quality

Consider Keywords are quality-ranked, not quota-stuffed.

Weak rows should not enter Consider just to fill a bucket. Strong but review-needed rows should be preserved with clear reasons.

---

## 33. v4.5 Update - Main Feature Quota, Top Volume, And FunVid

### 33.1 New Main Shortlist Quota

Target remains 40, with conceptual distribution across Core, Feature, Broad, and Consider.

### 33.2 WhereToUse And Dedup

Rows may include `WhereToUse` guidance for metadata planning, but the selector must remain driven by safety, utility, and diversity.

### 33.3 Sheet `13_Top_By_Volume`

This sheet highlights clean high-volume rows so reviewers can catch missed opportunities.

### 33.4 App FunVid

FunVid introduced stronger handling for face-filter, animal-face, and prank/video terminology across markets.

### 33.5 Seed CSV Tools For FunVid

Seed generation tools should produce normalized CSVs suitable for the same shared pipeline.

### 33.6 Internal Keyword Research Skill

Keyword research should be documented and stored per app under `Research/`, while runtime filtering remains shared.

### 33.7 v4.5 Tests

Tests should cover shortlist selector, top volume sheet, app-specific seed behavior, and workbook outputs.

---

## 34. v4.5 Update - Project-Wide Agentic Cache And Scoring Sync

### 34.1 Runner And Provider

Runners are cache-only. Subagents or external AI providers operate only in cache-warming workflows.

### 34.2 Agentic Cache Sequence

```powershell
python tools/warm_cache_helper.py find-misses --app <alias> --csv <input-csv> --market <MARKET>
python tools/warm_cache_helper.py prepare-batches --misses <misses-json> --output-dir .cache/agentic_batches
python tools/warm_cache_helper.py save-results --app <alias> --batch <batch-path> --results <result-path> --market <MARKET>
python tools/warm_cache_helper.py verify-cache --app <alias> --csv <input-csv> --market <MARKET>
```

Only run the pipeline after `verify-cache` prints:

```text
PASS <MARKET>: 0 missing
```

### 34.3 Shared Main Shortlist Selector

`shared/keyword_filter/shortlist.py` is the source of truth for main shortlist selection.

### 34.5 Volume Scoring

Use log reach and safe reach ceiling to avoid outlier suppression.

### 34.6 Risk Gate Before AI/Subagent Bucket

Hard deterministic risk is applied before trusting AI semantic bucket.

### 34.7 Regression Tests

Focused command:

```powershell
python -m unittest tests.test_metadata_suitability tests.test_main_shortlist_builder tests.test_suitability_cache_helper tests.test_pipeline_shared_contract
```

---

## 35. v4.5 Update - Shared Metadata Keyword Selector

The selector must:

- require metadata eligibility;
- apply language/risk/naturalness gates;
- apply quality and demand floors;
- use utility score;
- enforce diversity;
- record not-selected reasons;
- write quality warnings when safe pool is exhausted.

Important not-selected reasons:

```text
SINGLE_TOKEN_TOO_BROAD
SUITABILITY_RESEARCH_ONLY
SUITABILITY_PENDING_AUDIT
BELOW_DEMAND_FLOOR
CLUSTER_CAP_REACHED
SAFE_POOL_EXHAUSTED
```

---

## 36. v4.5 Update - Real Selector Diversity, Reach Normalization, Risk Core Override

### 36.1 Safe Backfill No Longer Skips Demand Filters

Backfill must pass the same quality, relevance, and demand filters as exact selection.

### 36.2 Reach Ceiling Against Outliers - `safe_reach_ceiling`

`safe_reach_ceiling(df, config)` ignores competitor/irrelevant rows and uses a high percentile instead of absolute max.

This prevents one huge competitor row from flattening all valid candidates' volume signal.

### 36.3 Relevancy Stacking Dampener - `dampen_stacked_relevancy`

`dampen_stacked_relevancy(row, config)` caps low-demand keyword-stuffed phrases that match several intent groups but do not have real demand.

Apply after relevancy is calculated and before BalancedScore:

```python
df["RelevancyScore"] = df.apply(lambda r: _shared_keyword_filter.dampen_stacked_relevancy(r, config), axis=1)
df["RelevancyScore"] = df["RelevancyScore"].clip(0.0, 1.0)
```

### 36.4 Real Semantic Cluster Diversity

Cluster diversity uses Jaccard similarity over meaningful tokens instead of exact token-bag keys.

Generic tokens that appear in too much of the candidate pool are ignored before similarity comparison.

Default:

```text
cluster_cap = 3
cluster_similarity_threshold = 0.5
cluster_generic_token_ratio = 0.30
```

### 36.5 Sheet `15_Selector_Quality_Log`

`15_Selector_Quality_Log` records selector warnings, especially when the safe pool is exhausted.

### 36.6 Risk Core-Intent Override - Declared-Safe Term + Functional Anchor

Core override for risky/platform terms requires:

1. risky/platform term appears in declared-safe app vocabulary;
2. row has a functional anchor;
3. row is not affiliation/official/competitor/force-drop.

### 36.7 Config Example: `risky_ip_terms` vs `risky_platform_terms`

Use `risky_ip_terms` for creative/game/franchise IP:

```text
Mario
Pokemon
Zelda
Sonic
Mortal Kombat
Naruto
Resident Evil
Metal Slug
```

Use `risky_platform_terms` for platform/manufacturer/system terms:

```text
Nintendo
Sony
Sega
PlayStation
Xbox
PSP
NDS
GBA
```

Use `platform_affiliation_terms` for official/claim phrases:

```text
official nintendo
my nintendo
nintendo switch
apple control center
```

### 36.8 AI-Recognized Classic IP - `ai_classic_ip`

AI decision rules such as these are treated as IP risk:

```text
classic_ip_intent
ip_intent
franchise_intent
ai_classic_ip
```

This catches game/franchise names not present in manual lists.

### 36.9 Agentic Cache Invalidation - `ruleset_version`

`ruleset_version` is part of the agentic context hash.

Bump it only when the agentic prompt/rubric changes and old semantic rows should be reclassified.

Changing deterministic risk/brand lists does not require agentic re-warm.

### 36.10 Regression Tests

```powershell
python -m unittest tests.test_main_shortlist_builder tests.test_pipeline_shared_contract tests.test_volume_score tests.test_relevancy_stacking tests.test_keyword_filter -v
```

---

## 37. v4.5 Update - Post-Candidate Metadata/Ads Suitability Gate

This is the current contract for keywords that are related to the app but too broad, weak, or acquisition-poor for metadata or ads.

Source of truth:

```text
shared/keyword_filter/suitability.py
tools/suitability_cache_helper.py
shared/keyword_filter/shortlist.py
.agents/skills/warm-suitability-cache/SKILL.md
```

Runner must call suitability after candidate classification/scoring and before main shortlist selection:

```python
df = _shared_keyword_filter.apply_metadata_suitability(df, config, app_profile=app_profile, market=config["market"])
shortlist_result = _shared_keyword_filter.build_main_keyword_shortlist(df, config)
```

The suitability gate answers two acquisition questions:

1. If a user searches this exact keyword on Google Play, is it likely to surface the right type of app?
2. If the store or an ad surfaces this app for that query, is the phrase specific enough to plausibly convert for this app?

Both questions matter.

Examples:

- `stik bluetooth` can be a real emulator feature, but weak Play Store acquisition intent by itself.
- `setting tombol gamepad` can describe a real feature, but may not surface the app for search/ads.
- `gba retro games` or `game boy advance` can be broad, but may still surface the right emulator category and deserve audit rather than automatic feature eligibility.
- `drop 4`, `fs advanced`, `and pies`, `mma manager`, and `yoto player` are wrong app type or off-core queries and should be research-only/dropped from metadata.

### 37.1 Output Columns

Suitability adds:

```text
MetadataEligible
AdsEligible
ResearchOnly
SuitabilityBucket
SuitabilityRule
SuitabilityReason
SuitabilityConfidence
SuitabilitySource
```

`01_Main_Keyword_Shortlist` may select only rows with:

```text
MetadataEligible=True
```

Ads v1 does not create a separate sheet by default. `AdsEligible` is an audit/export column for future ads workflows.

### 37.2 Config

Current config shape:

```python
"metadata_suitability": {
    "enabled": True,
    "audit_min_volume": 5,
    "fail_on_missing_audit": True,
    "single_token_policy": {
        "enabled": True,
        "default_action": "research_only",
        "keep_terms": ["nds", "ds", "gba"],
        "block_terms": ["arcade", "pizza", "moonlight", "turbospeed"],
    },
}
```

Meaning:

- `keep_terms`: atomic app/platform terms that still have clear intent as one-token queries.
- `block_terms`: one-token feature/style/category terms that are too broad.
- `audit_min_volume`: minimum Volume for multi-word suitability audit. Current default is `5`.
- `fail_on_missing_audit`: fail fast and export candidate pool when audit is required but cache is missing.
- `user_overrides.suitability_keep_terms`: exact app-owner-approved phrase overrides after deterministic gates pass.

### 37.3 Deterministic Precedence

Final suitability decision follows deterministic precedence:

1. Risk/drop/language/manual-review/naturalness/hard-filter gates always return `MetadataEligible=False`, `AdsEligible=False`, `ResearchOnly=True`.
2. Single-token keep terms are eligible.
3. Single-token block terms are research-only with rule `single_token_too_broad`.
4. Exact phrases in `metadata_suitability.keep_terms` or `user_overrides.suitability_keep_terms` are eligible after deterministic gates pass.
5. Cached subagent suitability is used only for ambiguous/audited cases and cannot rescue deterministic blocks.
6. Unlisted single tokens default to research-only if `default_action="research_only"` and no cached audit exists.
7. Hand-declared feature/core terms usually skip subagent suitability audit when they land deterministically in `Feature Keywords`, `System Keywords`, or `Core Intent Final`.
8. Multi-word keywords need audit when they are in `Feature Keywords`, `System Keywords`, `Broad Expansion`, `Consider Keywords`, `Style Keywords`, `Generic Style Reserve`, or `Game Keywords`, meet `audit_min_volume`, and are AI-inferred or in a non-feature/core bucket.
9. Audited keywords without cache become `suitability_pending_audit`; `apply_metadata_suitability` raises `SuitabilityAuditError` and exports a candidate pool CSV.

### 37.4 Subagent Suitability Audit

Use the candidate pool exported after classification/scoring, not the raw AppTweak CSV:

```powershell
python tools/suitability_cache_helper.py find-misses --app <alias> --csv <candidate-pool-csv> --market <MARKET>
python tools/suitability_cache_helper.py prepare-batches --misses <misses-json> --output-dir .cache/suitability_batches
python tools/suitability_cache_helper.py save-results --app <alias> --batch <batch-path> --results <result-path> --market <MARKET>
python tools/suitability_cache_helper.py verify-cache --app <alias> --csv <candidate-pool-csv> --market <MARKET>
```

If the pipeline hits missing suitability audit, it exports a ready-to-use pool:

```text
.cache/candidate_pools/<app_id>_<MARKET>_candidates.csv
```

SQLite uses the same file as agentic cache, but a separate table:

```text
.cache/agentic_keyword_analysis.sqlite3
keyword_suitability_analysis
```

Subagent result schema:

```json
{
  "batch_id": "market_suitability_batch_1",
  "items": [
    {
      "keyword": "example keyword",
      "metadata_eligible": false,
      "ads_eligible": false,
      "research_only": true,
      "suitability_bucket": "Research Only",
      "decision_rule": "ai_broad_head_term",
      "reason": "Broad category query with weak app-specific acquisition intent.",
      "confidence": 0.85
    }
  ]
}
```

`save-results` rejects:

- missing keywords;
- duplicate keywords;
- keywords outside the batch;
- invalid booleans;
- invalid confidence;
- context hash mismatch.

### 37.5 Regression Tests

```powershell
python -m unittest tests.test_metadata_suitability tests.test_suitability_cache_helper tests.test_main_shortlist_builder tests.test_pipeline_shared_contract -v
```

---

## 38. Project Memory

`shared/project_memory.py` reads `app_config.py` and `App_Profile.json` and renders:

- dashboard Setup tab;
- workbook sheet `00_Project_Memory`;
- app file `PROJECT_MEMORY.md`.

Project Memory is read-only documentation generated from source-of-truth files. Edit `app_config.py` or `App_Profile.json`, not generated memory, when changing app identity or policy.

---

## 39. Batch Runner

Manifest example:

```json
{
  "jobs": [
    {"app": "Pranky", "csv": "path/to/Pranky_US_EN.csv"},
    {"app": "ARFilter", "csv": "path/to/ARFilter_BR_PT.csv"}
  ]
}
```

Command:

```powershell
python run_aso_batch.py --manifest path\to\manifest.json
```

Batch mode is also cache-only. Jobs with cache misses must fail fast, then be warmed and rerun.

---

## 40. Definition Of Done For A Pipeline Run

A run is complete only when:

- app and market are resolved through registry/locale parser;
- profile/config preflight has been reviewed;
- agentic cache verifies `PASS <MARKET>: 0 missing`;
- pipeline runs without missing gloss/classification;
- suitability cache verifies when candidate pool requires it;
- workbook is generated under the app output folder;
- main shortlist contains only metadata-eligible rows;
- audit sheets explain dropped, research-only, and not-selected rows.

---

## 41. Full Regression Command

Run all tests:

```powershell
python -m unittest discover -s tests -v
```

Focused v4.5 command:

```powershell
python -m unittest tests.test_metadata_suitability tests.test_main_shortlist_builder tests.test_suitability_cache_helper tests.test_pipeline_shared_contract
```

Important test areas:

- agentic cache hit/miss;
- English gloss fail-fast;
- volume scoring;
- relevancy stacking dampener;
- risk core override;
- language grouping;
- suitability audit;
- shortlist selector;
- workbook output contract;
- batch runner behavior.

---

## 42. Migration Notes

- If deterministic risk/brand lists change, rerun the pipeline; AI cache re-warm is not required.
- If agentic prompt/rubric changes, bump `ruleset_version` and re-warm markets.
- If suitability policy or context changes, warm suitability cache for affected candidate pools.
- If target count cannot be filled safely, inspect `15_Selector_Quality_Log` and do not lower gates blindly.
- Keep this file as the complete planner spec; use `docs/USAGE.md` for operator quick-start.
