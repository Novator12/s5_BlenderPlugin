import bpy


EMPTY_GEOMETRY_NAME = "Empty-Geometry"


def resolve_geometry_mesh_object(entry):
    mesh_object = getattr(entry, "mesh_object", None)
    try:
        if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
            return bpy.data.objects.get(mesh_object.name)
    except ReferenceError:
        pass

    mesh_name = str(getattr(entry, "mesh_name", "") or "").strip()
    candidate = bpy.data.objects.get(mesh_name)
    if candidate is not None and candidate.type == "MESH" and candidate.data is not None:
        return candidate
    return None


def is_empty_geometry_entry(entry, mesh_object=None):
    if getattr(entry, "bin_mesh_data", "") == EMPTY_GEOMETRY_NAME:
        return True
    if getattr(entry, "mesh_name", "") == EMPTY_GEOMETRY_NAME and mesh_object is None:
        return True
    return False


def assigned_mesh_material_names(mesh_object):
    names = []
    errors = []
    material_slots = list(mesh_object.material_slots)
    if not material_slots:
        errors.append(f"Mesh '{mesh_object.name}' has no assigned material slots.")
        return names, errors

    for slot_index, slot in enumerate(material_slots):
        material = slot.material
        if material is None:
            errors.append(
                f"Mesh '{mesh_object.name}' material slot {slot_index + 1} is empty."
            )
            continue
        names.append(material.name)
    return names, errors


def geometry_material_status(entry):
    mesh_object = resolve_geometry_mesh_object(entry)
    tool_names = [material.name for material in entry.materials]
    if is_empty_geometry_entry(entry, mesh_object):
        return {
            "state": "EMPTY",
            "mesh_object": mesh_object,
            "scene_names": [],
            "tool_names": tool_names,
            "errors": [],
            "matches": True,
        }
    if mesh_object is None:
        return {
            "state": "MISSING_OBJECT",
            "mesh_object": None,
            "scene_names": [],
            "tool_names": tool_names,
            "errors": [f"Geometry '{entry.mesh_name}' is not linked to a mesh object."],
            "matches": False,
        }

    scene_names, errors = assigned_mesh_material_names(mesh_object)
    return {
        "state": "ERROR" if errors else "MATCH" if tool_names == scene_names else "MISMATCH",
        "mesh_object": mesh_object,
        "scene_names": scene_names,
        "tool_names": tool_names,
        "errors": errors,
        "matches": not errors and tool_names == scene_names,
    }


def sync_geometry_entry_materials(entry):
    status = geometry_material_status(entry)
    if status["state"] == "EMPTY":
        return {"changed": False, "changes": [], "errors": [], "status": status}
    if status["errors"]:
        return {
            "changed": False,
            "changes": [],
            "errors": list(status["errors"]),
            "status": status,
        }

    scene_names = status["scene_names"]
    changes = []
    while len(entry.materials) < len(scene_names):
        entry.materials.add()
        changes.append(f"added material slot {len(entry.materials)}")
    while len(entry.materials) > len(scene_names):
        removed_index = len(entry.materials) - 1
        removed_name = entry.materials[removed_index].name
        entry.materials.remove(removed_index)
        changes.append(f"removed material slot {removed_index + 1} ('{removed_name}')")

    for slot_index, scene_name in enumerate(scene_names):
        material_entry = entry.materials[slot_index]
        if material_entry.name == scene_name:
            continue
        old_name = material_entry.name
        material_entry.name = scene_name
        changes.append(
            f"slot {slot_index + 1}: '{old_name}' -> '{scene_name}'"
        )

    return {
        "changed": bool(changes),
        "changes": changes,
        "errors": [],
        "status": geometry_material_status(entry),
    }


def sync_geometry_tool_materials(scene):
    entries = list(scene.geometry_tool_items)
    statuses = [geometry_material_status(entry) for entry in entries]
    errors = []
    for entry_index, (entry, status) in enumerate(zip(entries, statuses)):
        if not status["errors"]:
            continue
        mesh_object = status["mesh_object"]
        geometry_name = mesh_object.name if mesh_object is not None else entry.mesh_name
        errors.extend(
            f"Geometry {entry_index + 1} ({geometry_name}): {message}"
            for message in status["errors"]
        )
    if errors:
        return {
            "changed_entries": [],
            "changed_count": 0,
            "errors": errors,
        }

    changed_entries = []
    for entry_index, entry in enumerate(entries):
        result = sync_geometry_entry_materials(entry)
        mesh_object = result["status"]["mesh_object"]
        geometry_name = mesh_object.name if mesh_object is not None else entry.mesh_name
        if result["changed"]:
            changed_entries.append({
                "index": entry_index,
                "name": geometry_name,
                "changes": result["changes"],
            })

    return {
        "changed_entries": changed_entries,
        "changed_count": len(changed_entries),
        "errors": errors,
    }
