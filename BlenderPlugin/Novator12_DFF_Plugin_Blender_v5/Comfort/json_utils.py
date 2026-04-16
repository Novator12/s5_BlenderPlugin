import json


def mapping_or_empty(value):
    return value if isinstance(value, dict) else {}


def list_or_empty(value):
    return value if isinstance(value, list) else []


def nested_mapping(source, *keys):
    current = source
    for key in keys:
        current = mapping_or_empty(current).get(key)
    return mapping_or_empty(current)


def nested_list(source, *keys):
    current = source
    for key in keys:
        current = mapping_or_empty(current).get(key)
    return list_or_empty(current)


def json_loads_or_default(raw_value, default):
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return default
    return default if parsed is None else parsed
