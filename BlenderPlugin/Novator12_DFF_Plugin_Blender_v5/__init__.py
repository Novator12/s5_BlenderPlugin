# ------------------------------------------Plugin Info -----------------------------------------------------------------------------------
# pyright: reportInvalidTypeForm=false

# --- bl_info sauber für 5.x ---
bl_info = {
    "name": "Novator12 DFF Plugin Blender v5",
    "author": "Novator12",
    "version": (1, 1, 0),
    "blender": (5, 0, 0),
    "location": "File > Import-Export + View3D Sidebar",
    "description": "Import/Export fuer starre Gebaeude und Gebaeude-Animationen (Settlers 5) inkl. UserData/Particle/Geometry Tools",
    "category": "Import-Export",
}

import bmesh
import bpy
from bpy.app.handlers import persistent

# Novator Adds:
# UserDataPlg Menü und Im- & Export + UI Panel Stuff
from bpy.types import PropertyGroup
from bpy.types import UIList
from bpy.types import Panel
from bpy.types import Operator
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty

# Spherengenerator
from mathutils import Vector

# Zusatzskripte
from .building_anm_export import BuildingAnmExportOperator
from .building_anm_import import BuildingAnmImportOperator
from .unit_anm_export import UnitAnmExportOperator
from .unit_anm_import import UnitAnmImportOperator
from .building_utilities import (
    ACTION_ANIM_FPS_PROP,
    ACTION_ANIM_FORMAT_PROP,
    ACTION_EXPORT_NAME_PROP,
    ACTION_START_PREV_KEYFRAME_PROP,
    ANIM_FORMAT_COMPRESSED,
    ANIM_FORMAT_HIERARCHICAL,
    ANIM_FORMAT_NODES,
    DEFAULT_S5_FPS,
    DEFAULT_ANIM_FORMAT,
    DEFAULT_START_PREV_KEYFRAME,
    ensure_action_anim_fps,
    ensure_action_anim_format,
    ensure_action_stashed_in_muted_nla,
    parse_action_anim_fps,
    parse_action_start_prev_keyframe,
)
from .building_model_export import (
    BuildingExportOperator,
    write_building_model,
)
from .unit_model_export import (
    UnitExportOperator,
)
from .building_model_import import (
    BuildingImportOperator,
    read_building_model,
)
from .unit_model_import import (
    UnitImportOperator,
    read_unit_model,
)
# Gobals
AtomicMaterialFX_Data = {}
ParticleDataList = {}
_LAST_ACTION_SYNC_KEY = None
_LAST_ACTION_BY_OBJECT = {}


# -------------------------------------------------------Export Functions------------------------------------------
# -----------------------------------------------------------------------------------------------------------------

def import_building_model_state(path):
    global AtomicMaterialFX_Data, ParticleDataList
    AtomicMaterialFX_Data, ParticleDataList = read_building_model(path, AtomicMaterialFX_Data, ParticleDataList)


def import_unit_model_state(path):
    read_unit_model(path)


def export_building_model_state(path, bone_type_data, particle_data, geometry_data):
    write_building_model(path, bone_type_data, particle_data, geometry_data, AtomicMaterialFX_Data, ParticleDataList)


def export_unit_model_state(path, context):
    from .unit_utilities import write_unit_model

    write_unit_model(path, context)


def _get_active_armature_action(context):
    active_object = getattr(context, "object", None)
    if active_object is None or active_object.type != "ARMATURE":
        return None, None

    animation_data = getattr(active_object, "animation_data", None)
    if animation_data is None:
        return active_object, None

    return active_object, animation_data.action


def _resolve_active_action(context):
    space_data = getattr(context, "space_data", None)
    action = getattr(space_data, "action", None)
    if action is not None:
        return action

    _armature_object, action = _get_active_armature_action(context)
    return action


def _collect_action_fcurves(action):
    fcurves = []
    seen = set()

    def _append_fcurve(fc):
        if fc is None:
            return
        identifier = getattr(fc, "as_pointer", None)
        key = identifier() if callable(identifier) else id(fc)
        if key in seen:
            return
        seen.add(key)
        fcurves.append(fc)

    try:
        for fc in action.fcurves:
            _append_fcurve(fc)
    except Exception:
        pass

    try:
        slots = list(getattr(action, "slots", []))
        layers = list(getattr(action, "layers", []))
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                if slots:
                    for slot in slots:
                        try:
                            channelbag = strip.channelbag(slot)
                        except Exception:
                            continue
                        if channelbag:
                            for fc in getattr(channelbag, "fcurves", []):
                                _append_fcurve(fc)
                else:
                    try:
                        channelbag = strip.channelbag(action_slot=None)
                    except Exception:
                        channelbag = None
                    if channelbag:
                        for fc in getattr(channelbag, "fcurves", []):
                            _append_fcurve(fc)
    except Exception:
        pass

    return fcurves


