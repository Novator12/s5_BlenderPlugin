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

import bpy

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
from .building_anm_export import BuildingAnmExportOperator, BuildingAnmJsonExportOperator
from .building_anm_import import BuildingAnmImportOperator, BuildingAnmJsonImportOperator
from .building_model_export import (
    BuildingDffExportOperator,
    BuildingDffJsonExportOperator,
    write_building_model,
)
from .building_model_import import (
    BuildingDffImportOperator,
    BuildingDffJsonImportOperator,
    read_building_model,
)
# Gobals
AtomicMaterialFX_Data = {}
ParticleDataList = {}


# -------------------------------------------------------Export Functions------------------------------------------
# -----------------------------------------------------------------------------------------------------------------

def import_building_model_state(path):
    global AtomicMaterialFX_Data, ParticleDataList
    AtomicMaterialFX_Data, ParticleDataList = read_building_model(path, AtomicMaterialFX_Data, ParticleDataList)


def export_building_model_state(path, bone_type_data, particle_data, geometry_data):
    write_building_model(path, bone_type_data, particle_data, geometry_data, AtomicMaterialFX_Data, ParticleDataList)


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

        # 4) Orphans purgen (mehrfach, weil Blender nicht immer alles in einem Durchlauf entfernt)
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
    BuildingDffImportOperator,
    BuildingDffJsonImportOperator,
    BuildingDffExportOperator,
    BuildingDffJsonExportOperator,
    BuildingAnmImportOperator,
    BuildingAnmJsonImportOperator,
    BuildingAnmExportOperator,
    BuildingAnmJsonExportOperator,

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

    SCENE_OT_clear_all,
    SCENE_PT_tools,
)

def draw_import_building_dff_menu_entry(self, context):
    self.layout.operator(BuildingDffImportOperator.bl_idname, text=BuildingDffImportOperator.bl_label)

def draw_import_building_dff_json_menu_entry(self, context):
    self.layout.operator(BuildingDffJsonImportOperator.bl_idname, text=BuildingDffJsonImportOperator.bl_label)

def draw_import_anm_menu_entry(self, context):
    self.layout.operator(BuildingAnmImportOperator.bl_idname, text=BuildingAnmImportOperator.bl_label)

def draw_import_animation_json_menu_entry(self, context):
    self.layout.operator(BuildingAnmJsonImportOperator.bl_idname, text=BuildingAnmJsonImportOperator.bl_label)

def draw_export_building_dff_menu_entry(self, context):
    self.layout.operator(BuildingDffExportOperator.bl_idname, text=BuildingDffExportOperator.bl_label)

def draw_export_building_dff_json_menu_entry(self, context):
    self.layout.operator(BuildingDffJsonExportOperator.bl_idname, text=BuildingDffJsonExportOperator.bl_label)

def draw_export_anm_menu_entry(self, context):
    self.layout.operator(BuildingAnmExportOperator.bl_idname, text=BuildingAnmExportOperator.bl_label)

def draw_export_anm_json_menu_entry(self, context):
    self.layout.operator(BuildingAnmJsonExportOperator.bl_idname, text=BuildingAnmJsonExportOperator.bl_label)


def register_file_menu_entries():
    imp = bpy.types.TOPBAR_MT_file_import
    exp = bpy.types.TOPBAR_MT_file_export

    for fn in (draw_import_building_dff_menu_entry, draw_import_building_dff_json_menu_entry, draw_import_anm_menu_entry, draw_import_animation_json_menu_entry):
        try: imp.remove(fn)
        except Exception: pass
        imp.append(fn)

    for fn in (draw_export_building_dff_menu_entry, draw_export_building_dff_json_menu_entry, draw_export_anm_menu_entry, draw_export_anm_json_menu_entry):
        try: exp.remove(fn)
        except Exception: pass
        exp.append(fn)

def unregister_file_menu_entries():
    imp = bpy.types.TOPBAR_MT_file_import
    exp = bpy.types.TOPBAR_MT_file_export

    for fn in (draw_import_building_dff_menu_entry, draw_import_building_dff_json_menu_entry, draw_import_anm_menu_entry, draw_import_animation_json_menu_entry):
        try: imp.remove(fn)
        except Exception: pass

    for fn in (draw_export_building_dff_menu_entry, draw_export_building_dff_json_menu_entry, draw_export_anm_menu_entry, draw_export_anm_json_menu_entry):
        try: exp.remove(fn)
        except Exception: pass


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    # Scene Properties (bei dir sind die teils im “else”-Branch – in 5.x müssen die immer registriert werden)
    bpy.types.Scene.bone_items = CollectionProperty(type=BoneMappingItem)
    bpy.types.Scene.bone_active_index = IntProperty(default=0)

    bpy.types.Scene.particle_effects = CollectionProperty(type=ParticleEffectBinding)
    bpy.types.Scene.particle_effects_index = IntProperty(default=0)

    bpy.types.Scene.geometry_tool_items = CollectionProperty(type=GeometryExportRecord)
    bpy.types.Scene.geometry_tool_index = IntProperty(default=0)

    register_file_menu_entries()

def unregister():
    unregister_file_menu_entries()

    # Scene Properties entfernen
    for attr in ("bone_items","bone_active_index","particle_effects","particle_effects_index","geometry_tool_items","geometry_tool_index"):
        if hasattr(bpy.types.Scene, attr):
            delattr(bpy.types.Scene, attr)

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)



if __name__ == "__main__":
    register()



