import bmesh
import bpy

from mathutils import Vector

from bpy.app.handlers import persistent
from bpy.props import IntProperty
from bpy.types import Operator, Panel, UIList

from .constants import (
    MESH_SPHERE_NAME_PROP,
    SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
    SCENE_MESH_VALIDATION_REPORT_PROP,
    SPHERE_EXPORT_CENTER_PROP,
    SPHERE_EXPORT_RADIUS_PROP,
    SPHERE_LINKED_MESH_PROP,
)
from .geometry_materials import geometry_material_status, sync_geometry_entry_materials
from .ui_animation import reset_animation_ui_state
from .validation_utils import (
    build_mesh_validation_lines,
    collect_loose_vertex_indices,
    mesh_validation_icon,
    validate_mesh_object,
)

_GEOMETRY_TOOL_SYNC_LOCK = False


def _ensure_object_mode(context):
    if context.mode == "EDIT_MESH" and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def _geometry_entry_mesh_object(entry):
    mesh_object = _resolve_geometry_entry_object(entry)
    if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
        return None
    return mesh_object


def _geometry_entry_mesh_name(entry, mesh_object=None):
    mesh_object = mesh_object or _geometry_entry_mesh_object(entry)
    return mesh_object.name if mesh_object is not None else entry.mesh_name


def _report_complete_mesh_validation_indices(operator, mesh_report, chunk_size=64):
    reports = []
    mesh_name = mesh_report["mesh_name"]

    if mesh_report["non_triangle_polygons"]:
        reports.append(("ERROR", "Non-triangulated face indices", mesh_report["non_triangle_polygons"]))
    if mesh_report["degenerate_polygons"]:
        reports.append(("ERROR", "Degenerate face indices", mesh_report["degenerate_polygons"]))
    if mesh_report["loose_vertices"]:
        reports.append(("WARNING", "Loose vertex indices", mesh_report["loose_vertices"]))

    for uv_layer in mesh_report["uv_layers"]:
        layer_index = uv_layer["layer_index"]
        if uv_layer["missing_used_vertices"]:
            reports.append((
                "ERROR",
                f"UV layer {layer_index} missing vertex indices",
                uv_layer["missing_used_vertices"],
            ))
        if uv_layer["conflicting_vertices"]:
            reports.append((
                "WARNING",
                f"UV layer {layer_index} Vertex->UV conflict indices",
                uv_layer["conflicting_vertices"],
            ))

    for severity, label, indices in reports:
        part_count = (len(indices) + chunk_size - 1) // chunk_size
        for part_index, offset in enumerate(range(0, len(indices), chunk_size), start=1):
            chunk = indices[offset:offset + chunk_size]
            part_label = f" (part {part_index}/{part_count})" if part_count > 1 else ""
            message = f"Mesh '{mesh_name}': {label}{part_label}: " + ", ".join(str(index) for index in chunk)
            operator.report({severity}, message)
            print(f"[Mesh Validation] {message}")


def _initialize_empty_geometry_entry(entry):
    if not entry.mesh_name or entry.mesh_name == "No data":
        entry.mesh_name = "Empty-Geometry"

    entry.bin_mesh_data = "Empty-Geometry"
    entry.materials.clear()

    material_entry = entry.materials.add()
    material_entry.name = "Empty-Geometry"
    material_entry.ambient = False
    material_entry.specular = False
    material_entry.diffuse = False
    material_entry.uv_trans = False
    material_entry.dual_tex = False
    material_entry.snow_texture = "Empty-Geometry"
    material_entry.texture_alpha = ""


def _resolve_geometry_entry_object(entry):
    mesh_object = getattr(entry, "mesh_object", None)
    if mesh_object is None:
        return None

    try:
        mesh_name = mesh_object.name
    except ReferenceError:
        return None

    return bpy.data.objects.get(mesh_name)


def sync_geometry_tool_selection(scene, context):
    if _GEOMETRY_TOOL_SYNC_LOCK or context is None:
        return

    index = getattr(scene, "geometry_tool_index", -1)
    if index < 0 or index >= len(scene.geometry_tool_items):
        return

    mesh_object = _resolve_geometry_entry_object(scene.geometry_tool_items[index])
    if mesh_object is None or mesh_object.type != "MESH":
        return

    view_layer = getattr(context, "view_layer", None)
    if view_layer is None:
        return

    active_object = view_layer.objects.active
    if active_object is not None and active_object.mode != "OBJECT" and bpy.ops.object.mode_set.poll():
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

    try:
        if mesh_object.hide_get():
            mesh_object.hide_set(False)
    except Exception:
        pass

    if getattr(mesh_object, "hide_viewport", False):
        mesh_object.hide_viewport = False

    for selected_object in list(getattr(context, "selected_objects", [])):
        if selected_object != mesh_object:
            try:
                selected_object.select_set(False)
            except Exception:
                pass

    try:
        mesh_object.select_set(True)
    except Exception:
        return

    try:
        view_layer.objects.active = mesh_object
    except Exception:
        pass


