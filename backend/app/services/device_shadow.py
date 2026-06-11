import json
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _compute_delta(desired: dict, reported: dict) -> dict:
    if not desired:
        return {}
    reported_clean = {k: v for k, v in reported.items() if not k.startswith("_")}
    delta = {}
    for key, desired_val in desired.items():
        if key.startswith("_"):
            continue
        if key not in reported_clean or reported_clean[key] != desired_val:
            delta[key] = desired_val
    return delta
