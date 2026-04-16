from collections import OrderedDict


def collect_texture_coordinates(mesh_object, vertex_count):
    texture_coordinate_sets = []
    for uv_layer in mesh_object.data.uv_layers:
        layer_coordinates = [None] * vertex_count
        has_uvs = False

        for polygon in mesh_object.data.polygons:
            for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                uv = uv_layer.data[loop_index].uv
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