@persistent
def sync_geometry_tool_entries(scene=None):
    global _GEOMETRY_TOOL_SYNC_LOCK

    context = bpy.context
    scene = scene or getattr(context, "scene", None)
    if scene is None or not hasattr(scene, "geometry_tool_items") or _GEOMETRY_TOOL_SYNC_LOCK:
        return

    changed = False
    removed_active_entry = False
    removed_before_active = 0
    active_index = getattr(scene, "geometry_tool_index", 0)

    _GEOMETRY_TOOL_SYNC_LOCK = True
    try:
        for index in range(len(scene.geometry_tool_items) - 1, -1, -1):
            entry = scene.geometry_tool_items[index]
            mesh_object = _resolve_geometry_entry_object(entry)

            if getattr(entry, "linked_to_object", False):
                if mesh_object is None or mesh_object.type != "MESH":
                    scene.geometry_tool_items.remove(index)
                    changed = True
                    if index == active_index:
                        removed_active_entry = True
                    elif index < active_index:
                        removed_before_active += 1
                    continue

                if entry.mesh_name != mesh_object.name:
                    entry.mesh_name = mesh_object.name
                    changed = True
    finally:
        _GEOMETRY_TOOL_SYNC_LOCK = False

    if not changed:
        return

    item_count = len(scene.geometry_tool_items)
    if item_count == 0:
        scene.geometry_tool_index = 0
        return

    next_active_index = max(0, active_index - removed_before_active)
    if removed_active_entry or next_active_index >= item_count:
        next_active_index = min(next_active_index, item_count - 1)

    if next_active_index != getattr(scene, "geometry_tool_index", -1):
        scene.geometry_tool_index = next_active_index

    sync_geometry_tool_selection(scene, context)


class BoneMappingList(UIList):
    bl_idname = "DYNAMIC_UL_bone_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "bone_index", text="Idx")
            layout.prop(item, "bone_name", text="Num")
            layout.prop(item, "bone_type", text="Mat")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"


class BoneMappingPanel(Panel):
    bl_idname = "VIEW3D_PT_bone_manager"
    bl_label = "Bone Manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Bone Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="User-Data Bones (3dsmax User Properties):")
        row = layout.row()
        row.template_list("DYNAMIC_UL_bone_list", "", context.scene, "bone_items", context.scene, "bone_active_index")

        row = layout.row()
        row.operator("export_model.add_bone_item", text="Add Bone", icon="PLUS")
        row.operator("export_model.remove_bone_item", text="Remove Bone", icon="X")
        row.operator("export_model.reset_bone_items", text="Reset", icon="LOOP_BACK")


class AddBoneMappingOperator(Operator):
    bl_idname = "export_model.add_bone_item"
    bl_label = "Add Bone Item"

    def execute(self, context):
        new_bone = context.scene.bone_items.add()
        new_bone.bone_index = "999"
        new_bone.bone_name = "999"
        new_bone.bone_type = "DECAL"
        context.scene.bone_active_index = len(context.scene.bone_items) - 1
        return {"FINISHED"}


class RemoveBoneMappingOperator(Operator):
    bl_idname = "export_model.remove_bone_item"
    bl_label = "Remove Bone Item"

    def execute(self, context):
        index = context.scene.bone_active_index
        if 0 <= index < len(context.scene.bone_items):
            context.scene.bone_items.remove(index)
            context.scene.bone_active_index = min(index, len(context.scene.bone_items) - 1)
        return {"FINISHED"}


class ResetBoneMappingsOperator(Operator):
    bl_idname = "export_model.reset_bone_items"
    bl_label = "Reset Bones"

    def execute(self, context):
        context.scene.bone_items.clear()
        context.scene.bone_active_index = 0
        return {"FINISHED"}


def _collect_sphere_export_state(context):
    from ..building_model_export import collect_armature_export_state, resolve_armature_for_export

    armature_object = resolve_armature_for_export(context)
    return collect_armature_export_state(armature_object)


