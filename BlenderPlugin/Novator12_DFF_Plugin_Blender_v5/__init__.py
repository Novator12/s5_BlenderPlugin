# ------------------------------------------Plugin Info -----------------------------------------------------------------------------------
# pyright: reportInvalidTypeForm=false

bl_info = {
    "name": "Novator12 DFF Plugin Blender v5",
    "author": "Novator12",
    "version": (2, 0, 0),
    "blender": (5, 0, 0),
    "location": "File > Import-Export + View3D Sidebar",
    "description": "Import/Export fuer starre Gebaeude und Gebaeude-Animationen (Settlers 5) inkl. UserData/Particle/Geometry Tools",
    "category": "Import-Export",
}

from .building_model_export import write_building_model
from .building_model_import import read_building_model
from .Comfort.ui_registration import register, unregister
from .unit_model_export import write_unit_model
from .unit_model_import import read_unit_model


AtomicMaterialFX_Data = {}
ParticleDataList = {}


def import_building_model_state(path):
    global AtomicMaterialFX_Data, ParticleDataList
    AtomicMaterialFX_Data, ParticleDataList = read_building_model(path, AtomicMaterialFX_Data, ParticleDataList)


def import_unit_model_state(path):
    read_unit_model(path)


def export_building_model_state(path, bone_type_data, particle_data, geometry_data):
    write_building_model(path, bone_type_data, particle_data, geometry_data, AtomicMaterialFX_Data, ParticleDataList)


def export_unit_model_state(path, context):
    write_unit_model(path, context)


if __name__ == "__main__":
    register()