def _sync_scene_range_to_action(scene, action):
    if action is None:
        return

    try:
        action_start = float(action.frame_range[0])
        action_end = float(action.frame_range[1])
    except Exception:
        return

    frame_length = max(0, int(round(action_end - action_start)))
    scene.frame_start = 0
    scene.frame_end = frame_length
    scene.frame_set(0)
    bpy.context.view_layer.update()


class ACTION_OT_apply_animation_fps(Operator):
    bl_idname = "action.apply_animation_fps"
    bl_label = "Apply FPS"

    def execute(self, context):
        action = _resolve_active_action(context)
        if action is None:
            self.report({"ERROR"}, "Keine aktive Action gefunden.")
            return {"CANCELLED"}

        try:
            target_fps = parse_action_anim_fps(action, DEFAULT_S5_FPS)
            parse_action_start_prev_keyframe(action, DEFAULT_START_PREV_KEYFRAME)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        current_fps = int(round(context.scene.render.fps)) if context.scene.render.fps > 0 else DEFAULT_S5_FPS
        if current_fps <= 0:
            current_fps = DEFAULT_S5_FPS

        scale = float(target_fps) / float(current_fps)
        if abs(scale - 1.0) > 1.0e-9:
            for fcurve in _collect_action_fcurves(action):
                for keyframe in getattr(fcurve, "keyframe_points", []):
                    keyframe.co.x *= scale
                    keyframe.handle_left.x *= scale
                    keyframe.handle_right.x *= scale
                try:
                    fcurve.update()
                except Exception:
                    pass

        scene = context.scene
        scene.render.fps = target_fps
        scene.render.fps_base = 1.0
        _sync_scene_range_to_action(scene, action)

        self.report({"INFO"}, "Animation FPS auf {} angewendet.".format(target_fps))
        return {"FINISHED"}


class ACTION_PT_animation_fps(Panel):
    bl_idname = "DOPESHEET_PT_animation_fps"
    bl_label = "Animation Tool"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation Tool"

    def draw(self, context):
        layout = self.layout
        try:
            action = _resolve_active_action(context)

            if action is None:
                layout.label(text="Keine aktive Action gefunden.")
                return

            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="Animation:")
            row.label(text=action.name)
            ensure_action_anim_format(action, DEFAULT_ANIM_FORMAT)
            col.prop(action, ACTION_ANIM_FPS_PROP, text="FPS", slider=False)
            col.prop(action, ACTION_ANIM_FORMAT_PROP, text="Anim-Type")
            col.prop(action, ACTION_START_PREV_KEYFRAME_PROP, text="Start-Prev-Keyframe", slider=False)
            layout.separator()
            layout.operator(ACTION_OT_apply_animation_fps.bl_idname, text="Apply FPS")
        except Exception as exc:
            layout.label(text="UI-Fehler im Animation Tool.")
            layout.label(text=str(exc))


@persistent
def _sync_timeline_to_selected_action(_scene=None):
    global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT

    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None:
        return

    armature_object, action = _get_active_armature_action(context)
    action_name = None if action is None else action.name_full
    object_name = None if armature_object is None else armature_object.name_full
    action_key = (object_name, action_name)

    if action_key == _LAST_ACTION_SYNC_KEY:
        return

    if armature_object is not None:
        previous_action = _LAST_ACTION_BY_OBJECT.get(object_name)
        if previous_action is not None and previous_action != action:
            try:
                ensure_action_stashed_in_muted_nla(armature_object, previous_action, clear_active=False)
            except Exception:
                pass

    _LAST_ACTION_SYNC_KEY = action_key
    if object_name is not None:
        if action is None:
            _LAST_ACTION_BY_OBJECT.pop(object_name, None)
        else:
            _LAST_ACTION_BY_OBJECT[object_name] = action
    if action is not None:
        _sync_scene_range_to_action(scene, action)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------Novator Bone Structur-Handler-------------------------------------------------------------

class BoneMappingItem(PropertyGroup):
    bone_index: StringProperty(name="Bone Index", default="")
    bone_name: StringProperty(name="Bone Name", default="")
    bone_type: EnumProperty(
        name="Type",
        items=[
            ('DECAL', "Decal", "Markiert den Bone als Decal"),
            ('BUILDING', "Building", "Markiert den Bone als Building")
        ],
        default='DECAL'
    )



class BoneMappingList(UIList):
    """UIList zur Anzeige der Bones"""
    bl_idname = "DYNAMIC_UL_bone_list"  # Dies ist der Name, auf den Blender verweist

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "bone_index", text="Idx")
            layout.prop(item, "bone_name", text="Num")
            layout.prop(item, "bone_type", text="Mat")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'


class BoneMappingPanel(Panel):
    """Panel zur Verwaltung der Bones"""
    bl_idname = "VIEW3D_PT_bone_manager"
    bl_label = "Bone Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Tools"

    def draw(self, context):
        layout = self.layout

        # UIList anzeigen
        layout.label(text="User-Data Bones (3dsmax User Properties):")
        row = layout.row()
        row.template_list(
            "DYNAMIC_UL_bone_list",  # ID der UIList
            "",
            context.scene, "bone_items",
            context.scene, "bone_active_index"
        )

        # Buttons für Hinzufügen und Entfernen
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
        new_bone.bone_type = 'DECAL'
        context.scene.bone_active_index = len(context.scene.bone_items) - 1
        return {'FINISHED'}