def _mesh_inverse_rest_matrix(mesh_object, armature_state):
    from ..building_model_export import accumulate_rest_matrix, get_bone_index_by_name

    if not mesh_object.vertex_groups:
        raise ValueError("Mesh has no vertex group.")

    bone_name = mesh_object.vertex_groups[0].name
    bone_names = armature_state["bone_names_sorted"]
    frame_index = get_bone_index_by_name(bone_names, bone_name)
    if frame_index == -1:
        raise ValueError(f"Bone '{bone_name}' was not found.")

    rest_matrix = accumulate_rest_matrix(
        armature_state["rest_matrices"],
        armature_state["hierarchy"],
        frame_index,
    )
    return rest_matrix.inverted()


def _calculate_mesh_export_sphere(mesh_object, armature_state):
    if mesh_object.data is None or not mesh_object.data.vertices:
        raise ValueError("Mesh has no vertices.")

    inverse_rest_matrix = _mesh_inverse_rest_matrix(mesh_object, armature_state)
    mesh_coordinates = [vertex.co.copy() for vertex in mesh_object.data.vertices]
    min_corner = Vector(tuple(min(coordinate[axis] for coordinate in mesh_coordinates) for axis in range(3)))
    max_corner = Vector(tuple(max(coordinate[axis] for coordinate in mesh_coordinates) for axis in range(3)))
    display_center = (min_corner + max_corner) / 2.0
    export_center = (inverse_rest_matrix @ display_center.to_4d()).to_3d()
    export_coordinates = [
        (inverse_rest_matrix @ vertex.co.to_4d()).to_3d()
        for vertex in mesh_object.data.vertices
    ]
    radius = max((coordinate - export_center).length for coordinate in export_coordinates)
    return display_center, export_center, max(radius, 0.01)


def _is_sphere_proxy(mesh_object, child):
    stored_sphere_name = mesh_object.get(MESH_SPHERE_NAME_PROP, "")
    linked_mesh_name = child.get(SPHERE_LINKED_MESH_PROP, "")
    return (
        child.name == stored_sphere_name
        or linked_mesh_name == mesh_object.name
        or (child.type == "MESH" and child.data and child.data.name.startswith("Sphere"))
    )


def _delete_mesh_sphere_proxies(mesh_object):
    for child in list(mesh_object.children):
        if not _is_sphere_proxy(mesh_object, child):
            continue
        mesh_data = child.data if child.type == "MESH" else None
        bpy.data.objects.remove(child, do_unlink=True)
        if mesh_data is not None and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    if MESH_SPHERE_NAME_PROP in mesh_object:
        del mesh_object[MESH_SPHERE_NAME_PROP]


def _create_mesh_sphere_proxy(
    context,
    mesh_object,
    display_center,
    export_center,
    display_radius,
):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=display_radius, location=(0.0, 0.0, 0.0))
    sphere = context.object
    sphere.name = f"{mesh_object.name}_Sphere"
    sphere.data.name = f"Sphere_{mesh_object.name}"
    sphere.parent = mesh_object
    sphere.location = display_center
    sphere.display_type = "WIRE"
    sphere.hide_render = True
    sphere.hide_set(True)
    mesh_object[MESH_SPHERE_NAME_PROP] = sphere.name
    sphere[SPHERE_LINKED_MESH_PROP] = mesh_object.name
    sphere[SPHERE_EXPORT_CENTER_PROP] = list(export_center)
    sphere[SPHERE_EXPORT_RADIUS_PROP] = display_radius
    return sphere


def _restore_active_object(context, active_object, selected_objects, mode="OBJECT"):
    if active_object is None or active_object.name not in bpy.data.objects:
        return

    for selected_object in list(context.selected_objects):
        selected_object.select_set(False)
    for selected_object in selected_objects:
        if selected_object.name in bpy.data.objects:
            selected_object.select_set(True)

    active_object.select_set(True)
    context.view_layer.objects.active = active_object
    if mode != "OBJECT" and bpy.ops.object.mode_set.poll():
        try:
            bpy.ops.object.mode_set(mode=mode)
        except RuntimeError:
            pass


