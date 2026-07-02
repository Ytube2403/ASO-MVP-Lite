import os
import re


APP_REGISTRY = {
    "ar_filter": {
        "folder": "apps/AR_Filter",
        "runner": "apps/AR_Filter/run_ar_filter_v4_3.py",
        "config": "apps/AR_Filter/app_config.py",
        "aliases": ["ARFilter", "AR_Filter"],
    },
    "game_emulator": {
        "folder": "apps/Game_Emulator",
        "runner": "apps/Game_Emulator/run_game_emulator_v4_4.py",
        "config": "apps/Game_Emulator/app_config.py",
        "aliases": ["GameEmulator", "GameRetro", "Game_Emulator"],
    },
    "prank_sounds": {
        "folder": "apps/Prank_Sounds",
        "runner": "apps/Prank_Sounds/run_pipeline.py",
        "config": "apps/Prank_Sounds/app_config.py",
        "aliases": ["Pranky", "PrankSounds", "Prank_Sounds"],
    },
    "control_widget": {
        "folder": "apps/Control_Widget",
        "runner": "apps/Control_Widget/run_control_widget_v4_3.py",
        "config": "apps/Control_Widget/app_config.py",
        "aliases": ["ControlWidget", "Control_Widget"],
    },
    "app_template": {
        "folder": "apps/App_Template",
        "runner": "apps/App_Template/run_pipeline.py",
        "config": "apps/App_Template/app_config.py",
        "aliases": ["AppTemplate", "App_Template"],
    },
    "emoji_battery_icon_customize": {
        "folder": "apps/Emoji_Battery_Icon_Customize",
        "runner": "apps/Emoji_Battery_Icon_Customize/run_pipeline.py",
        "config": "apps/Emoji_Battery_Icon_Customize/app_config.py",
        "aliases": ["EmojiBatteryIconCustomize", "Emoji_Battery_Icon_Customize", "EmojiBattery"],
    },
    "fun_vid": {
        "folder": "apps/FunVid",
        "runner": "apps/FunVid/run_pipeline.py",
        "config": "apps/FunVid/app_config.py",
        "aliases": ["FunVid", "Fun_Vid", "FunnyFaceFilters", "FunVid_100_Keywords", "FunVid_AnimalFace"],
    },
    "electric_gun": {
        "folder": "apps/ElectricGun",
        "runner": "apps/ElectricGun/run_pipeline.py",
        "config": "apps/ElectricGun/app_config.py",
        "aliases": ["ElectricGun", "Electric_Gun", "StunGun", "TaserPrank", "electric_gun"],
    },
    "nds_emulator": {
        "folder": "apps/NDS_Emulator",
        "runner": "apps/NDS_Emulator/run_pipeline.py",
        "config": "apps/NDS_Emulator/app_config.py",
        "aliases": ["NDSEmulator", "NDS_Emulator", "SuperNDS", "com.emulator.nds.super.game.console.handheld"],
    },
}


def normalize_alias(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def resolve_app(alias, project_root=None):
    normalized = normalize_alias(alias)
    for app_key, entry in APP_REGISTRY.items():
        aliases = [app_key, entry["folder"], *entry.get("aliases", [])]
        if normalized in {normalize_alias(candidate) for candidate in aliases}:
            resolved = dict(entry)
            resolved["key"] = app_key
            if project_root:
                resolved["runner_path"] = os.path.join(project_root, *entry["runner"].split("/"))
                resolved["config_path"] = os.path.join(project_root, *entry["config"].split("/"))
            return resolved
    raise KeyError(f"Unknown app alias '{alias}'. Registered aliases: {registered_aliases()}")


def registered_aliases():
    return sorted(alias for entry in APP_REGISTRY.values() for alias in entry.get("aliases", []))
