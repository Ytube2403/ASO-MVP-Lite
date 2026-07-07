# ASO App Workspace - Electric Gun

This folder contains ASO configuration, app profile, and the keyword filtering runner for **Electric Stun Gun Simulator - Taser prank** (`com.real.electric.stun.gun.simulator.taser.prank`).

## Folder Structure

```text
apps/ElectricGun/
|-- README.md
|-- app_config.py
|-- App_Profile.json
|-- run_pipeline.py
|-- Input/
`-- Output/
```

## Configure ElectricGun

Edit `app_config.py` when needed:

- `intent_core_terms`: core intent such as `stun gun`, `taser`, `electric stun gun`, `taser simulator`, `shock gun`, `electric shocker`.
- `feature_terms`: feature terms such as `flashlight strobe`, `vibration shock`, `electric shock sounds`, `hair clipper prank`.
- `competitor_brands`: competitor brands to exclude, such as `dmitsoft`, `strategimws`.
- `typo_blacklist`: common misspellings or noisy terms such as `tazer`, `tasser`, `teser`.

`App_Profile.json` stores live app metadata and direct competitor context, including `com.dmitsoft.stungun` and `com.strategimws.stungunsimulator`, for Competitor Boost.

## Run The Pipeline

Place raw keyword CSVs from AppTweak/Sensor Tower under `apps/ElectricGun/Input/`, for example `ElectricGun_US_EN.csv`.

Use the current operating flow in `../../docs/USAGE.md`: verify cache first, warm cache if there are misses, then run the pipeline. If the agentic prompt/rubric changes and `ruleset_version` is bumped, warm every market you plan to run.

From the repo root:

```powershell
python apps\ElectricGun\run_pipeline.py --csv apps\ElectricGun\Input\ElectricGun_US_EN.csv --market US_EN
python apps\ElectricGun\run_pipeline.py --csv apps\ElectricGun\Input\ElectricGun_US_EN.csv --market US_EN --interactive
```

The Excel report includes the target 40 utility + diversity shortlist, analysis sheets, and audit reasons for each kept/dropped keyword.