class MeshProxySphereCreateOperator(Operator):
    bl_idname = "object.create_and_parent_sphere"
    bl_label = "Generate"

    sphere_x: bpy.props.FloatProperty(name="X", default=0.0)
    sphere_y: bpy.props.FloatProperty(name="Y", default=0.0)
    sphere_z: bpy.props.FloatProperty(name="Z", default=0.0)
    sphere_radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01)

    def execute(self, context):
        obj = context.object
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Please select a mesh!")
            return {"CANCELLED"}

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            armature_state = _collect_sphere_export_state(context)
            _display_center, export_center, _radius = _calculate_mesh_export_sphere(obj, armature_state)
            display_center = Vector((self.sphere_x, self.sphere_y, self.sphere_z))

            inverse_rest_matrix = _mesh_inverse_rest_matrix(obj, armature_state)
            export_center = (inverse_rest_matrix @ display_center.to_4d()).to_3d()
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, f"Sphere calculation failed: {exc}")
            return {"CANCELLED"}

        _delete_mesh_sphere_proxies(obj)
        sphere = _create_mesh_sphere_proxy(
            context,
            obj,
            display_center,
            export_center,
            self.sphere_radius,
        )

        self.report({"INFO"}, "Sphere '{}' created and parented to '{}'.".format(sphere.name, obj.name))
        return {"FINISHED"}

    def invoke(self, context, event):
        obj = context.object
        if obj and obj.type == "MESH":
            selected_objects = list(context.selected_objects)
            original_mode = obj.mode
            try:
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode="OBJECT")
                armature_state = _collect_sphere_export_state(context)
                display_center, _export_center, radius = _calculate_mesh_export_sphere(obj, armature_state)
            except (RuntimeError, ValueError) as exc:
                self.report({"ERROR"}, f"Sphere calculation failed: {exc}")
                _restore_active_object(context, obj, selected_objects, original_mode)
                return {"CANCELLED"}

            self.sphere_x, self.sphere_y, self.sphere_z = display_center
            self.sphere_radius = radius
            _restore_active_object(context, obj, selected_objects)

        return context.window_manager.invoke_props_dialog(self)


class MeshProxySphereValidateAllOperator(Operator):
    bl_idname = "object.validate_all_mesh_spheres"
    bl_label = "Validate All Spheres"
    bl_description = "Recalculates and replaces the export sphere for every linked Geometry mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(getattr(context.scene, "geometry_tool_items", None))

    def execute(self, context):
        active_object = context.view_layer.objects.active
        selected_objects = list(context.selected_objects)
        original_mode = active_object.mode if active_object is not None else "OBJECT"
        rebuilt_count = 0
        skipped = []
        seen_objects = set()

        try:
            if active_object is not None and bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode="OBJECT")
            armature_state = _collect_sphere_export_state(context)

            for entry in context.scene.geometry_tool_items:
                mesh_object = _geometry_entry_mesh_object(entry)
                if mesh_object is None or mesh_object.name in seen_objects:
                    continue
                seen_objects.add(mesh_object.name)

                try:
                    display_center, export_center, radius = _calculate_mesh_export_sphere(mesh_object, armature_state)
                except (RuntimeError, ValueError) as exc:
                    skipped.append(f"{mesh_object.name}: {exc}")
                    continue

                _delete_mesh_sphere_proxies(mesh_object)
                _create_mesh_sphere_proxy(context, mesh_object, display_center, export_center, radius)
                rebuilt_count += 1
        except RuntimeError as exc:
            self.report({"ERROR"}, f"Sphere validation failed: {exc}")
            return {"CANCELLED"}
        finally:
            _restore_active_object(context, active_object, selected_objects, original_mode)

        if skipped:
            print("[Sphere Validation] Skipped entries:")
            for message in skipped:
                print(f"  {message}")
            self.report({"WARNING"}, f"Rebuilt {rebuilt_count} spheres; skipped {len(skipped)} meshes. See console for details.")
        else:
            self.report({"INFO"}, f"Rebuilt {rebuilt_count} spheres.")
        return {"FINISHED"}


class MeshProxySpherePanel(Panel):
    bl_label = "Sphere Menu"
    bl_idname = "OBJECT_PT_create_sphere"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sphere Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Create Sphere:")
        layout.operator(MeshProxySphereCreateOperator.bl_idname)
        layout.separator()
        layout.label(text="Validate all Spheres:")
        layout.operator(MeshProxySphereValidateAllOperator.bl_idname, text="Validate")


class PARTICLE_UL_effects(UIList):
    bl_idname = "DYNAMIC_UL_particle_effect_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            layout.prop(item, "bone_index", text="Index")
            layout.prop(item, "effect_type", text="Type")
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"


