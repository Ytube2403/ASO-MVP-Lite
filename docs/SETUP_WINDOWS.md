# Complete Windows Setup Guide

This guide is for a fresh Windows machine. The goal is to run the full ASO pipeline, Excel workbooks, dashboard, batch runner, language-aware deduplication, and Git sync tools.

## 1. Quick Checklist

### Required For The Pipeline

| Tool | Purpose | Notes |
|---|---|---|
| Windows 10/11 64-bit | Runtime environment | PowerShell is included with Windows |
| [Python](https://www.python.org/downloads/windows/) 3.11+ 64-bit | Run the pipeline and tests | During installation, make sure `python` works from the terminal |
| Python packages in `requirements.txt` | CSV, Excel, dashboard, language detection, stemming | Install with `python -m pip install -r requirements.txt` |
| Internet connection | Refresh profiles from Google Play and run external research tools when needed | Pipeline runners do not call AI/translation networks |
| Modern web browser | Open the dashboard and interactive selector | Microsoft Edge or Google Chrome both work |
| Microsoft Excel or [LibreOffice Calc](https://www.libreoffice.org/download/download-libreoffice/) | Open and review `.xlsx` workbooks | Excel is recommended for the most accurate formatting |

### Required For Clone/Pull/Push

| Tool | Purpose | Notes |
|---|---|---|
| [Git for Windows](https://git-scm.com/install/windows) | Clone, pull, commit, push | `Sync.bat` requires Git |
| [GitHub CLI](https://cli.github.com/) | Authenticate with GitHub from the terminal | `Sync.bat` uses `gh auth login` |

### Recommended For Editing Code And CSV

| Tool | Purpose |
|---|---|
| [Visual Studio Code](https://code.visualstudio.com/docs/setup/windows) | Edit config, JSON, Python, and CSV files |
| [Python extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) | Select interpreter, debug, run tests |
| [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) | IntelliSense and Python code checks |
| [Rainbow CSV](https://marketplace.visualstudio.com/items?itemName=mechatroner.rainbow-csv) | View CSV columns, lint, and filter quickly |

When you open the workspace in VS Code, `.vscode/extensions.json` recommends these extensions.

## 2. What You Do Not Need To Install Separately

- Node.js, npm, Java, Docker, or a database server are not required.
- SQLite is included in Python's standard library. The pipeline uses SQLite for the agentic cache and local tracker database.
- LibreTranslate, local translation models, or separate translation services are not required.
- PowerShell and Microsoft Edge are usually already available on Windows.
- AppTweak and Sensor Tower are only CSV sources. The pipeline does not require their extensions or SDKs.

## 3. Fresh Installation

Open PowerShell at the `ASO-MVP` folder:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

## 4. Python Package Roles

| Package | Role | Importance |
|---|---|---|
| `numpy` | Normalized scoring and numeric vectors | Required |
| `pandas` | Read CSVs, DataFrames, keyword processing | Required |
| `openpyxl` | Read/write Excel `.xlsx` workbooks | Required |
| `flask` | Run the local Keyword Tracker Dashboard | Required if using the dashboard |
| `langdetect` | Fallback language detection for difficult keywords | Strongly recommended |
| `snowballstemmer` | Locale-aware singular/plural variant grouping | Strongly recommended for full deduplication |

The pipeline has conservative fallbacks when `langdetect` or `snowballstemmer` is missing, but a complete environment should install both. If `snowballstemmer` is missing, Snowball tests show `skipped` and deduplication uses only the internal fallback.

## 5. Verify The Environment

After installing packages:

```powershell
python -c "import flask, langdetect, numpy, openpyxl, pandas, snowballstemmer; print('Python environment OK')"
python -m unittest discover -s tests -v
python -m compileall -q .
```

The test suite should finish with `OK` and no Snowball `skipped` line.

## 6. Agentic Cache And English Gloss

ASO-MVP does not translate keywords over the network during runtime. Runners only read the existing `EN` column in the CSV or `AIEnglishGloss` already warmed into `.cache/agentic_keyword_analysis.sqlite3` by Antigravity subagents.

If a non-English keyword is missing `english_gloss`, the pipeline fails fast before scoring. Run `tools/warm_cache_helper.py find-misses -> prepare-batches -> save-results -> verify-cache` before the real pipeline run.

If app config bumps `ruleset_version`, the cache context hash changes and old AI rows no longer match. Rerun `find-misses -> prepare-batches -> save-results -> verify-cache` for every market you plan to run. You do not need to delete SQLite; old cache rows are just orphaned under the old hash. If you only changed brand/risk lists, you do not need to re-warm because those lists are deterministic filters on every run.

## 7. GitHub Login For Sync.bat

Only needed if you use `Sync.bat` or automatic pull/push:

```powershell
git --version
gh --version
gh auth login --web --git-protocol https
gh auth status
```

## 8. Smoke-Test The Pipeline

From the `ASO-MVP` folder:

```powershell
python run_aso_filter.py --csv C:\path\to\Pranky_US_EN.csv
python tracker\run_dashboard.py
```

The dashboard opens at `http://127.0.0.1:5100`. After a pipeline run, the workbook should include sheet `00_Project_Memory`, the app folder should include `PROJECT_MEMORY.md`, and the dashboard `Setup` tab should show setup data for the selected app.

The full operating flow, including verify/warm agentic cache before running the pipeline, is in `docs/USAGE.md`.

## 9. Network Requirements

- Internet is needed when refreshing profiles from Google Play or when you run external Antigravity/research tools outside this repo.
- Agentic cache SQLite must contain intent and `english_gloss`; runners do not fall back to translation networks when cache is missing.
- GitHub clone, pull, or push requires internet and repository access.

## 10. Quick Troubleshooting

### `ModuleNotFoundError`

Check that the correct `.venv` is active, then reinstall:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Snowball Test Is `skipped`

```powershell
python -m pip install snowballstemmer
python -m unittest tests.test_text_dedup -v
```

### `python` Or `git` Command Not Found

Close and reopen the terminal after installation. If it still fails, check the `PATH` environment variable.

### Workbook Is Open And Cannot Be Overwritten

Close the `.xlsx` file in Excel, or pass `--output` with a new filename.

### Re-translate All Keywords

Run the pipeline, then delete the local cache:

```powershell
Remove-Item .cache\agentic_keyword_analysis.sqlite3*
```
