import bmesh
import bpy

from mathutils import Vector

from bpy.props import IntProperty
from bpy.types import Operator, Panel, UIList

from .constants import (
    MESH_SPHERE_NAME_PROP,
    SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
    SCENE_MESH_VALIDATION_REPORT_PROP,
    SPHERE_LINKED_MESH_PROP,
)
from .ui_animation import reset_animation_ui_state
from .validation_utils import (
    build_mesh_validation_lines,
    collect_loose_vertex_indices,
    mesh_validation_icon,
    validate_mesh_object,
)


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

        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=self.sphere_radius,
            location=(self.sphere_x, self.sphere_y, self.sphere_z),
        )
        sphere = bpy.context.object
        sphere.name = "{}_Sphere".format(obj.name)
        sphere.display_type = "WIRE"
        sphere.parent = obj
        obj[MESH_SPHERE_NAME_PROP] = sphere.name
        sphere[SPHERE_LINKED_MESH_PROP] = obj.name

        self.report({"INFO"}, "Sphere '{}' ceated and parented to '{}'.".format(sphere.name, obj.name))
        return {"FINISHED"}

    def invoke(self, context, event):
        obj = context.object
        if obj and obj.type == "MESH":
            mesh_world_coords = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
            center_x = sum(coord.x for coord in mesh_world_coords) / len(mesh_world_coords)
            center_y = sum(coord.y for coord in mesh_world_coords) / len(mesh_world_coords)
            center_z = sum(coord.z for coord in mesh_world_coords) / len(mesh_world_coords)
            center = Vector((center_x, center_y, center_z))
            max_distance = max((coord - center).length for coord in mesh_world_coords)

            self.sphere_x = center.x
            self.sphere_y = center.y
            self.sphere_z = center.z
            self.sphere_radius = max_distance

        return context.window_manager.invoke_props_dialog(self)


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
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is None:
            return

        box_main = layout.box()
        box_main.label(text=" Geometry {} --------------------------------------------------------------------------------------------------------------------------------------------------".format(index + 1))
        box_main.prop(item, "mesh_name", text="Mesh")

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

        row = box_main.row(align=True)
        add_op = row.operator("geometry_tools.add_material", icon="PLUS", text="")
        add_op.index = index
        rem_op = row.operator("geometry_tools.remove_material", icon="X", text="")
        rem_op.index = index

        row = box_main.row()
        row.prop(item, "bin_mesh_data", text="BinMesh")


class GEOMETRY_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_geometry_tools"
    bl_label = "Geometry Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Geometry Tools"

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
    bl_description = "Prueft das aktive Mesh auf Export-Probleme bei UVs, Triangles und BinMesh-Daten"

    def execute(self, context):
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "Kein aktives Mesh ausgewaehlt.")
            return {"CANCELLED"}

        mesh_report = validate_mesh_object(mesh_object)
        lines = build_mesh_validation_lines(mesh_report)
        setattr(context.scene, SCENE_MESH_VALIDATION_REPORT_PROP, "\n".join(lines))
        setattr(
            context.scene,
            SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP,
            ",".join(str(index) for index in mesh_report["loose_vertices"]),
        )

        has_error = any(line.startswith("ERROR:") for line in lines)
        has_warning = any(line.startswith("WARN:") for line in lines)
        if has_error:
            self.report({"WARNING"}, "Mesh-Check abgeschlossen: Fehler gefunden. Details im Mesh Validation Panel.")
        elif has_warning:
            self.report({"INFO"}, "Mesh-Check abgeschlossen: Warnungen gefunden. Details im Mesh Validation Panel.")
        else:
            self.report({"INFO"}, "Mesh-Check abgeschlossen: Keine Probleme gefunden.")
        return {"FINISHED"}


class GEOMETRY_OT_delete_loose_vertices(Operator):
    bl_idname = "geometry_tools.delete_loose_vertices"
    bl_label = "Delete Loose Vertices"
    bl_description = "Loescht unbenutzte Vertices im aktiven Mesh"

    def execute(self, context):
        mesh_object = context.active_object
        if mesh_object is None or mesh_object.type != "MESH" or mesh_object.data is None:
            self.report({"ERROR"}, "Kein aktives Mesh ausgewaehlt.")
            return {"CANCELLED"}

        mesh_data = mesh_object.data
        loose_indices = collect_loose_vertex_indices(mesh_object)
        if not loose_indices:
            setattr(context.scene, SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP, "")
            self.report({"INFO"}, "Keine losen Vertices gefunden.")
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
        self.report({"INFO"}, f"{len(loose_indices)} lose Vertices geloescht.")
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
            layout.label(text="Noch kein Report vorhanden.")
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
