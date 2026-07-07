---
name: create-profile
description: Create or repair a complete, schema-correct App_Profile.json for a registered app so the ASO pipeline understands the app's real identity, positioning, features, exclusions, and competitors, and therefore evaluates keyword relevancy and blacklists correctly instead of guessing. Use when the user asks to create, build, or fix an app profile, for example "Create profile <AppName>", "Build profile <AppName>", or "Fix App_Profile.json for <AppName>", when App_Profile.json is missing/incomplete, or when a pipeline/preflight reports ProfileStatus EMPTY_FETCH_FAILED, GENERATED_STALE_FALLBACK, or "No competitor apps found".

---

# Create Profile (standard App_Profile.json)

`App_Profile.json` is the app's ground truth for the pipeline. `shared/profile_service.py::get_app_profile` prefers a hand-authored `App_Profile.json` over any scraped/generated profile, marks it `ProfileStatus: CUSTOM`, and feeds it into relevancy scoring, competitor keyword scanning, and PROJECT_MEMORY. A missing or thin profile is why keyword evaluation "guesses" — no competitors, weak positioning, wrong identity. This skill produces a **complete, consistent, schema-correct** profile the system can trust.

The canonical schema is `schema_version 2.0` — mirror `apps/App_Template/App_Profile.json` exactly for structure.

## When to run

- The user asks to create/build/repair a profile for an app.
- Preflight / `run-pipeline-aso` reports `EMPTY_FETCH_FAILED`, `GENERATED_STALE_FALLBACK`, or "No competitor apps found in App_Profile.json".
- `build_project_memory` warns about profile↔config mismatches (see step 4).

## Step 0 — Resolve the app and read what already exists

Resolve the app via the registry (never guess a folder):

```powershell
python -c "from shared.app_registry import resolve_app; import os; print(resolve_app('<alias>', os.getcwd()))"
```

Then read, to ground the profile in the app's real identity:

- `<app folder>/app_config.py` — the source of truth for `app_id`, `app_name`, `category`, and the semantic vocabulary (`intent_core_terms`, `feature_terms`, `style_terms`, `market_language_policy`, `competitor_brands`, `risky_ip_terms`).
- `<app folder>/App_Profile.json` if present — repair/enrich it, do not silently discard user content.
- `<app folder>/PROJECT_MEMORY.md` and anything under `<app folder>/Research/` for prior findings.

If `app_config.py` only exposes a legacy `FILTER_POLICY`, note that the profile becomes the primary identity source — fill it especially carefully.

## Step 1 — Gather real store evidence

Do original research; do not invent facts. Prefer, in order:

1. A user-provided Google Play/App Store URL or AppTweak export (most authoritative).
2. The live store listing fetched with the web tools available in this environment (title, developer, category, content rating, short + full description, installs, last updated).
3. `App_Profile.json`/`PROJECT_MEMORY.md`/`Research/` already in the repo.

For **competitors**, find 2–5 genuinely comparable apps (same core function/market), and for each capture: `package_id`, `title`, `developer`, `why_relevant`, `short_description`, the first ~200 chars of their full description (`desc200`), and a few `overlap_keywords` (terms they rank/optimize for that this app legitimately shares). These fields directly drive competitor keyword scanning — accuracy matters more than quantity.

If the store cannot be fetched (offline) and the user has no export, tell them the profile will be authored from repo evidence only and may be incomplete — do not fabricate live metadata.

## Step 2 — Write App_Profile.json (schema 2.0)

Write `<app folder>/App_Profile.json` with this structure (all sections present). The fields the pipeline actually consumes are marked ★ — get those right above all:

```json
{
  "schema_version": "2.0",
  "profile_type": "aso_app_profile",
  "last_checked": "<YYYY-MM-DD today>",
  "source_url": "<store URL>",
  "app_identity": {
    "app_id": "<MUST equal app_config app_id>",        // ★
    "package_id": "<same as app_id for Android>",
    "title": "<live store title>",                       // ★
    "developer": "<developer>",
    "category": "<store category, consistent with config>",
    "content_rating": "<e.g. Rated for 3+>",
    "monetization": { "contains_ads": true, "in_app_purchases": false },
    "installs": "<e.g. 1M+>",
    "updated_on": "<store last updated>"
  },
  "live_store_metadata": {
    "short_description": "<real current short description>",   // ★ relevancy signal
    "full_description_digest": {
      "one_sentence_summary": "<one-sentence what-it-does>",    // ★ full_description signal
      "description_sections": ["...", "..."],
      "main_feature_claims": ["...", "..."],
      "how_to_use_flow": ["Step 1 ...", "Step 2 ..."]
    }
  },
  "corrected_positioning": {
    "primary_positioning": "<what this app really is>",         // ★ PROJECT_MEMORY
    "secondary_positioning": ["..."],
    "not_the_right_positioning": ["<intents to exclude>"],      // ★ prevents wrong-intent keywords
    "strongest_differentiators": ["..."]                        // ★
  },
  "competitor_strategy": {
    "recommended_competitor_types": [
      { "type": "Direct competitor", "description": "..." }
    ],
    "suggested_competitors": [
      {
        "package_id": "com.competitor.one",                     // ★
        "title": "Competitor One",                              // ★
        "developer": "...",
        "relationship": "direct competitor",
        "why_relevant": "...",
        "short_description": "...",                             // ★ scanned for proven keywords
        "desc200": "<first ~200 chars of their full description>", // ★
        "overlap_keywords": ["...", "..."]                       // ★
      }
    ]
  }
}
```

