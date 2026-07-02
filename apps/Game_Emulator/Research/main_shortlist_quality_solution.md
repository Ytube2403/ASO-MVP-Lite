# Game Emulator Main Shortlist Quality Solution

Date: 2026-07-01
App: Game Emulator: GB4 Retro Games
Target: Improve `01_Main_Keyword_Shortlist` so it favors strong demand and high relevance keywords.

## Current Diagnosis

The current Game Emulator output is letting too many weak or risky terms into the main shortlist because `Core Intent Final` is too permissive and quota filling is prioritized over quality.

Latest workbook review under `apps/Game_Emulator/Output/072026/`:

| Market | Main Rows | Sections | Weak Rows* | Notes |
|---|---:|---|---:|---|
| US_EN | 30 | 25 Core, 5 Feature, 5 Broad | 18 | Missing Feature and Consider quotas; weak Core terms include `naruto emulator`, `gamer boy emulator`, `ideas emulator`, `sboy`, `manic emu`. |
| MX_ES | 40 | 25 Core, 5 Feature, 5 Broad, 5 Consider | 25 | IP/platform terms appear in main review area, e.g. `pokemon`, `mario bros`, `super mario`. |
| ID_ID | 40 | 25 Core, 5 Feature, 5 Broad, 5 Consider | 24 | Weak Core terms include `emulator pc`, `nes games all in one offline`, `psp emulator for android`. |
| IN_HI | 40 | 25 Core, 5 Feature, 5 Broad, 5 Consider | 30 | Many slang/broad game terms with low relevance enter Core. |
| BR_PT | 40 | 25 Core, 5 Feature, 5 Broad, 5 Consider | 16 | Consider area includes several compliance/IP/platform terms. |

*Weak row heuristic used for audit: `Volume <= 10` OR `BalancedScore < 0.40` OR `RelevancyScore < 0.50`.

Key implementation findings:

- `apps/Game_Emulator/run_game_emulator_v4_4.py` still selects `25` Core keywords, then `5` Broad keywords. It does not fully implement the current v4.5 quota contract of `25 Core + 5 Feature + 5 Broad + 5 Consider`.
- The current classifier treats any keyword matching broad core terms as `Core Intent Final`. This allows low-quality terms containing only `emulator` or a loose emulator-like phrase to occupy metadata slots.
- `volume_score_policy.exclude_low_tier_from_metadata_shortlist=True` only blocks `Volume <= 5`. It does not protect the main list from weak `Volume 7-14` keywords.
- Risk handling is not strict enough for the main list. Terms containing IP, console/platform brands, competitor names, ROM/download/BIOS intent, or unsupported platforms should be audit/research candidates, not metadata candidates.
- `13_Top_By_Volume` is required by the spec but missing in the latest US_EN workbook.

## Recommended Solution

Introduce a strict `MainMetadataEligibility` gate before quota selection. Do not let every bucket candidate compete for main-list slots. A keyword must pass all gates below before it can enter `Core`, `Feature`, `Broad`, or main-sheet `Consider` sections.

### 1. Hard Risk Gate

Exclude from metadata shortlist:

- Competitor brands: `sboy`, `ideas emulator`, `gamer boy`, `manic emu`, `ppsspp`, `citra`, `dolphin`, `retroarch`, etc.
- Registered console/platform or affiliation-only terms unless the phrase is generic and non-misleading.
- Game IP/franchise terms: `pokemon`, `mario`, `naruto`, `zelda`, etc.
- Unsupported platform terms: PS1, PS2, PS3, PS4, PS5, 3DS, Wii, Switch, GameCube.
- ROM/download/BIOS/ISO intent unless explicitly marked as legal/import-your-own and placed in audit, not metadata.

These can remain in research/audit sheets for blacklist mapping, but should not enter `01_Main_Keyword_Shortlist`.

### 2. Strong Intent Shape Gate

For `Core Intent Final`, require one of these shapes:

- Exact approved core phrase: `game emulator`, `retro game emulator`, `classic game emulator`, `gba emulator`, `gameboy emulator`, `arcade emulator`.
- Compound intent: an emulator term plus a relevant generic modifier, such as `retro`, `classic`, `game`, `console`, `android`, `offline`, `all in one`, `handheld`.
- Local-market equivalent with verified semantic intent, such as `emulador de jogos retro` or strong Hinglish/Indonesian emulator phrasing.

Reject as Core:

- Single loose terms: `emulator`, `emu`, `console`, `game`, `retro`.
- Competitor-like names plus emulator: `ideas emulator`, `gamer boy emulator`, `manic emu`.
- IP plus emulator: `naruto emulator`, `pokemon gba emulator`.
- Broad game nostalgia terms without emulator intent: `dabba game`, `tv wala video game`, `coin wala game`.

### 3. Demand Gate

Define `DemandQualified=True` when at least one is true:

- `Volume >= market_volume_p60` among non-dropped candidates.
- `MaximumReach >= market_reach_p60` among non-dropped candidates.
- `VolumeN >= 0.12` and `RelevancyScore >= 0.75`.
- Keyword is an exact approved core phrase with `RelevancyScore >= 0.85` and `Volume >= market_volume_p40`.

This avoids a brittle global threshold. For Game Emulator, each market has a different volume distribution, and some strong generic terms have modest AppTweak Volume but strong reach.

