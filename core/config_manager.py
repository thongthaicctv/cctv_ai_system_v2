import copy
import json
import os

CONFIG_FILE = "config.json"
_CONFIG_CACHE = None
_CONFIG_MTIME = None


def _default_config():
    return {
        "alert_enabled": True,
        "storage_path": "videos",
        "record_auto_stop_seconds": 300,
        "record_mapping": {},
        "cameras": [],
    }


def _normalize_config(data):
    merged = _default_config()
    merged.update(data or {})

    cameras = merged.get("cameras", [])
    camera_ids = [str(cam.get("id", "")).strip() for cam in cameras if cam.get("id")]
    valid_ids = set(camera_ids)

    raw_mapping = merged.get("record_mapping", {}) or {}
    normalized = {}

    for cam_id in camera_ids:
        if cam_id in raw_mapping:
            targets = [
                str(target)
                for target in raw_mapping.get(cam_id, [])
                if str(target) in valid_ids
            ]
            normalized[cam_id] = targets
        else:
            normalized[cam_id] = [cam_id]

    merged["record_mapping"] = normalized
    return merged


def load_config(force=False):
    global _CONFIG_CACHE, _CONFIG_MTIME

    if not os.path.exists(CONFIG_FILE):
        default_data = _default_config()
        _CONFIG_CACHE = default_data
        _CONFIG_MTIME = None
        return copy.deepcopy(default_data)

    try:
        current_mtime = os.path.getmtime(CONFIG_FILE)
    except OSError:
        return copy.deepcopy(_default_config())

    if force or _CONFIG_CACHE is None or _CONFIG_MTIME != current_mtime:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            _CONFIG_CACHE = _normalize_config(json.load(f))
        _CONFIG_MTIME = current_mtime

    return copy.deepcopy(_CONFIG_CACHE)


def save_config(data):
    global _CONFIG_CACHE, _CONFIG_MTIME

    normalized = _normalize_config(data)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=4, ensure_ascii=False)

    _CONFIG_CACHE = normalized
    try:
        _CONFIG_MTIME = os.path.getmtime(CONFIG_FILE)
    except OSError:
        _CONFIG_MTIME = None
