import bpy

from bpy.props import CollectionProperty, EnumProperty, IntProperty, StringProperty

from ..building_anm_export import BuildingAnmExportOperator
from ..building_anm_import import BuildingAnmImportOperator
from ..building_model_export import BuildingExportOperator
from ..building_model_import import BuildingImportOperator
from .constants import (
    ACTION_ANIM_FPS_PROP,
    ACTION_ANIM_FORMAT_PROP,
    ACTION_EXPORT_NAME_PROP,
    ACTION_START_PREV_KEYFRAME_PROP,
    ANIM_FORMAT_ITEMS,
    DEFAULT_ANIM_FORMAT,
    DEFAULT_S5_FPS,
    DEFAULT_START_PREV_KEYFRAME,
    SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
    SCENE_MESH_VALIDATION_REPORT_PROP,
)
from .ui_animation import ACTION_OT_apply_animation_fps, ACTION_PT_animation_fps, reset_animation_ui_state, sync_timeline_to_selected_action
from .ui_properties import BoneMappingItem, GeometryExportRecord, GeometryMaterialRecord, ParticleEffectBinding
from .ui_tools import (
    AddBoneMappingOperator,
    BoneMappingList,
    BoneMappingPanel,
    GEOMETRY_OT_add_entry,
    GEOMETRY_OT_add_material,
    GEOMETRY_OT_delete_loose_vertices,
    GEOMETRY_OT_remove_entry,
    GEOMETRY_OT_remove_material,
    GEOMETRY_OT_reset_entries,
    GEOMETRY_OT_validate_selected_mesh,
    GEOMETRY_PT_mesh_validation,
    GEOMETRY_PT_tools,
    GEOMETRY_UL_tool_entries,
    MeshProxySphereCreateOperator,
    MeshProxySpherePanel,
    PARTICLE_OT_add_effect,
    PARTICLE_OT_remove_effect,
    PARTICLE_OT_reset_effects,
    PARTICLE_PT_tools,
    PARTICLE_UL_effects,
    RemoveBoneMappingOperator,
    ResetBoneMappingsOperator,
    SCENE_OT_clear_all,
    SCENE_PT_tools,
)
from ..unit_anm_export import UnitAnmExportOperator
from ..unit_anm_import import UnitAnmImportOperator
from ..unit_model_export import UnitExportOperator
from ..unit_model_import import UnitImportOperator


CLASSES = (
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
        try:
            imp.remove(fn)
        except Exception:
            pass
        imp.append(fn)

    for fn in (
        draw_export_building_menu_entry,
        draw_export_anm_menu_entry,
        draw_export_unit_menu_entry,
        draw_export_unit_anm_menu_entry,
    ):
        try:
            exp.remove(fn)
        except Exception:
            pass
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
        try:
            imp.remove(fn)
        except Exception:
            pass

    for fn in (
        draw_export_building_menu_entry,
        draw_export_anm_menu_entry,
        draw_export_unit_menu_entry,
        draw_export_unit_anm_menu_entry,
    ):
        try:
            exp.remove(fn)
        except Exception:
            pass


def register_properties():
    bpy.types.Scene.bone_items = CollectionProperty(type=BoneMappingItem)
    bpy.types.Scene.bone_active_index = IntProperty(default=0)

    bpy.types.Scene.particle_effects = CollectionProperty(type=ParticleEffectBinding)
    bpy.types.Scene.particle_effects_index = IntProperty(default=0)

    bpy.types.Scene.geometry_tool_items = CollectionProperty(type=GeometryExportRecord)
    bpy.types.Scene.geometry_tool_index = IntProperty(default=0)
    bpy.types.Scene.s5_mesh_validation_report = StringProperty(name="Mesh Validation Report", default="")
    bpy.types.Scene.s5_mesh_validation_loose_indices = StringProperty(name="Loose Vertex Indices", default="")

    bpy.types.Action.s5_anim_fps = StringProperty(name="FPS", default=str(DEFAULT_S5_FPS))
    bpy.types.Action.s5_anim_format = EnumProperty(name="Anim-Type", items=ANIM_FORMAT_ITEMS, default=DEFAULT_ANIM_FORMAT)
    bpy.types.Action.s5_export_name = StringProperty(name="Export-Name", default="")
    bpy.types.Action.s5_import_prev_keyframe = StringProperty(name="Start-Prev-Keyframe", default=str(DEFAULT_START_PREV_KEYFRAME))


def unregister_properties():
    for attr in (
        "bone_items",
        "bone_active_index",
        "particle_effects",
        "particle_effects_index",
        "geometry_tool_items",
        "geometry_tool_index",
        SCENE_MESH_VALIDATION_REPORT_PROP,
        SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
    ):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    for attr in (
        ACTION_ANIM_FPS_PROP,
        ACTION_ANIM_FORMAT_PROP,
        ACTION_EXPORT_NAME_PROP,
        ACTION_START_PREV_KEYFRAME_PROP,
    ):
        if hasattr(bpy.types.Action, attr):
            delattr(bpy.types.Action, attr)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    register_properties()
    register_file_menu_entries()
    reset_animation_ui_state()
    if sync_timeline_to_selected_action not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_timeline_to_selected_action)


def unregister():
    unregister_file_menu_entries()

    if sync_timeline_to_selected_action in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_timeline_to_selected_action)
    reset_animation_ui_state()
    unregister_properties()

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
