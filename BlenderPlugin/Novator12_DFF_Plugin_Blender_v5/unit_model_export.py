import os

from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper


def _ensure_filepath_extension(filepath, extension):
    root, _old_ext = os.path.splitext(filepath)
    return root + extension if root else filepath + extension


class UnitExportOperator(Operator, ExportHelper):
    bl_idname = "export_model.unit"
    bl_label = "Novator-Export-Unit (.dff/.json)"
    filename_ext = ".dff"
    filter_glob: StringProperty(default="*.dff;*.json", options={"HIDDEN"})
    file_format: EnumProperty(
        name="Format",
        items=(
            ("DFF", ".dff", "Export as .dff"),
            ("JSON", ".json", "Export as .json"),
        ),
        default="DFF",
    )

    def check(self, _context):
        desired_ext = ".dff" if self.file_format == "DFF" else ".json"
        updated_path = _ensure_filepath_extension(self.filepath, desired_ext)
        if updated_path != self.filepath:
            self.filepath = updated_path
            return True
        return False

    def draw(self, _context):
        self.layout.prop(self, "file_format")

    def execute(self, context):
        from . import export_unit_model_state

        export_path = _ensure_filepath_extension(self.filepath, ".dff" if self.file_format == "DFF" else ".json")
        try:
            export_unit_model_state(export_path, context)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