class RemoveBoneMappingOperator(Operator):
    bl_idname = "export_model.remove_bone_item"
    bl_label = "Remove Bone Item"

    def execute(self, context):
        index = context.scene.bone_active_index
        if 0 <= index < len(context.scene.bone_items):
            context.scene.bone_items.remove(index)
            context.scene.bone_active_index = min(index, len(context.scene.bone_items) - 1)
        return {'FINISHED'}


class ResetBoneMappingsOperator(Operator):
    bl_idname = "export_model.reset_bone_items"
    bl_label = "Reset Bones"

    def execute(self, context):
        context.scene.bone_items.clear()
        context.scene.bone_active_index = 0
        return {'FINISHED'}


# ---------------------------------------------- Novator Spheren Generator --------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class MeshProxySphereCreateOperator(bpy.types.Operator):
    """Erstellt eine Sphere und parentet sie an das ausgewählte Mesh"""
    bl_idname = "object.create_and_parent_sphere"
    bl_label = "Generate"

    # Eigenschaften für den Operator (ohne Typannotationen)
    sphere_x: bpy.props.FloatProperty(name="X", default=0.0)
    sphere_y: bpy.props.FloatProperty(name="Y", default=0.0)
    sphere_z: bpy.props.FloatProperty(name="Z", default=0.0)
    sphere_radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01)


    def execute(self, context):
        obj = context.object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh!")
            return {'CANCELLED'}
        
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # Erstelle die Sphere
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=self.sphere_radius,
            location=(self.sphere_x, self.sphere_y, self.sphere_z)
        )
        sphere = bpy.context.object
        sphere.name = "{}_Sphere".format(obj.name)
        sphere.display_type = 'WIRE'

        # Sphere parenten
        sphere.parent = obj

        # Custom Property hinzufügen
        obj["sphere_name"] = sphere.name
        sphere["linked_mesh"] = obj.name

        self.report({'INFO'}, "Sphere '{}' ceated and parented to '{}'.".format(sphere.name, obj.name))
        return {'FINISHED'}

    def invoke(self, context, event):
        obj = context.object

        if obj and obj.type == 'MESH':
            # Berechne die Weltkoordinaten der Vertices
            mesh_world_coords = [obj.matrix_world @ v.co for v in obj.data.vertices]

            # Berechne den Mittelpunkt des Meshes
            center_x = sum(coord.x for coord in mesh_world_coords) / len(mesh_world_coords)
            center_y = sum(coord.y for coord in mesh_world_coords) / len(mesh_world_coords)
            center_z = sum(coord.z for coord in mesh_world_coords) / len(mesh_world_coords)
            center = Vector((center_x, center_y, center_z))

            # Berechne den Radius der Sphere (maximale Entfernung vom Mittelpunkt zu den Vertices)
            max_distance = max((coord - center).length for coord in mesh_world_coords)

            # Setze die Standardwerte
            self.sphere_x = center.x
            self.sphere_y = center.y
            self.sphere_z = center.z
            self.sphere_radius = max_distance

        return context.window_manager.invoke_props_dialog(self)


class MeshProxySpherePanel(bpy.types.Panel):
    """Panel im N-Reiter"""
    bl_label = "Sphere Menu"
    bl_idname = "OBJECT_PT_create_sphere"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sphere Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Create Sphere:")

        # Button für die Operator-Dialogbox
        layout.operator(MeshProxySphereCreateOperator.bl_idname)


# ---------------------------------------------- Novator Particle Menü ------------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class ParticleEffectBinding(PropertyGroup):
    """Repräsentiert einen Partikeleffekt-Eintrag"""
    bone_index: StringProperty(name="Bone Index", default="")
    effect_type: EnumProperty(
        name="Effekte",
        items=[
            ('Ubisoft', "Ubisoft", "Vom Import gefundener Particle-Effect wird verwendet."),
            ('smoke10', "smoke10", "Erzeugt eine Rauchwolke am Bone mit passendem Index"),
            ('fire02', "fire02", "Feuer-Effekt"),
            ('woodchip', "woodchip", "Holzsplitter-Effekt"),
            ('PB_Weathermachine_lightning', "PB_Weathermachine_lightning", "Blitz-Effekt der Wettermaschine"),
            ('sulfur_spray', "sulfur_spray", "Schwefel-Spray-Effekt"),
            ('salimTrapIcon', "salimTrapIcon", "Effekt für Salims Falle"),
            ('TMP_resourceGold_Sparkle', "TMP_resourceGold_Sparkle", "Gold-Funkeln-Effekt"),
            ('XD_StoneSparkles', "XD_StoneSparkles", "Stein-Funkeln-Effekt"),
            ('smoke11', "smoke11", "Alternative Rauchwolke"),
            ('XF_Leaves', "XF_Leaves", "Blätterwirbel-Effekt"),
            ('smoke12', "smoke12", "Weitere Rauchvariante"),
            ('fire01', "fire01", "Feuer-Effekt (Variante 1)"),
            ('firewheel', "firewheel", "Feuerrad-Effekt (Yuki-Shurikens")
        ],
        default='smoke10'
    )


