import bpy

from bpy.props import BoolProperty, CollectionProperty, EnumProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup

from ..particle_effects_data import PARTICLE_EFFECT_LUT


PARTICLE_EFFECT_ITEMS = [
    ("Ubisoft", "Ubisoft", "Vom Import gefundener Particle-Effect wird verwendet."),
]
for effect_name in sorted(PARTICLE_EFFECT_LUT):
    PARTICLE_EFFECT_ITEMS.append((effect_name, effect_name, effect_name))


class BoneMappingItem(PropertyGroup):
    bone_index: StringProperty(name="Bone Index", default="")
    bone_name: StringProperty(name="Bone Name", default="")
    bone_type: EnumProperty(
        name="Type",
        items=[
            ("DECAL", "Decal", "Markiert den Bone als Decal"),
            ("BUILDING", "Building", "Markiert den Bone als Building"),
        ],
        default="DECAL",
    )
    include_tag: BoolProperty(
        name="Tag + Effect",
        description=(
            "Keeps or adds 'tag = <Bone Name>' together with the selected effect; "
            "use this for animated snow/decal frames"
        ),
        default=False,
    )


class ParticleEffectBinding(PropertyGroup):
    bone_index: StringProperty(name="Bone Index", default="")
    effect_type: EnumProperty(
        name="Effekte",
        items=PARTICLE_EFFECT_ITEMS,
        default="smoke10" if "smoke10" in PARTICLE_EFFECT_LUT else PARTICLE_EFFECT_ITEMS[0][0],
    )


class GeometryMaterialRecord(PropertyGroup):
    name: StringProperty(name="Material Name")
    uv_trans: BoolProperty(name="UVTrans", default=False)
    dual_tex: BoolProperty(name="DualTex", default=False)
    ambient: BoolProperty(name="Ambient", default=True)
    specular: BoolProperty(name="Specular", default=False)
    diffuse: BoolProperty(name="Diffuse", default=True)
    snow_texture: StringProperty(name="Snow Texture", default="No data")
    texture_alpha: StringProperty(name="Texture Alpha", default="")


def geometry_mesh_object_poll(_self, obj):
    return obj is not None and getattr(obj, "type", None) == "MESH"


def update_geometry_mesh_object(self, _context):
    mesh_object = self.mesh_object
    if mesh_object is None:
        self.linked_to_object = False
        return

    self.mesh_name = mesh_object.name
    self.linked_to_object = True


class GeometryExportRecord(PropertyGroup):
    mesh_name: StringProperty(name="Mesh Name", default="No data")
    bone_index: StringProperty(name="Bone Index", default="")
    mesh_object: PointerProperty(
        name="Mesh Object",
        type=bpy.types.Object,
        poll=geometry_mesh_object_poll,
        update=update_geometry_mesh_object,
    )
    linked_to_object: BoolProperty(name="Linked To Mesh Object", default=False)
    materials: CollectionProperty(type=GeometryMaterialRecord)
    bin_mesh_data: StringProperty(name="BinMesh Data", default="No data")
