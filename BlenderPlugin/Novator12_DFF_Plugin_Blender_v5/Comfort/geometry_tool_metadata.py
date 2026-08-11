import json


def write_geometry_tool_metadata(scene, geometry_data, mesh_object, empty_geometry=False, bone_index=None):
    geometry_items = getattr(scene, "geometry_tool_items", None)
    if geometry_items is None:
        return None

    geometry_entry = geometry_items.add()
    geometry_entry.mesh_name = mesh_object.name
    geometry_entry.mesh_object = mesh_object
    geometry_entry.linked_to_object = True
    geometry_entry.materials.clear()
    if bone_index is not None:
        geometry_entry.bone_index = str(bone_index)

    if empty_geometry:
        geometry_entry.bin_mesh_data = "Empty-Geometry"
        material_entry = geometry_entry.materials.add()
        material_entry.name = "Empty-Geometry"
        material_entry.ambient = False
        material_entry.specular = False
        material_entry.diffuse = False
        material_entry.uv_trans = False
        material_entry.dual_tex = False
        material_entry.snow_texture = "Empty-Geometry"
        material_entry.texture_alpha = ""
        return geometry_entry

    extension = geometry_data.get("extension", {})
    bin_mesh = extension.get("BinMeshPLG")
    if bin_mesh is None:
        geometry_entry.bin_mesh_data = "No data"
    else:
        geometry_entry.bin_mesh_data = json.dumps({
            "Flags": bin_mesh.get("Flags", {}),
            "Meshes": bin_mesh.get("Meshes", []),
        })

    for material in geometry_data.get("materials", []):
        material_entry = geometry_entry.materials.add()
        textures = material.get("textures", [])
        texture_info = textures[0] if textures else {}
        material_entry.name = texture_info.get("texture", "Unknown")
        material_entry.texture_alpha = texture_info.get("textureAlpha", "")

        surface_props = material.get("SurfaceProps", {})
        material_entry.ambient = bool(surface_props.get("ambient", 1))
        material_entry.specular = bool(surface_props.get("specular", 0))
        material_entry.diffuse = bool(surface_props.get("diffuse", 1))

        material_fx = material.get("extension", {}).get("MaterialFXMat", {})
        fx_data = material_fx.get("Data1", {})
        fx_type = fx_data.get("Type", "")
        if fx_type == "DualTexture":
            material_entry.dual_tex = True
            material_entry.snow_texture = (fx_data.get("Texture1") or {}).get("texture", "No data")
        elif fx_type == "UVTransformMat":
            material_entry.uv_trans = True
            material_entry.snow_texture = "UVTransformMat"
        else:
            material_entry.snow_texture = "No data"

    return geometry_entry