# UI-Liste
class PARTICLE_UL_effects(UIList):
    """UIList zur Anzeige der Partikeleffekte"""
    bl_idname = "DYNAMIC_UL_particle_effect_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "bone_index", text="Index")
            layout.prop(item, "effect_type", text="Type")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'


# Panel mit Liste und Plus/Minus
class PARTICLE_PT_tools(Panel):
    """Panel zur Verwaltung der Partikeleffekte"""
    bl_idname = "VIEW3D_PT_particle_manager"
    bl_label = "Particle Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Particle Tools"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Atomic-Effekte (ParticleStandard):")
        row = layout.row()
        row.template_list(
            "DYNAMIC_UL_particle_effect_list",
            "",
            context.scene, "particle_effects",
            context.scene, "particle_effects_index"
        )

        row = layout.row()
        row.operator("export_model.add_particle_effect", text="Add Effect", icon="PLUS")
        row.operator("export_model.remove_particle_effect", text="Remove Effect", icon="X")
        row.operator("export_model.reset_particle_effects", text="Reset", icon="LOOP_BACK")


# Add Operator
class PARTICLE_OT_add_effect(Operator):
    bl_idname = "export_model.add_particle_effect"
    bl_label = "Add Particle Effect"

    def execute(self, context):
        new_effect = context.scene.particle_effects.add()
        new_effect.bone_index = "999"
        new_effect.effect_type = 'smoke10'
        context.scene.particle_effects_index = len(context.scene.particle_effects) - 1
        return {'FINISHED'}


# Remove Operator
class PARTICLE_OT_remove_effect(Operator):
    bl_idname = "export_model.remove_particle_effect"
    bl_label = "Remove Particle Effect"

    def execute(self, context):
        index = context.scene.particle_effects_index
        if 0 <= index < len(context.scene.particle_effects):
            context.scene.particle_effects.remove(index)
            context.scene.particle_effects_index = min(index, len(context.scene.particle_effects) - 1)
        return {'FINISHED'}


class PARTICLE_OT_reset_effects(Operator):
    bl_idname = "export_model.reset_particle_effects"
    bl_label = "Reset Particle Effects"

    def execute(self, context):
        context.scene.particle_effects.clear()
        context.scene.particle_effects_index = 0
        return {'FINISHED'}


# ---------------------------------------------- Novator Geometry Menü ------------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class GeometryMaterialRecord(PropertyGroup):
    name: StringProperty(name="Material Name")
    uv_trans: BoolProperty(name="UVTrans", default=False)
    dual_tex: BoolProperty(name="DualTex", default=False)
    ambient: BoolProperty(name="Ambient", default=True)
    specular: BoolProperty(name="Specular", default=False)
    diffuse: BoolProperty(name="Diffuse", default=True)
    snow_texture: StringProperty(name="Snow Texture", default="No data")
    texture_alpha: StringProperty(name="Texture Alpha", default="")


class GeometryExportRecord(PropertyGroup):
    mesh_name: StringProperty(name="Mesh Name", default="No data")
    materials: CollectionProperty(type=GeometryMaterialRecord)
    bin_mesh_data: StringProperty(name="BinMesh Data", default="No data")


class GEOMETRY_UL_tool_entries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is None:
            return

        box_main = layout.box()

        # Sichtbarer Header in der Box
        box_main.label(
            text=" Geometry {} --------------------------------------------------------------------------------------------------------------------------------------------------".format(
                index + 1))

        # Mesh-Name
        box_main.prop(item, "mesh_name", text="Mesh")

        # Materialien mit eigener Box & Checkboxen
        for idx, mat in enumerate(item.materials):
            mat_box = box_main.box()
            mat_box.prop(mat, "name", text="Material {}".format(idx + 1))

            row = mat_box.row(align=True)
            row.prop(mat, "uv_trans")
            row.prop(mat, "dual_tex")

            row = mat_box.row(align=True)
            row.prop(mat, "ambient")
            row.prop(mat, "specular")
            row.prop(mat, "diffuse")

            row = mat_box.row()
            row.prop(mat, "snow_texture")
            row.prop(mat, "texture_alpha")

        # Plus / Minus Buttons für Materials
        row = box_main.row(align=True)
        add_op = row.operator("geometry_tools.add_material", icon="PLUS", text="")
        add_op.index = index
        rem_op = row.operator("geometry_tools.remove_material", icon="X", text="")
        rem_op.index = index

        # BinMesh Property
        row = box_main.row()
        row.prop(item, "bin_mesh_data", text="BinMesh")