class PARTICLE_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_particle_manager"
    bl_label = "Particle Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Particle Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Atomic-Effekte (ParticleStandard):")
        row = layout.row()
        row.template_list(
            "DYNAMIC_UL_particle_effect_list",
            "",
            context.scene,
            "particle_effects",
            context.scene,
            "particle_effects_index",
        )

        row = layout.row()
        row.operator("export_model.add_particle_effect", text="Add Effect", icon="PLUS")
        row.operator("export_model.remove_particle_effect", text="Remove Effect", icon="X")
        row.operator("export_model.reset_particle_effects", text="Reset", icon="LOOP_BACK")


class PARTICLE_OT_add_effect(Operator):
    bl_idname = "export_model.add_particle_effect"
    bl_label = "Add Particle Effect"

    def execute(self, context):
        new_effect = context.scene.particle_effects.add()
        new_effect.bone_index = "999"
        new_effect.effect_type = "smoke10"
        context.scene.particle_effects_index = len(context.scene.particle_effects) - 1
        return {"FINISHED"}


class PARTICLE_OT_remove_effect(Operator):
    bl_idname = "export_model.remove_particle_effect"
    bl_label = "Remove Particle Effect"

    def execute(self, context):
        index = context.scene.particle_effects_index
        if 0 <= index < len(context.scene.particle_effects):
            context.scene.particle_effects.remove(index)
            context.scene.particle_effects_index = min(index, len(context.scene.particle_effects) - 1)
        return {"FINISHED"}


class PARTICLE_OT_reset_effects(Operator):
    bl_idname = "export_model.reset_particle_effects"
    bl_label = "Reset Particle Effects"

    def execute(self, context):
        context.scene.particle_effects.clear()
        context.scene.particle_effects_index = 0
        return {"FINISHED"}


class GEOMETRY_UL_tool_entries(UIList):
    bl_idname = "GEOMETRY_UL_tool_entries"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is None:
            return

        if self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text=str(index + 1), icon="MESH_DATA")
            return

        status = geometry_material_status(item)
        mesh_object = status["mesh_object"]
        display_name = mesh_object.name if mesh_object is not None else item.mesh_name
        object_icon = "MESH_DATA" if mesh_object is not None else "EMPTY_AXIS"

        row = layout.row(align=True)
        index_row = row.row(align=True)
        index_row.ui_units_x = 2.4
        index_row.label(text=f"{index + 1:02d}", icon=object_icon)
        row.label(text=display_name)

        status_row = row.row(align=True)
        status_row.alignment = "RIGHT"
        if status["state"] in {"ERROR", "MISSING_OBJECT"}:
            status_row.label(text="", icon="ERROR")
        elif status["state"] == "MISMATCH":
            status_row.label(text="", icon="FILE_REFRESH")
        elif status["state"] == "EMPTY":
            status_row.label(text="", icon="PARTICLES")
        else:
            status_row.label(text="", icon="CHECKMARK")
        status_row.label(text=str(len(item.materials)), icon="MATERIAL")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = bpy.types.UI_UL_list.filter_items_by_name(
            self.filter_name,
            self.bitflag_filter_item,
            items,
            "mesh_name",
            reverse=self.use_filter_invert,
        )
        return flags, []


def _draw_geometry_materials(layout, entry, entry_index, status):
    header = layout.row(align=True)
    header.label(text=f"Materials ({len(entry.materials)})", icon="MATERIAL")
    header.operator(
        "geometry_tools.sync_materials_from_mesh",
        icon="FILE_REFRESH",
        text="Sync from Mesh",
    )
    add_op = header.operator("geometry_tools.add_material", icon="PLUS", text="")
    add_op.index = entry_index
    remove_op = header.operator("geometry_tools.remove_material", icon="X", text="")
    remove_op.index = entry_index

    if status["state"] == "MISMATCH":
        warning = layout.row()
        warning.alert = True
        warning.label(
            text="Geometry material names differ from the Scene mesh and will be synchronized on export.",
            icon="FILE_REFRESH",
        )
    elif status["errors"]:
        warning = layout.row()
        warning.alert = True
        warning.label(text=status["errors"][0], icon="ERROR")

    if not entry.materials:
        layout.label(text="No Geometry materials configured.", icon="INFO")
        return

    scene_names = status["scene_names"]
    for material_index, material in enumerate(entry.materials):
        material_box = layout.box()
        material_header = material_box.row(align=True)
        material_header.label(text=f"Slot {material_index + 1}", icon="MATERIAL")
        if material_index < len(scene_names) and material.name != scene_names[material_index]:
            material_header.label(text=f"Scene: {scene_names[material_index]}", icon="FILE_REFRESH")

        material_box.prop(material, "name", text="Material Name")

        effects = material_box.row(align=True)
        effects.prop(material, "uv_trans", toggle=True)
        effects.prop(material, "dual_tex", toggle=True)

        lighting = material_box.row(align=True)
        lighting.prop(material, "ambient", toggle=True)
        lighting.prop(material, "specular", toggle=True)
        lighting.prop(material, "diffuse", toggle=True)

        material_box.prop(material, "snow_texture", text="Snow Texture")
        material_box.prop(material, "texture_alpha", text="Texture Alpha")


