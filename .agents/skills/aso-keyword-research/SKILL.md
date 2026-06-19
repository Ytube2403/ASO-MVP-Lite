---
name: aso-keyword-research
description: Expand and build ASO seed keyword sets for a registered app in this workspace using app config/profile, competitor analysis, local search behavior, and web research. Use when the user asks in Vietnamese or English to research, expand, collect, or build keywords for an app, including prompts like "Nghien cuu tu khoa <AppName>", "Nghiên cứu từ khóa <AppName>", "Research keywords <AppName>", or market-specific requests such as BR_PT keyword research for FunVid.
---

# ASO Keyword Research

Use this skill to collect seed keywords for an app before running the ASO filtering pipeline. The goal is breadth and relevance: collect many plausible seed keywords, grouped by intent, without scoring Volume, Difficulty, KEI, or metadata placement.

## Inputs

Resolve the app from the user's app name or alias. Prefer the workspace registry when available, then read:

- `apps/<AppName>/app_config.py`
- `apps/<AppName>/App_Profile.json`
- Existing input CSVs under `apps/<AppName>/Input/` when they help avoid duplicates
- Existing research notes under `apps/<AppName>/Research/` if present

Extract:

- App identity, market, category, platform, and semantic mode
- Actual app positioning, feature claims, differentiators, and exclusions
- `intent_core_terms`, `feature_terms`, `style_terms`, `visual_terms`
- Competitor brands, suggested competitors, risky IP/platform terms, and irrelevant intents

If the target market is explicit in the user request, use it. If it is ambiguous, infer from `app_config.py`; ask only when the requested market conflicts with the config and the intended market cannot be inferred safely.

## Research Rules

- Stay faithful to actual app features. Do not invent unsupported features.
- For non-US markets, do original local-market research. Do not simply translate US_EN keywords.
- Use available web/search tools for current competitor pages, Google Play/App Store phrasing, trends, autocomplete-style phrases, and local slang.
- Avoid competitor brands in the final seed list unless the phrase is a safe generic concept.
- Remove obvious noise such as `app`, `free`, `download`, and unrelated categories unless they are part of a meaningful long-tail query.
- Include diacritic and no-diacritic variants when local users commonly type both.
- Include bilingual or mixed-language queries when they are natural for the target market.
- Keep keyword research separate from filtering. Do not assign Volume, Difficulty, KEI, title slots, or final metadata recommendations.

## Workflow

1. Read the app config/profile and summarize the real feature surface.
2. Scan declared competitors and category peers for promoted wording, feature names, and positioning.
3. Research local search behavior for the target market: slang, casual/formal variants, common misspell-free variants, bilingual patterns, trend phrases, and platform-specific wording.
4. Expand semantically around core intents, concrete features, styles/vibes, content formats, and adjacent user jobs.
5. Remove unsupported, risky, competitor-branded, and irrelevant terms.
6. Deduplicate case-insensitively while preserving meaningful language variants.
7. Save the result as a Markdown artifact under `apps/<AppName>/Research/`.

## Output

Reply in chat with:

### 1. App Positioning And Competitor Summary

Briefly state the actual app positioning, target market, and competitor/market sources scanned.

### 2. New Keyword Proposal Table

Use this table:

| Keyword | Semantic Group | Reason |
|---|---|---|
| `face morph filter` | Feature | Expands the morph feature with store-search phrasing |
| `animal look alike` | Core Intent | Matches the animal identity-test intent |

Allowed semantic groups:

- `Core Intent`
- `Feature`
- `Style`
- `Visual / Content Format`
- `Bilingual / Mixed`
- `Local Slang`
- `Research Only`

### 3. Copy-Friendly Flat Lists

Provide one keyword per line, grouped as:

- Native language keywords
- English or bilingual keywords
- Research-only / risky keywords

### 4. Saved Artifact

Save a Markdown file in:

```text
apps/<AppName>/Research/
```

Use lowercase market/topic filenames:

```text
<market>_keyword_research.md
<market>_<topic>_keyword_research.md
```

Examples:

```text
apps/FunVid/Research/us_en_keyword_research.md
apps/FunVid/Research/br_pt_animal_face_keyword_research.md
```

The artifact should include the same summary, keyword table, flat lists, date, target market, and source notes. If a file already exists, append a dated section unless the user explicitly asks to replace it.