class GEOMETRY_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_geometry_tools"
    bl_label = "Geometry Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Geometry Tools'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Geometry Data:")
        scene = context.scene

        layout.template_list("GEOMETRY_UL_tool_entries", "", scene, "geometry_tool_items", scene, "geometry_tool_index")

        row = layout.row()
        row.operator("geometry_tools.add_entry", icon="PLUS")
        row.operator("geometry_tools.remove_entry", icon="X")
        row.operator("geometry_tools.reset_entries", icon="LOOP_BACK")


class GEOMETRY_OT_add_entry(Operator):
    bl_idname = "geometry_tools.add_entry"
    bl_label = "Add Geometry Entry"

    def execute(self, context):
        context.scene.geometry_tool_items.add()
        context.scene.geometry_tool_index = len(context.scene.geometry_tool_items) - 1
        return {'FINISHED'}


class GEOMETRY_OT_remove_entry(Operator):
    bl_idname = "geometry_tools.remove_entry"
    bl_label = "Remove Geometry Entry"

    def execute(self, context):
        index = context.scene.geometry_tool_index
        if 0 <= index < len(context.scene.geometry_tool_items):
            context.scene.geometry_tool_items.remove(index)
            context.scene.geometry_tool_index = min(index, len(context.scene.geometry_tool_items) - 1)
        return {'FINISHED'}


class GEOMETRY_OT_reset_entries(Operator):
    bl_idname = "geometry_tools.reset_entries"
    bl_label = "Reset Geometry Entries"

    def execute(self, context):
        context.scene.geometry_tool_items.clear()
        context.scene.geometry_tool_index = 0
        return {'FINISHED'}


class GEOMETRY_OT_add_material(Operator):
    bl_idname = "geometry_tools.add_material"
    bl_label = "Add Material"
    index: IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        geo.materials.add()
        return {'FINISHED'}


class GEOMETRY_OT_remove_material(Operator):
    bl_idname = "geometry_tools.remove_material"
    bl_label = "Remove Material"
    index: IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        if geo.materials:
            geo.materials.remove(len(geo.materials) - 1)
        return {'FINISHED'}


def _format_index_preview(indices, limit=8):
    if not indices:
        return "-"

    preview = ", ".join(str(index) for index in indices[:limit])
    if len(indices) > limit:
        preview += ", ..."
    return preview


def _collect_loose_vertex_indices(mesh_object):
    mesh_data = mesh_object.data
    used_vertices = set()

    for polygon in mesh_data.polygons:
        used_vertices.update(polygon.vertices)

    all_vertices = set(range(len(mesh_data.vertices)))
    return sorted(all_vertices - used_vertices)


def _validate_selected_mesh_lines(context, mesh_object):
    mesh_data = mesh_object.data
    non_triangle_polygons = []
    degenerate_polygons = []
    loose_vertices = _collect_loose_vertex_indices(mesh_object)

    for polygon in mesh_data.polygons:
        polygon_vertices = list(polygon.vertices)

        if len(polygon_vertices) != 3:
            non_triangle_polygons.append(polygon.index)

        if len(set(polygon_vertices)) < len(polygon_vertices):
            degenerate_polygons.append(polygon.index)

    lines = [
        f"Mesh: {mesh_object.name}",
        f"Vertices: {len(mesh_data.vertices)} | Faces: {len(mesh_data.polygons)} | UV-Layers: {len(mesh_data.uv_layers)}",
    ]

    if non_triangle_polygons:
        lines.append(
            "ERROR: Nicht-triangulierte Faces gefunden. "
            f"Exporter nimmt nur die ersten 3 Vertices. Face-Indizes: {_format_index_preview(non_triangle_polygons)}"
        )
    else:
        lines.append("OK: Alle Faces sind trianguliert.")

    if degenerate_polygons:
        lines.append(
            "ERROR: Degenerierte Faces mit doppelten Vertex-Indizes gefunden. "
            f"Face-Indizes: {_format_index_preview(degenerate_polygons)}"
        )

    if loose_vertices:
        lines.append(
            "WARN: Lose/unbenutzte Vertices gefunden. "
            f"Vertex-Indizes: {_format_index_preview(loose_vertices)}"
        )
    else:
        lines.append("OK: Keine losen Vertices gefunden.")

    if not mesh_data.uv_layers:
        lines.append("WARN: Keine UV-Layer vorhanden.")
    else:
        tolerance = 1.0e-6
        used_vertices = set(range(len(mesh_data.vertices))) - set(loose_vertices)
        for layer_index, uv_layer in enumerate(mesh_data.uv_layers):
            vertex_to_uv = {}
            conflicting_vertices = set()

            for polygon in mesh_data.polygons:
                for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                    uv = uv_layer.data[loop_index].uv
                    uv_pair = (float(uv.x), float(uv.y))
                    previous_uv = vertex_to_uv.get(vertex_index)
                    if previous_uv is None:
                        vertex_to_uv[vertex_index] = uv_pair
                        continue

                    if (
                        abs(previous_uv[0] - uv_pair[0]) > tolerance
                        or abs(previous_uv[1] - uv_pair[1]) > tolerance
                    ):
                        conflicting_vertices.add(vertex_index)

            missing_used_vertices = sorted(vertex for vertex in used_vertices if vertex not in vertex_to_uv)
            if missing_used_vertices:
                lines.append(
                    f"ERROR: UV-Layer {layer_index} hat benutzte Vertices ohne UV. "
                    f"Vertex-Indizes: {_format_index_preview(missing_used_vertices)}"
                )
            else:
                lines.append(f"OK: UV-Layer {layer_index} deckt alle benutzten Vertices ab.")

            if conflicting_vertices:
                lines.append(
                    f"WARN: UV-Layer {layer_index} hat Vertex->UV-Konflikte an Seams. "
                    "Der Exporter speichert nur einen UV-Wert pro Vertex. "
                    f"Vertex-Indizes: {_format_index_preview(sorted(conflicting_vertices))}"
                )
            else:
                lines.append(f"OK: UV-Layer {layer_index} hat keine Vertex->UV-Konflikte.")

    return lines, loose_vertices


