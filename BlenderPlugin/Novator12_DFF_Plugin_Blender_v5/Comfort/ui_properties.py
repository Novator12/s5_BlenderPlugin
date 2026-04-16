from bpy.props import BoolProperty, CollectionProperty, EnumProperty, StringProperty
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


class GeometryExportRecord(PropertyGroup):
    mesh_name: StringProperty(name="Mesh Name", default="No data")
    materials: CollectionProperty(type=GeometryMaterialRecord)
    bin_mesh_data: StringProperty(name="BinMesh Data", default="No data")
