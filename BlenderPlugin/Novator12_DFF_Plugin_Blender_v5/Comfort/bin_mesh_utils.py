import json

from collections import Counter, OrderedDict


DEFAULT_BIN_MESH_FLAGS = OrderedDict((
    ("UnIndexed", False),
    ("Type", "TriStrip"),
))


def empty_bin_mesh():
    return OrderedDict((
        ("Flags", OrderedDict(DEFAULT_BIN_MESH_FLAGS)),
        ("Meshes", []),
    ))


def canonicalize_bin_mesh(bin_mesh):
    flags = bin_mesh.get("Flags", {}) if isinstance(bin_mesh, dict) else {}
    meshes = bin_mesh.get("Meshes", []) if isinstance(bin_mesh, dict) else []

    canonical_meshes = []
    if isinstance(meshes, list):
        for mesh in meshes:
            if not isinstance(mesh, dict):
                continue
            vertex_indices = mesh.get("VertexIndices", [])
            canonical_meshes.append(OrderedDict((
                ("MaterialIndex", mesh.get("MaterialIndex")),
                ("VertexIndices", list(vertex_indices) if isinstance(vertex_indices, list) else vertex_indices),
            )))

    return OrderedDict((
        ("Flags", OrderedDict((
            ("UnIndexed", flags.get("UnIndexed")),
            ("Type", flags.get("Type")),
        ))),
        ("Meshes", canonical_meshes),
    ))


def bin_mesh_to_json(bin_mesh):
    return json.dumps(canonicalize_bin_mesh(bin_mesh), separators=(",", ":"))


def _triangle_counter_from_mesh(mesh_object):
    triangles = Counter()
    non_triangle_faces = []
    for polygon in mesh_object.data.polygons:
        vertices = tuple(int(index) for index in polygon.vertices)
        if len(vertices) != 3:
            non_triangle_faces.append(polygon.index)
            continue
        triangles[(int(polygon.material_index), tuple(sorted(vertices)))] += 1
    return triangles, non_triangle_faces


def _triangle_counter_from_strips(meshes):
    triangles = Counter()
    for mesh in meshes:
        material_index = mesh["MaterialIndex"]
        vertex_indices = mesh["VertexIndices"]
        for index in range(len(vertex_indices) - 2):
            triangle = vertex_indices[index:index + 3]
            if len(set(triangle)) < 3:
                continue
            triangles[(material_index, tuple(sorted(triangle)))] += 1
    return triangles


def validate_bin_mesh(mesh_object, bin_mesh_value, material_count=None):
    errors = []
    parsed = bin_mesh_value
    if isinstance(bin_mesh_value, str):
        if not bin_mesh_value or bin_mesh_value in {"No data", "Empty-Geometry"}:
            parsed = empty_bin_mesh()
        else:
            try:
                parsed = json.loads(bin_mesh_value)
            except (TypeError, json.JSONDecodeError) as exc:
                return {
                    "valid": False,
                    "errors": [f"BinMesh is not valid JSON: {exc}"],
                    "bin_mesh": None,
                }

    if not isinstance(parsed, dict):
        return {
            "valid": False,
            "errors": ["BinMesh must be a JSON object."],
            "bin_mesh": None,
        }

    flags = parsed.get("Flags")
    if not isinstance(flags, dict):
        errors.append("Flags is missing or is not an object.")
        flags = {}
    if flags.get("UnIndexed") is not False:
        errors.append("Flags.UnIndexed must be false.")
    if flags.get("Type") != "TriStrip":
        errors.append("Flags.Type must be 'TriStrip'.")

    meshes = parsed.get("Meshes")
    validated_meshes = []
    vertex_count = len(mesh_object.data.vertices)
    if not isinstance(meshes, list):
        errors.append("Meshes is missing or is not a list.")
        meshes = []

    for mesh_index, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            errors.append(f"Meshes[{mesh_index}] is not an object.")
            continue

        material_index = mesh.get("MaterialIndex")
        if isinstance(material_index, bool) or not isinstance(material_index, int):
            errors.append(f"Meshes[{mesh_index}].MaterialIndex must be an integer.")
            continue
        if material_index < 0:
            errors.append(f"Meshes[{mesh_index}].MaterialIndex is negative.")
        if material_count is not None and material_index >= material_count:
            errors.append(
                f"Meshes[{mesh_index}].MaterialIndex {material_index} is outside the {material_count} materials."
            )

        vertex_indices = mesh.get("VertexIndices")
        if not isinstance(vertex_indices, list):
            errors.append(f"Meshes[{mesh_index}].VertexIndices must be a list.")
            continue

        normalized_indices = []
        for strip_index, vertex_index in enumerate(vertex_indices):
            if isinstance(vertex_index, bool) or not isinstance(vertex_index, int):
                errors.append(
                    f"Meshes[{mesh_index}].VertexIndices[{strip_index}] must be an integer."
                )
                continue
            if vertex_index < 0 or vertex_index >= vertex_count:
                errors.append(
                    f"Meshes[{mesh_index}].VertexIndices[{strip_index}]={vertex_index} is outside 0..{vertex_count - 1}."
                )
            normalized_indices.append(vertex_index)

        validated_meshes.append({
            "MaterialIndex": material_index,
            "VertexIndices": normalized_indices,
        })

    expected_triangles, non_triangle_faces = _triangle_counter_from_mesh(mesh_object)
    if non_triangle_faces:
        preview = ", ".join(str(index) for index in non_triangle_faces[:8])
        if len(non_triangle_faces) > 8:
            preview += ", ..."
        errors.append(f"Mesh is not triangulated. Face indices: {preview}")

    if not errors:
        strip_triangles = _triangle_counter_from_strips(validated_meshes)
        missing = expected_triangles - strip_triangles
        unexpected = strip_triangles - expected_triangles
        if missing or unexpected:
            errors.append(
                "TriStrip topology does not match the mesh "
                f"(missing triangles: {sum(missing.values())}, unexpected triangles: {sum(unexpected.values())})."
            )

    return {
        "valid": not errors,
        "errors": errors,
        "bin_mesh": canonicalize_bin_mesh(parsed),
    }