Rules that keep the system from getting confused:
- `app_identity.app_id` **must** equal `app_config.py`'s `app_id`. A mismatch makes PROJECT_MEMORY warn and misattributes evaluation.
- `category` and positioning must be consistent with the app's `intent_core_terms`/`feature_terms` — the profile and config should describe the *same* app.
- `not_the_right_positioning` should name the intents this app must NOT rank for (e.g. a retro emulator that is not a "video editor") so wrong-intent keywords are dropped, not scored.
- Every `suggested_competitors` entry needs at least `package_id`, `title`, and `short_description` (or `why_relevant`) so it adapts cleanly; otherwise it is silently dropped and you lose competitor keyword coverage.
- Preserve accurate content from an existing `App_Profile.json`; only correct what is wrong or missing.
- Write valid JSON (double quotes, no trailing commas, UTF-8). Do not leave template placeholder text like "Fill in one sentence..." in a real profile.

## Step 3 — Cross-check profile ↔ config (avoid keyword-eval confusion)

The profile feeds relevancy/competitor scanning; hard-drops and blacklists live in `app_config.py`. For consistent evaluation, verify — and report to the user (do not silently edit config here):

- Competitor **brand names** from `suggested_competitors` are also present in `app_config.py`'s `competitor_brands` (so they are hard-dropped, not scored as opportunities).
- Any IP/console/franchise names surfaced during research are reflected in `risky_ip_terms` / relevant risk groups.
- `app_name`, `app_id`, and `category` agree between config and profile.

If gaps exist, list the exact terms to add to config so the user (or a config-editing step) can apply them.

## Step 4 — Validate

Confirm the profile loads as CUSTOM, adapts cleanly, and raises no setup warnings:

```powershell
python -c "from shared.effective_config import resolve_effective_app; import os; _,_,cfg,prof = resolve_effective_app('<alias>', os.getcwd(), '<MARKET>'); print('status:', prof.get('ProfileStatus'), '| app_id match:', cfg.get('app_id')==prof.get('app_id'), '| competitors:', len(prof.get('competitors', [])))"
python -c "from shared.project_memory import build_project_memory_for_app; import os; m=build_project_memory_for_app(os.path.join(os.getcwd(),'apps','<AppFolder>')); print('warnings:', m['warnings'] or 'none')"
```

Pass criteria:
- `status: CUSTOM`
- `app_id match: True`
- `competitors:` equals the number of `suggested_competitors` you wrote (if lower, some entries failed to adapt — fix their required fields)
- `warnings: none` — or, for each remaining warning, either fix it or explain to the user why it is acceptable (e.g. genuinely no direct competitors exist).

Do not consider the profile "done" until validation passes or every remaining warning is explained.

## Step 5 — Report

Tell the user:
- The file written (`<app folder>/App_Profile.json`) and whether it was created or repaired.
- `ProfileStatus`, app_id match, competitor count, and the validation `warnings` result.
- Any profile↔config gaps from Step 3 (exact terms to add to `competitor_brands`/`risky_ip_terms`).
- Which fields are evidence-based vs inferred, and note anything that needs a live re-fetch later (profiles have a 14-day TTL for generated profiles, but a CUSTOM profile you author is used until changed).

## Definition of done (self-check before you reply)

Do not finish until every box is true. If any is false, fix it before replying.

- [ ] `App_Profile.json` was written with the full schema 2.0 structure (all sections present, valid JSON, no placeholder text).
- [ ] Every ★ field the pipeline consumes is populated from real evidence (or clearly marked as inferred).
- [ ] `app_identity.app_id` equals `app_config.py`'s `app_id`.
- [ ] Each `suggested_competitors` entry has at least `package_id`, `title`, and `short_description`/`why_relevant` (so none are silently dropped).
- [ ] Validation (Step 4) shows `ProfileStatus: CUSTOM`, `app_id match: True`, competitor count equal to the number written, and `warnings: none` — or every remaining warning is explained to the user.
- [ ] Profile↔config gaps (Step 3) were reported with the exact terms to add — nothing was silently changed in `app_config.py`.

## Guardrails

- Never fabricate store metadata, installs, or competitors to force validation to pass. Author from real evidence; mark inferences.
- Do not overwrite a correct hand-authored profile — enrich/repair it.
- Keep this skill focused on the profile. Editing `app_config.py`, running the filter, or warming cache are separate steps (`run-pipeline-aso`, `warm-agentic-cache`).
- Seed keyword *research* is a different, earlier task — use `.agents/skills/aso-keyword-research/SKILL.md` for that.