def _draw_geometry_entry_details(layout, entry, entry_index):
    status = geometry_material_status(entry)
    mesh_object = status["mesh_object"]
    display_name = mesh_object.name if mesh_object is not None else entry.mesh_name

    detail = layout.box()
    detail.use_property_split = True
    detail.use_property_decorate = False

    header = detail.row(align=True)
    geometry_icon = "PARTICLES" if status["state"] == "EMPTY" else "MESH_DATA"
    header.label(text=f"Geometry {entry_index + 1}: {display_name}", icon=geometry_icon)
    if status["state"] == "MATCH":
        header.label(text="Materials synced", icon="CHECKMARK")
    elif status["state"] == "MISMATCH":
        header.label(text="Sync required", icon="FILE_REFRESH")
    elif status["state"] in {"ERROR", "MISSING_OBJECT"}:
        header.label(text="Invalid Scene materials", icon="ERROR")
    else:
        header.label(text="Empty Geometry", icon="PARTICLES")

    detail.prop(entry, "mesh_object", text="Scene Object")

    mesh_row = detail.row()
    mesh_row.enabled = not entry.linked_to_object
    mesh_row.prop(entry, "mesh_name", text="Mesh Name")

    bone_row = detail.row()
    bone_row.enabled = not entry.linked_to_object or status["state"] == "EMPTY"
    bone_row.prop(entry, "bone_index", text="Bone Index")

    detail.separator()
    _draw_geometry_materials(detail, entry, entry_index, status)

    detail.separator()
    bin_mesh_box = detail.box()
    bin_mesh_header = bin_mesh_box.row(align=True)
    bin_mesh_header.label(text="BinMesh Data", icon="MOD_TRIANGULATE")
    if entry.bin_mesh_data == "Empty-Geometry":
        bin_mesh_header.label(text="Empty Geometry", icon="PARTICLES")
    elif entry.bin_mesh_data in {"", "No data"}:
        bin_mesh_header.label(text="Not generated", icon="INFO")
    else:
        bin_mesh_header.label(text="Stored", icon="CHECKMARK")
    bin_mesh_box.prop(entry, "bin_mesh_data", text="")


class GEOMETRY_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_geometry_tools"
    bl_label = "Geometry Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Geometry Tools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        info_box = layout.box()
        info_box.label(
            text="For particle effects, use an Empty Geometry entry and assign its Bone Index.",
            icon="INFO",
        )

        list_header = layout.row(align=True)
        list_header.label(text="Geometries", icon="OUTLINER_OB_MESH")
        list_header.label(text=str(len(scene.geometry_tool_items)))

        list_row = layout.row()
        list_row.template_list(
            "GEOMETRY_UL_tool_entries",
            "geometry_entries",
            scene,
            "geometry_tool_items",
            scene,
            "geometry_tool_index",
            rows=7,
            maxrows=10,
        )
        actions = list_row.column(align=True)
        actions.operator("geometry_tools.add_entry", icon="PLUS", text="")
        actions.operator("geometry_tools.remove_entry", icon="X", text="")
        actions.separator()
        actions.operator("geometry_tools.reset_entries", icon="LOOP_BACK", text="")

        if not scene.geometry_tool_items:
            layout.label(text="No Geometry entries. Select a mesh and add one.", icon="INFO")
            return

        entry_index = min(max(scene.geometry_tool_index, 0), len(scene.geometry_tool_items) - 1)
        _draw_geometry_entry_details(
            layout,
            scene.geometry_tool_items[entry_index],
            entry_index,
        )


