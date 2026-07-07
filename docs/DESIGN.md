---
version: 1.3.0
name: Google Material Design Light Theme System
description: Google Light Theme design system optimized for slide decks, ASO Keyword Filter tools, and the Keyword Tracker Dashboard.
colors:
  bg-base: "#f8f9fa"        # Light Google background (Grey 100)
  bg-surface: "#ffffff"     # Main card background (White)
  text-primary: "#202124"   # Primary dark text (Google Charcoal)
  text-secondary: "#5f6368" # Secondary/description text (Google Slate)
  accent-blue: "#1a73e8"    # Google Blue
  accent-red: "#ea4335"     # Google Red
  accent-yellow: "#fbbc05"  # Google Yellow
  accent-green: "#34a853"   # Google Green
  bg-accent-soft: "#e8f0fe" # Soft blue background (Blue 50)
  border-color: "#dadce0"   # Standard Google divider border
  bg-code: "#f1f3f4"        # Code block background (Grey 200)
typography:
  fontFamily:
    display: "'Google Sans', 'Product Sans', 'Plus Jakarta Sans', sans-serif"
    body: "'Roboto', 'Plus Jakarta Sans', sans-serif"
    mono: "'JetBrains Mono', 'Consolas', monospace"
  fontSize:
    display-huge: "80px"
    display-title: "44px"
    display-subtitle: "20px"
    card-title: "24px"
    body-large: "20px"
    body-regular: "16px"
    code-block: "15px"
rounded:
  sm: "4px"
  md: "8px"
  lg: "16px"
  full: "9999px"
spacing:
  slide-padding: "70px"
  gap-grid: "24px"
  card-padding: "32px"
  content-gap: "16px"
components:
  viewport:
    background: "#eef2f3"
  deck-stage:
    width: "1920px"
    height: "1080px"
    aspect-ratio: "16/9"
    background: "{colors.bg-base}"
  card-material:
    background: "{colors.bg-surface}"
    border: "1px solid {colors.border-color}"
    border-radius: "{rounded.lg}"
    box-shadow: "0 1px 3px rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15)"
  pre-light:
    background: "{colors.bg-code}"
    border: "1px solid {colors.border-color}"
    border-radius: "{rounded.md}"
    font-family: "{typography.fontFamily.mono}"
    color: "#202124"
  dashboard-app-bar:
    background: "{colors.bg-surface}"
    border-bottom: "1px solid {colors.border-color}"
    font-family: "'Outfit', sans-serif"
  dashboard-kpi-card:
    background: "{colors.bg-surface}"
    border-radius: "{rounded.md}"
    box-shadow: "0 1px 2px rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15)"
  dashboard-chart-card:
    background: "{colors.bg-surface}"
    border-radius: "{rounded.md}"
    min-height: "400px"
  dashboard-colors:
    success-bg: "#e6f4ea"
    success-text: "#137333"
    danger-bg: "#fce8e6"
    danger-text: "#c5221f"
    warning-bg: "#fef7e0"
    warning-text: "#b06000"
---

# Google Material Design Standards (Light Theme)

## 1. Overview

This design system moves fully from a dark UI to a Material Design light theme. The goal is a friendly, clean, spacious feel similar to Google products such as Drive, Slides, and Console. The light layout improves readability and reduces layout crowding while using Google's four main accent colors to identify features and keyword groups.

## 2. Colors

- **Base background (`bg-base`):** light grey `#f8f9fa`, reducing glare and separating the slide stage from the outer viewport.
- **Surface background (`bg-surface`):** pure white `#ffffff` for content cards.
- **Google Blue (`accent-blue` - `#1a73e8`):** main titles, primary navigation, and Core Intent.
- **Google Green (`accent-green` - `#34a853`):** code examples and recommended setup items.
- **Google Yellow (`accent-yellow` - `#fbbc05`):** warnings and Consider lists.
- **Google Red (`accent-red` - `#ea4335`):** blocked competitor brands, errors, and noisy keywords.

## 3. Typography