def _mesh_validation_icon(line):
    if line.startswith("OK:"):
        return 'CHECKMARK'
    if line.startswith("ERROR:"):
        return 'CANCEL'
    if line.startswith("WARN:"):
        return 'ERROR'
    return 'INFO'


class GEOMETRY_OT_validate_selected_mesh(Operator):
    bl_idname = "geometry_tools.validate_selected_mesh"
    bl_label = "Validate Selected Mesh"
    bl_description = "Prüft das aktive Mesh auf Export-Probleme bei UVs, Triangles und BinMesh-Daten"

    def execute(self, context):
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "Kein aktives Mesh ausgewählt.")
            return {'CANCELLED'}

        lines, loose_vertices = _validate_selected_mesh_lines(context, mesh_object)
        context.scene.s5_mesh_validation_report = "\n".join(lines)
        context.scene.s5_mesh_validation_loose_indices = ",".join(str(index) for index in loose_vertices)

        has_error = any(line.startswith("ERROR:") for line in lines)
        has_warning = any(line.startswith("WARN:") for line in lines)
        if has_error:
            self.report({"WARNING"}, "Mesh-Check abgeschlossen: Fehler gefunden. Details im Mesh Validation Panel.")
        elif has_warning:
            self.report({"INFO"}, "Mesh-Check abgeschlossen: Warnungen gefunden. Details im Mesh Validation Panel.")
        else:
            self.report({"INFO"}, "Mesh-Check abgeschlossen: Keine Probleme gefunden.")

        return {'FINISHED'}


class GEOMETRY_OT_delete_loose_vertices(Operator):
    bl_idname = "geometry_tools.delete_loose_vertices"
    bl_label = "Delete Loose Vertices"
    bl_description = "Löscht unbenutzte Vertices im aktiven Mesh"

    def execute(self, context):
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "Kein aktives Mesh ausgewählt.")
            return {'CANCELLED'}

        mesh_data = mesh_object.data
        loose_indices = _collect_loose_vertex_indices(mesh_object)
        if not loose_indices:
            context.scene.s5_mesh_validation_loose_indices = ""
            self.report({"INFO"}, "Keine losen Vertices gefunden.")
            return {'CANCELLED'}

        if mesh_object.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(mesh_data)
            bm.verts.ensure_lookup_table()
            verts_to_delete = [bm.verts[index] for index in loose_indices if index < len(bm.verts)]
            bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
            bmesh.update_edit_mesh(mesh_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(mesh_data)
            bm.verts.ensure_lookup_table()
            verts_to_delete = [bm.verts[index] for index in loose_indices if index < len(bm.verts)]
            bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
            bm.to_mesh(mesh_data)
            bm.free()
            mesh_data.update()

        lines, remaining_loose_vertices = _validate_selected_mesh_lines(context, mesh_object)
        context.scene.s5_mesh_validation_report = "\n".join(lines)
        context.scene.s5_mesh_validation_loose_indices = ",".join(str(index) for index in remaining_loose_vertices)
        self.report({"INFO"}, f"{len(loose_indices)} lose Vertices gelöscht.")
        return {'FINISHED'}


class GEOMETRY_PT_mesh_validation(Panel):
    bl_idname = "VIEW3D_PT_geometry_mesh_validation"
    bl_label = "Mesh Validation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Geometry Tools'

    def draw(self, context):
        layout = self.layout
        layout.operator(GEOMETRY_OT_validate_selected_mesh.bl_idname, icon='CHECKMARK')

        loose_indices = getattr(context.scene, "s5_mesh_validation_loose_indices", "")
        if loose_indices:
            layout.operator(GEOMETRY_OT_delete_loose_vertices.bl_idname, icon='X')

        report = getattr(context.scene, "s5_mesh_validation_report", "")
        if not report:
            layout.label(text="Noch kein Report vorhanden.")
            return

        box = layout.box()
        for line in report.splitlines():
            box.label(text=line, icon=_mesh_validation_icon(line))


# ---------------------------------------------- Delete Scene Button --------------------------------------------
# ---------------------------------------------------------------------------------------------------------------


# -------------------------------------------------------------------
# Clear Scene: Panel statt Header + 5.x hide API + lights statt lamps
# -------------------------------------------------------------------

class SCENE_OT_clear_all(bpy.types.Operator):
    bl_idname = "scene.clear_all_objects"
    bl_label = "Clear Scene"
    bl_description = "Löscht alle Objekte + unbenutzte Datenblöcke aus der Szene"

    def execute(self, context):
        global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT

        scene = context.scene

        # Tool-Listen leeren
        for op in (
            "export_model.reset_bone_items",
            "export_model.reset_particle_effects",
            "geometry_tools.reset_entries",
        ):
            try:
                bpy.ops.__getattr__(op.split(".")[0]).__getattr__(op.split(".")[1])()
            except Exception:
                pass

        # Sicher in OBJECT mode
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode='OBJECT')

        # Unhide (damit wirklich alles gelöscht werden kann)
        for obj in list(bpy.data.objects):
            try:
                obj.hide_set(False)
            except Exception:
                pass
            obj.hide_render = False
            obj.hide_select = False

        # 1) Alle Objekte aus der Datei löschen (robust, ohne Ops)
        # do_unlink=True entfernt sie aus allen Collections/Scenes
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # 2) Alle Child-Collections unter "Scene Collection" löschen
        root = scene.collection  # Root-Collection kann NICHT gelöscht werden

        def remove_children(coll):
            for child in list(coll.children):
                remove_children(child)
                bpy.data.collections.remove(child)

        remove_children(root)

        # 3) World entfernen (optional)
        if scene.world:
            w = scene.world
            scene.world = None
            if w.users == 0:
                bpy.data.worlds.remove(w)

        # 4) Alle Actions explizit entfernen, auch solche mit Fake User.
        for action in list(bpy.data.actions):
            try:
                action.use_fake_user = False
            except Exception:
                pass
            try:
                bpy.data.actions.remove(action)
            except Exception:
                pass

        _LAST_ACTION_SYNC_KEY = None
        _LAST_ACTION_BY_OBJECT = {}

        # 5) Orphans purgen (mehrfach, weil Blender nicht immer alles in einem Durchlauf entfernt)
        for _ in range(5):
            # In Blender 5 gibt’s bpy.data.orphans_purge
            res = bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
            # Wenn nix mehr gelöscht wurde: fertig
            if not res:
                break

        return {'FINISHED'}