class GEOMETRY_OT_sync_materials_from_mesh(Operator):
    bl_idname = "geometry_tools.sync_materials_from_mesh"
    bl_label = "Sync Materials from Mesh"
    bl_description = "Copies material slot names and count from the active Geometry mesh; Snow Texture is preserved"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        entry_index = scene.geometry_tool_index
        if entry_index < 0 or entry_index >= len(scene.geometry_tool_items):
            self.report({"ERROR"}, "No Geometry entry selected.")
            return {"CANCELLED"}

        entry = scene.geometry_tool_items[entry_index]
        result = sync_geometry_entry_materials(entry)
        if result["errors"]:
            for message in result["errors"]:
                print(f"[Geometry Materials] ERROR: {message}")
            self.report({"ERROR"}, result["errors"][0])
            return {"CANCELLED"}
        if result["status"]["state"] == "EMPTY":
            self.report({"INFO"}, "Empty Geometry does not require Scene material synchronization.")
            return {"FINISHED"}
        if not result["changed"]:
            self.report({"INFO"}, "Geometry materials already match the Scene mesh.")
            return {"FINISHED"}

        for change in result["changes"]:
            print(f"[Geometry Materials] Geometry {entry_index + 1}: {change}")
        self.report(
            {"INFO"},
            f"Synchronized {len(result['changes'])} material changes from the Scene mesh.",
        )
        return {"FINISHED"}


class GEOMETRY_OT_add_entry(Operator):
    bl_idname = "geometry_tools.add_entry"
    bl_label = "Add Geometry Entry"

    def execute(self, context):
        geometry_entry = context.scene.geometry_tool_items.add()
        mesh_object = context.active_object
        if mesh_object is not None and mesh_object.type == "MESH":
            geometry_entry.mesh_name = mesh_object.name
            geometry_entry.mesh_object = mesh_object
            geometry_entry.linked_to_object = True
            sync_result = sync_geometry_entry_materials(geometry_entry)
            if sync_result["errors"]:
                self.report({"WARNING"}, sync_result["errors"][0])
        else:
            _initialize_empty_geometry_entry(geometry_entry)
        context.scene.geometry_tool_index = len(context.scene.geometry_tool_items) - 1
        return {"FINISHED"}


class GEOMETRY_OT_remove_entry(Operator):
    bl_idname = "geometry_tools.remove_entry"
    bl_label = "Remove Geometry Entry"

    def execute(self, context):
        index = context.scene.geometry_tool_index
        if 0 <= index < len(context.scene.geometry_tool_items):
            context.scene.geometry_tool_items.remove(index)
            context.scene.geometry_tool_index = min(index, len(context.scene.geometry_tool_items) - 1)
        return {"FINISHED"}


class GEOMETRY_OT_reset_entries(Operator):
    bl_idname = "geometry_tools.reset_entries"
    bl_label = "Reset Geometry Entries"

    def execute(self, context):
        context.scene.geometry_tool_items.clear()
        context.scene.geometry_tool_index = 0
        return {"FINISHED"}


class GEOMETRY_OT_add_material(Operator):
    bl_idname = "geometry_tools.add_material"
    bl_label = "Add Material"
    index: IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        geo.materials.add()
        return {"FINISHED"}


class GEOMETRY_OT_remove_material(Operator):
    bl_idname = "geometry_tools.remove_material"
    bl_label = "Remove Material"
    index: IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        if geo.materials:
            geo.materials.remove(len(geo.materials) - 1)
        return {"FINISHED"}


class GEOMETRY_OT_validate_selected_mesh(Operator):
    bl_idname = "geometry_tools.validate_selected_mesh"
    bl_label = "Validate Selected Mesh"
    bl_description = "Checks the active mesh for topology, loose vertices, and basic UV problems"

    def execute(self, context):
        _ensure_object_mode(context)
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "No active mesh selected.")
            return {"CANCELLED"}

        mesh_report = validate_mesh_object(mesh_object)
        lines = build_mesh_validation_lines(mesh_report)
        _report_complete_mesh_validation_indices(self, mesh_report)
        setattr(context.scene, SCENE_MESH_VALIDATION_REPORT_PROP, "\n".join(lines))
        setattr(
            context.scene,
            SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
            ",".join(str(index) for index in mesh_report["loose_vertices"]),
        )

        has_error = any(line.startswith("ERROR:") for line in lines)
        has_warning = any(line.startswith("WARN:") for line in lines)
        if has_error:
            self.report({"WARNING"}, "Mesh validation found errors. See Mesh Validation.")
        elif has_warning:
            self.report({"INFO"}, "Mesh validation found warnings. See Mesh Validation.")
        else:
            self.report({"INFO"}, "Mesh validation passed.")
        return {"FINISHED"}