- **Display font (`Google Sans` / `Plus Jakarta Sans`):** rounded sans-serif style for a clean, accessible Google-like feel.
- **Body font (`Roboto` / `Plus Jakarta Sans`):** high readability for long text, bullets, and explanations.
- **Monospace font (`JetBrains Mono` / `Consolas`):** fixed-width code and structured data.

## 4. Layout And Division

To prevent text overflow and layout drift, the slide system is split from 7 slides to **10 slides**:

- The **10-step workflow** is split into 2 slides, 5 steps per slide.
- Output structure is grouped by v4.5 concepts: target 40 utility + diversity and audit sheet `13_Top_By_Volume`.
- Input data standards are separated into one slide for CSV naming and one slide for required columns.

## 5. Visual Illustrations

Every slide should include at least one visual element:

- Timeline paths or roadmaps for workflow steps.
- File-tree diagrams for CSV naming and folder placement.
- Data-grid mockups for required columns.
- Doughnut charts for keyword quotas.
- Editor-layout mockups for config files.

## 6. Do's And Don'ts

### Do

- Use the defined Google color tokens for emphasis.
- Keep at least 70px slide padding and at least 24px between cards.
- Use light text on dark code blocks and dark text on light content surfaces.

### Don't

- Do not put more than 5 child cards in one 16:9 slide-stage grid.
- Do not use dark-heavy card backgrounds inside this light theme.
- Do not use serif fonts for body text.

## 7. Keyword Tracker Dashboard

The **ASO Keyword Tracker Dashboard** (`tracker/static/`) follows this Google Material Design Light Theme with web-app-specific additions.

### 7.1 Typography

- **Heading/UI font:** `Outfit` from Google Fonts. It replaces Google Sans because of its open license while keeping a modern sans-serif feel.
- **Body/data font:** system fallback from `Roboto`.

### 7.2 Dashboard Color Semantics

| Token | Color | Meaning |
|---|---|---|
| `--success` / `--success-bg` | `#34a853` / `#e6f4ea` | Positive growth: rank up, volume up |
| `--danger` / `--danger-bg` | `#ea4335` / `#fce8e6` | Negative movement: rank down, volume down, keyword lost |
| `--warning` / `--warning-bg` | `#fbbc05` / `#fef7e0` | Warning or needs-review state |
| `--primary` / `--primary-bg` | `#1a73e8` / `#e8f0fe` | Primary accent, action buttons, active tab, Brand badge |

### 7.3 Components

- **App Bar:** sticky top bar, white background, bottom border `#dadce0`.
- **Control Panel:** four dropdowns (App, Locale, Month A, Month B) and Export button.
- **Tab Bar:** five horizontal tabs (Overview, Keywords, Trend, Movers, Setup) with an indicator under the active tab.
- **KPI Cards:** four-column grid, fixed 120px height, large value and delta badge.
- **Chart Cards:** Apache ECharts, minimum 300px height, responsive resize.
- **Data Table:** sortable headers, search, filters, pagination, zebra striping.
- **Toast:** bottom-right floating notification, auto-hides after 3 seconds.

### 7.4 Spacing And Layout

- **Main content padding:** 24px.
- **Card gap:** 16-24px.
- **Grid breakpoints:** 4 columns -> 2 columns at <=1200px -> 1 column at <=650px.

### 7.5 Setup Tab / Project Memory

- **Purpose:** read-only overview for the selected app, sourced from `app_config.py` and `App_Profile.json`, independent of locale/month.
- **Sections:** App identity, Positioning, Keyword setup, Competitor setup, Drop/risk setup, User overrides, Quota, and Warnings.
- **Cards:** use an 8px-radius grid card layout. Do not nest cards inside cards. Each section should have a short title and scannable chips/rows.
- **Badges:** use clear badges for `Drop`, `Consider`, `Reserve`, and `Boost` using dashboard semantic colors.
- **Warnings:** show prominent warning cards for missing competitors, missing competitor brands, config overlap, or profile/config mismatch.
- **No editing:** v1 should not include editing controls. To change setup, users edit the source of truth in `app_config.py` or `App_Profile.json`.
