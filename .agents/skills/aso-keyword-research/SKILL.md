---
name: aso-keyword-research
description: Expand and build ASO seed keyword sets for a registered app in this workspace using app config/profile, competitor analysis, local search behavior, and web research. Use when the user asks to research, expand, collect, or build keywords for an app, including prompts like "Research keywords <AppName>", "Build keyword seeds for <AppName>", "Expand ASO keywords for <AppName>", or market-specific requests such as BR_PT keyword research for FunVid.
---

# ASO Keyword Research

Use this skill to collect seed keywords for an app before running the ASO filtering pipeline. The goal is breadth and relevance: collect many plausible seed keywords, grouped by intent, without scoring Volume, Difficulty, KEI, or metadata placement.

## Execution contract (MUST read and follow first)

These rules are mandatory. Do not skip, reorder, or substitute them.

1. You **MUST run all five research lanes as five separate subagents** (see "Research Lanes") whenever a multi-agent / task-spawning tool exists in this environment. Spawn them in parallel when the environment supports it.
2. You **MUST NOT do the five lanes yourself inline** when such a tool is available. Doing the research in the main thread instead of delegating is a failure of this skill.
3. The **only** allowed fallback is when the environment genuinely has no subagent/task tool at all. In that case you MUST first tell the user, verbatim: "No multi-agent tool is available, running the 5 lanes sequentially inline as a fallback." — then proceed sequentially. Never take this fallback silently, and never take it merely because it is faster.
4. Before spawning, output a short plan listing the five subagents by name so it is visible that all five will run.
5. You are not done until the "Definition of done" checklist at the end passes. If any lane did not run, re-run that lane before reporting.

## Inputs

Resolve the app from the user's app name or alias. Prefer the workspace registry when available, and use the resolved registry `folder` path instead of guessing a folder from the alias. Then read:

- `<resolved app folder>/app_config.py`
- `<resolved app folder>/App_Profile.json`
- `<resolved app folder>/PROJECT_MEMORY.md` when present
- Existing input CSVs under `<resolved app folder>/Input/` when they help avoid duplicates
- Existing research notes under `<resolved app folder>/Research/` if present

Extract:

- App identity, market, category, platform, and semantic mode
- Actual app positioning, feature claims, differentiators, and exclusions
- `intent_core_terms`, `feature_terms`, `style_terms`, `visual_terms`
- Competitor brands, suggested competitors, risky IP/platform terms, and irrelevant intents

If `app_config.py` only exposes a legacy `FILTER_POLICY` instead of a full `APP_CONFIG`, derive missing identity, features, and semantic terms from `App_Profile.json`, `PROJECT_MEMORY.md`, and the app runner.

If the target market is explicit in the user request, use it. If it is ambiguous, infer from `app_config.py`; ask only when the requested market conflicts with the config and the intended market cannot be inferred safely.

## Research Lanes

Cover these five research lanes. Per the Execution contract above, each lane MUST be run as its **own subagent** (in parallel when supported) using whatever multi-agent / task tool this environment provides. Spawn exactly these five, by name; do not merge them and do not run them inline unless the no-tool fallback in the Execution contract applies:

1. **Linguistic & Cultural Analyst (`linguistic_cultural_agent`)**:
   - Focus: Local slang, colloquial terms, emotional qualifiers, cultural context, diacritic/no-diacritic behavior, and native category names (e.g., in ID: *jadul*, *lawas*, *gimbot*, *dingdong*, *rental ps*).
2. **Store Search Autocomplete Scanner (`autocomplete_scanner_agent`)**:
   - Focus: Collecting real store autocomplete data when an autocomplete export/scraper is available; otherwise clearly labeling results as autocomplete-style inferred suggestions from store listings, web search phrasing, and existing input CSVs.
3. **Bilingual Search Analyst (`bilingual_search_agent`)**:
   - Focus: Analyzing how local users code-switch/mix English technical terms (e.g., *emulator, GBA, ROM, save state*) with local verbs, prepositions, or device terms (e.g., *cara main*, *cara pasang*, *di hp*, *pakai stik*).
