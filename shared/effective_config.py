import importlib.util
import json
import os

from shared.app_registry import resolve_app


def _load_python_module(path):
    spec = importlib.util.spec_from_file_location("aso_app_config", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load app config: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_runner_config(runner_path, market=""):
    with open(runner_path, "r", encoding="utf-8") as runner_file:
        source = runner_file.read()

    start = source.find("config = {")
    if start == -1:
        raise RuntimeError(f"config = {{ block not found in {runner_path}")

    depth = 0
    end = -1
    for index in range(start + len("config = "), len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end == -1:
        raise RuntimeError(f"Cannot locate end of config block in {runner_path}")

    class ArgsMock:
        pass

    args = ArgsMock()
    args.market = market or "US_EN"
    sandbox = {"args": args}
    exec(source[start:end], sandbox)
    return dict(sandbox["config"])


def deep_merge_config(base, override):
    """Merge override into base without silently discarding list/dict content.

    Plain dict.update() replaces whole top-level keys, so if both `base` and
    `override` define e.g. risky_ip_terms with different entries, override's
    list wins entirely and base's entries vanish (this is exactly how a
    runner's inline risky_ip_terms lost "mario"/"zelda" to FILTER_POLICY's
    shorter list). Dicts merge recursively key-by-key; lists union in order
    (base first, then override's new items); everything else (scalars) still
    lets override win, preserving the intended "override configures policy"
    behavior for non-collection values.
    """
    merged = dict(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = deep_merge_config(base_value, override_value)
        elif isinstance(base_value, list) and isinstance(override_value, list):
            merged[key] = base_value + [item for item in override_value if item not in base_value]
        else:
            merged[key] = override_value
    return merged


def load_effective_config(config_path, runner_path=None, market=""):
    module = _load_python_module(config_path)
    config = getattr(module, "APP_CONFIG", None)
    if isinstance(config, dict):
        effective = dict(config)
    elif runner_path:
        effective = _extract_runner_config(runner_path, market)
        filter_policy = getattr(module, "FILTER_POLICY", None)
        if isinstance(filter_policy, dict):
            effective = deep_merge_config(effective, filter_policy)
    else:
        raise RuntimeError(f"APP_CONFIG dict not found in {config_path}")

    if market:
        effective["market"] = market
    return effective


def load_app_profile(app_folder):
    profile_path = os.path.join(app_folder, "App_Profile.json")
    if not os.path.exists(profile_path):
        return {}
    with open(profile_path, "r", encoding="utf-8") as profile_file:
        return json.load(profile_file)


def resolve_effective_app(app_alias, project_root, market=""):
    app = resolve_app(app_alias, project_root)
    app_folder = os.path.join(project_root, *app["folder"].split("/"))
    config = load_effective_config(app["config_path"], app.get("runner_path"), market)
    from shared.profile_service import get_app_profile
    app_profile = get_app_profile(config, config.get("app_name", "App"), app_folder)
    return app, app_folder, config, app_profile
