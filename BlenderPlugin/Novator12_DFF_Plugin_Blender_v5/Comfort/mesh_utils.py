from collections import OrderedDict


def _default_uv_entry():
    return OrderedDict((
        ("u", 0.0),
        ("v", 0.0),
    ))


def uv_layer_coordinates(uv_layer, expected_count=None):
    modern_values = getattr(uv_layer, "uv", None)
    legacy_values = getattr(uv_layer, "data", None)

    if expected_count is not None:
        if modern_values is not None and len(modern_values) == expected_count:
            return modern_values, "vector"
        if legacy_values is not None and len(legacy_values) == expected_count:
            return legacy_values, "uv"

    if modern_values is not None and len(modern_values):
        return modern_values, "vector"
    if legacy_values is not None:
        return legacy_values, "uv"
    return (), "vector"


def collect_texture_coordinates(mesh_object, vertex_count):
    texture_coordinate_sets = []
    for uv_layer in mesh_object.data.uv_layers:
        uv_values, coordinate_property = uv_layer_coordinates(
            uv_layer,
            expected_count=len(mesh_object.data.loops),
        )
        if len(uv_values) != len(mesh_object.data.loops):
            raise ValueError(
                f"Mesh '{mesh_object.name}' UV layer '{uv_layer.name}' has {len(uv_values)} "
                f"entries for {len(mesh_object.data.loops)} face corners."
            )

        layer_coordinates = [_default_uv_entry() for _ in range(vertex_count)]
        has_uvs = False

        for polygon in mesh_object.data.polygons:
            for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                uv = getattr(uv_values[loop_index], coordinate_property)
                layer_coordinates[vertex_index] = OrderedDict((
                    ("u", uv.x),
                    ("v", 1 - uv.y),
                ))
                has_uvs = True

        if has_uvs:
            texture_coordinate_sets.append(layer_coordinates)

    return texture_coordinate_sets


def build_geometry_format(mesh_object, texture_coordinate_sets):
    if not texture_coordinate_sets:
        return {
            "TriStrip": False,
            "Positions": False,
            "NumTextureCoordinates": 0,
            "PreLit": False,
            "Normals": False,
            "Light": False,
            "ModulateMaterialColor": False,
            "Native": False,
            "NativeInstance": False,
        }

    return {
        "TriStrip": True,
        "Positions": True,
        "NumTextureCoordinates": 2 if len(mesh_object.data.uv_layers) > 1 else 1,
        "PreLit": False,
        "Normals": True,
        "Light": True,
        "ModulateMaterialColor": False,
        "Native": False,
        "NativeInstance": False,
    }