4. **Console & IP Brand Mapper (`console_ip_mapper_agent`)**:
   - Focus: Compiling a comprehensive database of all classic consoles, clones (e.g., *Spica, Polystation*), and game IPs (e.g., *Mario, Sonic, Pokemon, GTA, Winning Eleven*) to serve as both search opportunities and blacklist candidates for later filtering stages.
5. **Feature-Based Keyword Expander (`feature_keyword_expander_agent`)**:
   - Focus: Taking the core features of the product (e.g., *save/load state, fast forward, virtual button layout, controller mapping*) as seed keywords and expanding them into related local search variations.

## Evidence Standards

Classify every non-obvious keyword or insight with one of these evidence levels:

- `Observed`: captured from an explicit source such as an ASO export, autocomplete scrape CSV, store listing title/snippet, app review, local article, forum thread, or video title. Include the source URL/path and accessed date.
- `Derived`: transformed from observed evidence by localizing, adding/removing diacritics, or combining a local verb with an observed category term. Cite the source terms used.
- `Inference`: plausible language-market reasoning without direct evidence. Keep it, but label it as inference and avoid overstating it.

Do not call a keyword "scraped", "actual autocomplete", or "store suggestion" unless it came from an autocomplete API/export/browser scrape or a saved autocomplete CSV. If it came from web search snippets or store listing titles, label it `Autocomplete-style / Inferred`.

## Lane Procedures

### Cultural & Linguistic Lane

1. Start from the app's real feature surface and category nouns.
2. Collect local-language category names, verbs, and user jobs from at least two available evidence types when possible: app/store listings, local help articles, reviews/comments, existing CSVs, or web search result phrasing.
3. Generate diacritic and no-diacritic variants only when the language commonly supports both search behaviors.
4. Separate generic local culture/style terms from platform/IP/competitor terms.
5. Output a compact evidence table with columns: `Term`, `Meaning`, `Evidence Level`, `Source / Derivation`, `Safety`.

### Store Autocomplete Lane

1. First check for a saved autocomplete dataset under `<resolved app folder>/Research/autocomplete/<market>_autocomplete.csv` or a user-provided ASO export.
2. If a scraper/tool exists and the user explicitly asked for real autocomplete scraping, run it with conservative rate limits and save raw results before analysis.
3. If no scrape/export exists, do not pretend one exists. Use store listings, web search result phrasing, and existing CSVs only as `Autocomplete-style / Inferred` evidence.
4. Keep raw autocomplete strings separate from cleaned or localized variants.
5. Classify each suggestion as `Safe`, `Research Only`, `Blacklist Candidate`, or `Compliance Risk`.
6. Record seed query, suggestion, source type, URL/path, accessed date, and whether the suggestion is raw or normalized.

## Research Rules

- Stay faithful to actual app features. Do not invent unsupported features.
- For non-US markets, do original local-market research. Do not simply translate US_EN keywords.
- Use available web/search tools for current competitor pages, Google Play/App Store phrasing, trends, autocomplete-style phrases, and local slang.
- Keep competitor, console, platform, and IP terms in the research artifact as they are crucial for blacklist mapping. In fact, having IP/brand names is highly recommended for mapping out competitor brand spaces and creating the Blacklist for the later filtering step.
- Split keyword output by safety: `Safe Local Concepts & Nicknames`, `Safe English & Bilingual Keywords`, `Autocomplete & Store Suggestions`, and `Blacklist Candidates (Consoles & Game IPs)`.
- Include source notes with URLs and accessed dates.
- Remove obvious noise such as `app`, `free`, `download`, and unrelated categories unless they are part of a meaningful long-tail query.
- Include diacritic and no-diacritic variants when local users commonly type both.
- Include bilingual or mixed-language queries when they are natural for the target market.
- Keep keyword research separate from filtering. Do not assign Volume, Difficulty, KEI, title slots, or final metadata recommendations.
- Target roughly 100-300 proposed seed keywords per market.

## Workflow

1. Read the app config/profile and summarize the real feature surface.
2. Output the plan of the five named subagents, then **spawn all five as subagents** (parallel when supported) per the Execution contract. Take the inline fallback only if there is genuinely no multi-agent tool, and only after telling the user.
3. Consolidate their keyword lists, local insights, and source notes.
4. Separate safe seeds from research-only IP/competitor terms and blacklist candidates.
5. Deduplicate case-insensitively while preserving meaningful language variants.
6. Write a consolidated master keyword research report.
7. Save the result as a Markdown file under `<resolved app folder>/Research/`.