class SCENE_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_novator_scene_tools"
    bl_label = "Novator Scene Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Scene Tools"

    def draw(self, context):
        self.layout.operator("scene.clear_all_objects", icon='TRASH')


# ---------------------------------------------- Register/ Unregister Classes -----------------------------------
# ---------------------------------------------------------------------------------------------------------------
        

# -------------------------------------------------------------------
# Register/Unregister: 5.x-only, keine Version-Branches mehr
# -------------------------------------------------------------------

CLASSES = (
    # Import/Export Operatoren
    BuildingImportOperator,
    BuildingAnmImportOperator,
    BuildingExportOperator,
    BuildingAnmExportOperator,
    UnitImportOperator,
    UnitAnmImportOperator,
    UnitExportOperator,
    UnitAnmExportOperator,
    ACTION_OT_apply_animation_fps,
    ACTION_PT_animation_fps,

    # Deine UI/Property Klassen (wie bei dir vorhanden)
    BoneMappingItem,
    BoneMappingList,
    BoneMappingPanel,
    AddBoneMappingOperator,
    RemoveBoneMappingOperator,
    ResetBoneMappingsOperator,

    MeshProxySphereCreateOperator,
    MeshProxySpherePanel,

    ParticleEffectBinding,
    PARTICLE_UL_effects,
    PARTICLE_PT_tools,
    PARTICLE_OT_add_effect,
    PARTICLE_OT_remove_effect,
    PARTICLE_OT_reset_effects,

    GeometryMaterialRecord,
    GeometryExportRecord,
    GEOMETRY_UL_tool_entries,
    GEOMETRY_PT_tools,
    GEOMETRY_OT_add_entry,
    GEOMETRY_OT_remove_entry,
    GEOMETRY_OT_reset_entries,
    GEOMETRY_OT_add_material,
    GEOMETRY_OT_remove_material,
    GEOMETRY_OT_validate_selected_mesh,
    GEOMETRY_OT_delete_loose_vertices,
    GEOMETRY_PT_mesh_validation,

    SCENE_OT_clear_all,
    SCENE_PT_tools,
)

def draw_import_building_menu_entry(self, context):
    self.layout.operator(BuildingImportOperator.bl_idname, text=BuildingImportOperator.bl_label)

def draw_import_unit_menu_entry(self, context):
    self.layout.operator(UnitImportOperator.bl_idname, text=UnitImportOperator.bl_label)

def draw_import_anm_menu_entry(self, context):
    self.layout.operator(BuildingAnmImportOperator.bl_idname, text=BuildingAnmImportOperator.bl_label)