class GEOMETRY_OT_delete_loose_vertices(Operator):
    bl_idname = "geometry_tools.delete_loose_vertices"
    bl_label = "Delete Loose Vertices"
    bl_description = "Deletes unused vertices from the active mesh"

    def execute(self, context):
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "No active mesh selected.")
            return {"CANCELLED"}

        mesh_data = mesh_object.data
        loose_indices = collect_loose_vertex_indices(mesh_object)
        if not loose_indices:
            setattr(context.scene, SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP, "")
            self.report({"INFO"}, "No loose vertices found.")
            return {"CANCELLED"}

        if mesh_object.mode == "EDIT":
            bm = bmesh.from_edit_mesh(mesh_data)
            bm.verts.ensure_lookup_table()
            verts_to_delete = [bm.verts[index] for index in loose_indices if index < len(bm.verts)]
            bmesh.ops.delete(bm, geom=verts_to_delete, context="VERTS")
            bmesh.update_edit_mesh(mesh_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(mesh_data)
            bm.verts.ensure_lookup_table()
            verts_to_delete = [bm.verts[index] for index in loose_indices if index < len(bm.verts)]
            bmesh.ops.delete(bm, geom=verts_to_delete, context="VERTS")
            bm.to_mesh(mesh_data)
            bm.free()
            mesh_data.update()

        mesh_report = validate_mesh_object(mesh_object)
        lines = build_mesh_validation_lines(mesh_report)
        setattr(context.scene, SCENE_MESH_VALIDATION_REPORT_PROP, "\n".join(lines))
        setattr(
            context.scene,
            SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
            ",".join(str(index) for index in mesh_report["loose_vertices"]),
        )
        self.report({"INFO"}, f"Deleted {len(loose_indices)} loose vertices.")
        return {"FINISHED"}


class GEOMETRY_PT_mesh_validation(Panel):
    bl_idname = "VIEW3D_PT_geometry_mesh_validation"
    bl_label = "Mesh Validation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Geometry Tools"

    def draw(self, context):
        layout = self.layout
        layout.operator(GEOMETRY_OT_validate_selected_mesh.bl_idname, icon="CHECKMARK")

        loose_indices = getattr(context.scene, SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP, "")
        if loose_indices:
            layout.operator(GEOMETRY_OT_delete_loose_vertices.bl_idname, icon="X")

        report = getattr(context.scene, SCENE_MESH_VALIDATION_REPORT_PROP, "")
        if not report:
            layout.label(text="No mesh validation report available.")
            return

        box = layout.box()
        for line in report.splitlines():
            box.label(text=line, icon=mesh_validation_icon(line))


class SCENE_OT_clear_all(Operator):
    bl_idname = "scene.clear_all_objects"
    bl_label = "Clear Scene"
    bl_description = "Loescht alle Objekte + unbenutzte Datenbloecke aus der Szene"

    def execute(self, context):
        scene = context.scene

        for op in (
            "export_model.reset_bone_items",
            "export_model.reset_particle_effects",
            "geometry_tools.reset_entries",
        ):
            try:
                bpy.ops.__getattr__(op.split(".")[0]).__getattr__(op.split(".")[1])()
            except Exception:
                pass

        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode="OBJECT")

        for obj in list(bpy.data.objects):
            try:
                obj.hide_set(False)
            except Exception:
                pass
            obj.hide_render = False
            obj.hide_select = False

        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        root = scene.collection

        def remove_children(coll):
            for child in list(coll.children):
                remove_children(child)
                bpy.data.collections.remove(child)

        remove_children(root)

        if scene.world:
            world = scene.world
            scene.world = None
            if world.users == 0:
                bpy.data.worlds.remove(world)

        for action in list(bpy.data.actions):
            try:
                action.use_fake_user = False
            except Exception:
                pass
            try:
                bpy.data.actions.remove(action)
            except Exception:
                pass

        reset_animation_ui_state()
        for _ in range(5):
            result = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            if not result:
                break

        return {"FINISHED"}


class SCENE_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_novator_scene_tools"
    bl_label = "Novator Scene Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Scene Tools"

    def draw(self, context):
        self.layout.operator("scene.clear_all_objects", icon="TRASH")
