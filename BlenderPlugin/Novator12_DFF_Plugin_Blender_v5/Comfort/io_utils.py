import json
import os
import subprocess

from .json_utils import list_or_empty, mapping_or_empty
from .transform_utils import get_converter_exe_location


def safe_decode_console(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1", errors="replace")


def convert_binary_dff_to_json(binary_data, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    process = subprocess.Popen(
        [converter_path, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(input=binary_data)
    stderr_text = stderr.decode("utf-8", "replace").strip()
    if process.returncode != 0:
        raise RuntimeError(f"S5Converter import failed with exit code {process.returncode}: {stderr_text or 'no stderr output'}")
    if stderr_text:
        raise RuntimeError(f"S5Converter import reported an error: {stderr_text}")
    return json.loads(stdout.decode("utf-8"))


def collect_invalid_texture_coordinate_entries(payload):
    invalid_entries = []
    clump = mapping_or_empty(payload).get("clump")
    geometries = list_or_empty(mapping_or_empty(clump).get("geometries"))

    for geometry_index, geometry in enumerate(geometries):
        texture_layers = list_or_empty(mapping_or_empty(geometry).get("textureCoordinates"))
        for layer_index, layer in enumerate(texture_layers):
            if not isinstance(layer, list):
                invalid_entries.append((geometry_index, layer_index, None, type(layer).__name__))
                continue

            for coord_index, uv in enumerate(layer):
                if not isinstance(uv, dict) or "u" not in uv or "v" not in uv:
                    invalid_entries.append((geometry_index, layer_index, coord_index, uv))

    return invalid_entries


def convert_json_to_binary_dff(payload, converter_path):
    if not os.path.isfile(converter_path):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {converter_path}")

    invalid_entries = collect_invalid_texture_coordinate_entries(payload)
    if invalid_entries:
        preview = ", ".join(
            f"geom {geometry_index}, layer {layer_index}, index {coord_index}: {value!r}"
            for geometry_index, layer_index, coord_index, value in invalid_entries[:8]
        )
        raise RuntimeError(
            "JSON enthaelt ungueltige textureCoordinates-Eintraege. "
            "Erwartet wird pro UV ein Objekt mit 'u' und 'v'. "
            f"Beispiele: {preview}"
        )

    process = subprocess.Popen(
        [converter_path, "--export"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    stdout, stderr = process.communicate(input=payload_bytes)
    stderr_text = stderr.decode("utf-8", "replace").strip()
    if process.returncode != 0:
        raise RuntimeError(f"S5Converter export failed with exit code {process.returncode}: {stderr_text or 'no stderr output'}")
    if stderr_text:
        raise RuntimeError(f"S5Converter export reported an error: {stderr_text}")
    if not stdout:
        raise RuntimeError("S5Converter export lieferte keine DFF-Daten (0 Bytes stdout).")
    return stdout


def load_building_model_payload(path, converter_path=None):
    converter_path = converter_path or get_converter_exe_location()
    if path.endswith(".dff"):
        with open(path, "rb") as handle:
            return convert_binary_dff_to_json(handle.read(), converter_path)

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_building_model_payload(path, payload, converter_path=None):
    converter_path = converter_path or get_converter_exe_location()
    if path.endswith(".json"):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
        return

    binary_payload = convert_json_to_binary_dff(payload, converter_path)
    with open(path, "wb") as handle:
        handle.write(binary_payload)


def convert_anm_to_json_external(anm_path: str) -> dict:
    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

    with open(anm_path, "rb") as handle:
        binary_data = handle.read()

    process = subprocess.Popen(
        [exe, "--import"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    outs, errs = process.communicate(input=binary_data)

    stdout_text = safe_decode_console(outs)
    stderr_text = safe_decode_console(errs)

    if stderr_text:
        print("[S5Converter stderr]")
        print(stderr_text)

    if process.returncode != 0:
        raise RuntimeError(f"S5Converter Fehler:\n{stderr_text}")

    try:
        return json.loads(stdout_text)
    except Exception as exc:
        raise RuntimeError(f"S5Converter lieferte kein gueltiges JSON zurueck: {exc}")


def convert_json_to_anm_external(js: dict, anm_path: str):
    if anm_path.endswith(".json"):
        with open(anm_path, "w", encoding="utf-8") as outfile:
            json.dump(js, outfile, indent=4)
        return

    exe = get_converter_exe_location()
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"S5Converter.exe nicht gefunden: {exe}")

    process = subprocess.Popen(
        [exe, "--export"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    bytes_data = json.dumps(js).encode("utf-8")
    outs, errs = process.communicate(input=bytes_data)

    stderr_text = safe_decode_console(errs)
    if stderr_text:
        print("[S5Converter stderr]")
        print(stderr_text)

    try:
        with open(anm_path, "wb") as outfile:
            outfile.write(outs)
    except BrokenPipeError as exc:
        print("[ERROR] BrokenPipe beim Schreiben in Datei {}: {}".format(anm_path, exc))