def draw_import_unit_anm_menu_entry(self, context):
    self.layout.operator(UnitAnmImportOperator.bl_idname, text=UnitAnmImportOperator.bl_label)

def draw_export_building_menu_entry(self, context):
    self.layout.operator(BuildingExportOperator.bl_idname, text=BuildingExportOperator.bl_label)

def draw_export_unit_menu_entry(self, context):
    self.layout.operator(UnitExportOperator.bl_idname, text=UnitExportOperator.bl_label)

def draw_export_anm_menu_entry(self, context):
    self.layout.operator(BuildingAnmExportOperator.bl_idname, text=BuildingAnmExportOperator.bl_label)

def draw_export_unit_anm_menu_entry(self, context):
    self.layout.operator(UnitAnmExportOperator.bl_idname, text=UnitAnmExportOperator.bl_label)


def register_file_menu_entries():
    imp = bpy.types.TOPBAR_MT_file_import
    exp = bpy.types.TOPBAR_MT_file_export

    for fn in (
        draw_import_building_menu_entry,
        draw_import_anm_menu_entry,
        draw_import_unit_menu_entry,
        draw_import_unit_anm_menu_entry,
    ):
        try: imp.remove(fn)
        except Exception: pass
        imp.append(fn)

    for fn in (
        draw_export_building_menu_entry,
        draw_export_anm_menu_entry,
        draw_export_unit_menu_entry,
        draw_export_unit_anm_menu_entry,
    ):
        try: exp.remove(fn)
        except Exception: pass
        exp.append(fn)

def unregister_file_menu_entries():
    imp = bpy.types.TOPBAR_MT_file_import
    exp = bpy.types.TOPBAR_MT_file_export

    for fn in (
        draw_import_building_menu_entry,
        draw_import_anm_menu_entry,
        draw_import_unit_menu_entry,
        draw_import_unit_anm_menu_entry,
    ):
        try: imp.remove(fn)
        except Exception: pass

    for fn in (
        draw_export_building_menu_entry,
        draw_export_anm_menu_entry,
        draw_export_unit_menu_entry,
        draw_export_unit_anm_menu_entry,
    ):
        try: exp.remove(fn)
        except Exception: pass


def register():
    global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT

    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Scene Properties (bei dir sind die teils im “else”-Branch – in 5.x müssen die immer registriert werden)
    bpy.types.Scene.bone_items = CollectionProperty(type=BoneMappingItem)
    bpy.types.Scene.bone_active_index = IntProperty(default=0)

    bpy.types.Scene.particle_effects = CollectionProperty(type=ParticleEffectBinding)
    bpy.types.Scene.particle_effects_index = IntProperty(default=0)

    bpy.types.Scene.geometry_tool_items = CollectionProperty(type=GeometryExportRecord)
    bpy.types.Scene.geometry_tool_index = IntProperty(default=0)
    bpy.types.Scene.s5_mesh_validation_report = StringProperty(
        name="Mesh Validation Report",
        default="",
    )
    bpy.types.Scene.s5_mesh_validation_loose_indices = StringProperty(
        name="Loose Vertex Indices",
        default="",
    )

    bpy.types.Action.s5_anim_fps = StringProperty(name="FPS", default=str(DEFAULT_S5_FPS))
    bpy.types.Action.s5_anim_format = EnumProperty(
        name="Anim-Type",
        items=(
            (ANIM_FORMAT_HIERARCHICAL, "HierarchicalAnim", "Use HierarchicalAnim metadata"),
            (ANIM_FORMAT_COMPRESSED, "CompressedAnim", "Use CompressedAnim metadata"),
            (ANIM_FORMAT_NODES, "Nodes", "Use converter nodes[] metadata"),
        ),
        default=DEFAULT_ANIM_FORMAT,
    )
    bpy.types.Action.s5_export_name = StringProperty(name="Export-Name", default="")
    bpy.types.Action.s5_import_prev_keyframe = StringProperty(name="Start-Prev-Keyframe", default=str(DEFAULT_START_PREV_KEYFRAME))

    register_file_menu_entries()
    _LAST_ACTION_SYNC_KEY = None
    _LAST_ACTION_BY_OBJECT = {}
    if _sync_timeline_to_selected_action not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_sync_timeline_to_selected_action)

def unregister():
    global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT

    unregister_file_menu_entries()

    if _sync_timeline_to_selected_action in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_sync_timeline_to_selected_action)
    _LAST_ACTION_SYNC_KEY = None
    _LAST_ACTION_BY_OBJECT = {}

    # Scene Properties entfernen
    for attr in ("bone_items","bone_active_index","particle_effects","particle_effects_index","geometry_tool_items","geometry_tool_index","s5_mesh_validation_report","s5_mesh_validation_loose_indices"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    for attr in ("s5_anim_fps", "s5_anim_format", "s5_export_name", "s5_import_prev_keyframe"):
        if hasattr(bpy.types.Action, attr):
            delattr(bpy.types.Action, attr)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)



if __name__ == "__main__":
    register()