## Definition of done (self-check before you reply)

Do not finish until every box is true. If any is false, fix it (usually: re-run the missing lane) before replying.

- [ ] All five lanes ran as **separate subagents** (or, if no multi-agent tool exists, the fallback notice was shown to the user first).
- [ ] The chat output has a distinct, labeled subsection for each of the five lanes.
- [ ] Every non-obvious keyword has an evidence level (`Observed` / `Derived` / `Inference`) with a source/derivation.
- [ ] Autocomplete results are labeled real-scraped vs `Autocomplete-style / Inferred` — no false "scraped" claims.
- [ ] The Markdown artifact was written under `<resolved app folder>/Research/`.
- [ ] No Volume / Difficulty / KEI / metadata slots were assigned (that is the pipeline's job, not research).

## Output

Reply in chat with:

### 1. App Positioning And Competitor Summary

Briefly state the actual app positioning, target market, and competitor/market sources scanned.

### 2. Market Insights Summary

Provide a bulleted summary of findings from the 5 subagents:
- Cultural & Linguistic Context, including evidence levels and any inference-only terms
- Store Autocomplete Suggestions, explicitly distinguishing real scraped/exported suggestions from autocomplete-style inferred suggestions
- Bilingual Search Habits
- Console & IP Brand Map (including safe vs. blacklist candidates)
- Feature-Based Keyword Expansion

### 3. Master Keyword Proposal Table

Use this table:

| Keyword | Semantic Group | Local Context & Search Intent | Evidence Level | Safety / ASO Classification |
|---|---|---|---|---|
| `emulator game jadul` | Core Intent | Retro game emulator. Bridges "emulator" and local nostalgia. | Observed | Safe Local Slang |
| `gameboy` | Research Only | Nintendo's handheld console. Used for blacklist mapping. | Observed | Registered Console (Blacklist) |

Allowed ASO Classifications:
- `Safe Local Slang`
- `Safe Descriptor / Generic`
- `Safe Bilingual Phrase`
- `Safe Autocomplete Search` (only when the query has no competitor brand, console/platform brand, game IP, ROM/download/BIOS compliance risk, or unsupported feature)
- `Research Only / Console Mapping`
- `Research Only / Competitor Mapping`
- `Research Only / IP Mapping`
- `Compliance Risk (Audit Only)`
- `Clone Brand (Review/Caution)`
- `Registered Console (Blacklist)`
- `Trademarked Game IP (Blacklist)`

### 4. Copy-Friendly Flat Lists

Provide one keyword per line, grouped as:
- Safe Local Concepts & Nicknames
- Safe English & Bilingual Keywords
- Real Autocomplete / ASO Export Suggestions, if available
- Autocomplete-style / Inferred Store Suggestions, if real autocomplete data is unavailable
- Blacklist Candidates - Consoles & Game IPs (for downstream blacklist setup)
- Excluded / Deprioritized keywords with short reasons

### 5. Source Notes

List source URLs/paths and accessed dates for competitor pages, store listings, autocomplete exports/scrapes, local-market articles, app reviews, existing CSVs, and any other references used. If a point is an inference from local search behavior rather than a directly sourced fact, label it as `Inference`.

### 6. Policy And Filtering Notes

Briefly summarize which keyword families should remain research-only, blacklist candidates, or deprioritized before filtering. Do not draft title, subtitle, short description, full description, metadata slots, or final metadata placement recommendations.

### 7. Saved Artifact

Save a Markdown file in:

```text
<resolved app folder>/Research/
```

Use lowercase market/topic filenames:

```text
<market>_keyword_research.md
<market>_<topic>_keyword_research.md
```

Examples:

```text
apps/FunVid/Research/us_en_keyword_research.md
apps/Game_Emulator/Research/id_id_keyword_research.md
```

The artifact should include the same summary, market insights, keyword table, flat lists, source notes, policy/filtering notes, date, and target market. If a file already exists, append a dated section unless the user explicitly asks to replace it.