### 4. Relevance And Score Floors

Use hard floors before quota filling:

| Section | Minimum Relevancy | Minimum BalancedScore | Demand Requirement |
|---|---:|---:|---|
| Core Intent Final | 0.65 | 0.45 | Required |
| Feature Keywords | 0.60 | 0.42 | Required |
| Broad Expansion | 0.55 | 0.42 | Required |
| Consider Keywords in main workbook | 0.60 | 0.40 | Required unless explicitly audit-only |

If a market cannot fill quota after these gates, under-fill the section and report `QuotaStatus=UNDER_FILLED_QUALITY_GATED`. Do not backfill with weak keywords.

### 5. Separate Metadata From Audit

Prefer this workbook structure:

- `01_Main_Keyword_Shortlist`: only metadata-safe keywords, `25 Core + 5 Feature + 5 Broad + 5 Consider`.
- `01b_Consider_Keywords`: review-only candidates, including borderline language, market-specific slang, and lower-confidence long-tail terms.
- `13_Top_By_Volume`: top clean non-dropped volume opportunities for manual rescue.
- Existing audit sheets: keep dropped, language mismatch, IP, competitor, platform, and compliance-risk terms.

The last 5 rows remain `Consider / Research Only`, but should still pass risk, relevance, score, and demand gates.

## Proposed Ranking Formula

Keep `BalancedScore` for general audit, but add a separate `MetadataPriorityScore` for main-list selection:

```text
MetadataPriorityScore =
  0.40 * RelevancyScore
+ 0.30 * DemandScore
+ 0.15 * RankOpportunityScore
+ 0.10 * KEIN
+ 0.05 * ExpansionValue
```

Where:

```text
DemandScore = max(VolumeN, percentile_normalized(MaximumReach), percentile_normalized(Volume))
```

Important: this score is applied only after the hard eligibility gates. It should not rescue competitor/IP/platform/compliance-risk keywords.

## Example Outcomes

Should stay or compete for Core:

- `retro games emulator`
- `game emulator`
- `classic game emulator`
- `gba emulator`
- `gba game emulator`
- `game boy advance gba emulator`
- `video game emulator`

Should move out of main metadata:

- `naruto emulator` -> IP/franchise risk.
- `ideas emulator` -> competitor/brand-like risk.
- `gamer boy emulator` -> competitor/brand-like risk.
- `sboy` -> competitor/brand-like risk.
- `manic emu` -> competitor/brand-like risk.
- `retro bowl` -> specific game intent, not emulator metadata.
- `xbox game pass` -> platform/subscription intent, not app functionality.
- `dabba game`, `tv wala video game`, `coin wala game` -> local research/slang only unless paired with emulator intent and demand.

## Implementation Checklist

1. Add a shared `MainKeywordShortlistBuilder` under `shared/keyword_filter/shortlist.py`.
2. Set the shared default quota to `25 Core + 5 Feature + 5 Broad + 5 Consider`.
3. Add `keyword_quota.main_file` to `apps/Game_Emulator/app_config.py` with `25/5/5/5`.
4. Add `metadata_quality_gate` config with section-specific floors for relevance, balanced score, and demand.
5. Compute market percentiles after hard filtering and before shortlist selection.
6. Update app runners to call the shared builder instead of carrying local copy-pasted `build_shortlist()` implementations.
7. Add a dedicated Feature quota from `System Keywords` for Game Emulator, but only for supported/generic systems and app features.
8. Move IP/platform/competitor/compliance-risk terms out of main metadata and into audit/research sheets.
9. Restore required sheet `13_Top_By_Volume`.
10. Add regression tests that assert quota behavior and known bad terms do not enter main metadata.

## Source Notes

- Local workbook audit: `apps/Game_Emulator/Output/072026/Game_Emulator_US-EN_Output.xlsx`, `MX-ES`, `ID-ID`, `IN-HI`, `BR-PT`, accessed 2026-07-01.
- Local runner: `apps/Game_Emulator/run_game_emulator_v4_4.py`, accessed 2026-07-01.
- Local config: `apps/Game_Emulator/app_config.py`, accessed 2026-07-01.
- Local spec: `docs/ASO_Keyword_Planner_v4_5.md`, accessed 2026-07-01.
- Google Play store listing best practices: store listings should accurately describe app functionality, avoid misleading references to other apps/products, and avoid repetitive/irrelevant keyword blocks. Source: https://support.google.com/googleplay/android-developer/answer/13393723?hl=en, accessed 2026-07-01.
- AppTweak ASO keyword research guidance: prioritize keywords by relevance, search volume, and competition; high volume alone is not sufficient. Source: https://www.apptweak.com/en/aso-blog/best-aso-keyword-research-tools, accessed 2026-07-01.
- AppTweak long-tail guidance: lower-volume long-tail terms can be valuable when highly relevant, but lists should be organized by relevance, search volume, and ranking difficulty. Source: https://www.apptweak.com/en/aso-blog/how-to-improve-aso-with-long-tail-keywords, accessed 2026-07-01.
- Apple Ads keyword guidance: start from terms users would use to find an app like yours and terms explaining the service or need met. Source: https://ads.apple.com/app-store/best-practices/keywords, accessed 2026-07-01.


