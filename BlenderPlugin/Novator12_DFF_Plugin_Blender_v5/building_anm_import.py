from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .building_utilities import (
    apply_animation_data_to_armature,
    apply_animation_json_to_armature,
    convert_anm_to_json_external,
    ensure_armature_active,
)


class BuildingAnmImportOperator(Operator, ImportHelper):
    bl_idname = "import_anim.building_anm"
    bl_label = "Novator-Import-Buidling-Anm(.anm)"
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={"HIDDEN"})

    def execute(self, context):
        try:
            armature_object = ensure_armature_active()
            payload = convert_anm_to_json_external(self.filepath)
            apply_animation_data_to_armature(payload, armature_object, self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class BuildingAnmJsonImportOperator(Operator, ImportHelper):
    bl_idname = "import_anim.building_anm_json"
    bl_label = "Novator-Import-Buidling-Anm-Json(.json)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            armature_object = ensure_armature_active()
            apply_animation_json_to_armature(self.filepath, armature_object, self.filepath)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
