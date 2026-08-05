CONVERTER_EXE_NAME = "S5Converter.exe"

DEFAULT_S5_FPS = 30
MIN_ANIM_NODE_ID = 600
DEFAULT_START_PREV_KEYFRAME = -123456789

ACTION_ANIM_FPS_PROP = "s5_anim_fps"
ACTION_ANIM_FORMAT_PROP = "s5_anim_format"
ACTION_EXPORT_NAME_PROP = "s5_export_name"
ACTION_START_PREV_KEYFRAME_PROP = "s5_import_prev_keyframe"

ANIM_FORMAT_HIERARCHICAL = "hierarchical"
ANIM_FORMAT_COMPRESSED = "compressed"
ANIM_FORMAT_NODES = "nodes"
DEFAULT_ANIM_FORMAT = ANIM_FORMAT_HIERARCHICAL
ANIM_FORMAT_ITEMS = (
    (ANIM_FORMAT_HIERARCHICAL, "HierarchicalAnim", "Use HierarchicalAnim metadata"),
    (ANIM_FORMAT_COMPRESSED, "CompressedAnim", "Use CompressedAnim metadata"),
    (ANIM_FORMAT_NODES, "Nodes", "Use converter nodes[] metadata"),
)

SCENE_MESH_VALIDATION_REPORT_PROP = "s5_mesh_validation_report"
SCENE_MESH_VALIDATION_LOOSE_INDICES_PROP = "s5_mesh_validation_loose_indices"

ROOT_HANIM_NODES_PROP = "s5_root_hanim_nodes"
ROOT_HANIM_PARENTS_PROP = "s5_root_hanim_parents"
ATOMIC_FRAME_INDEX_PROP = "s5_atomic_frame_index"
ATOMIC_EXTENSION_PROP = "s5_atomic_extension"
GEOMETRY_USER_DATA_PROP = "s5_geometry_user_data"
MATERIAL_PAYLOAD_PROP = "s5_material_payload"
TEXTURE_NAME_PROP = "s5_texture_name"
TEXTURE_ALPHA_PROP = "s5_texture_alpha"
MATERIAL_AMBIENT_PROP = "s5_ambient"
MATERIAL_SPECULAR_PROP = "s5_specular"
MATERIAL_DIFFUSE_PROP = "s5_diffuse"
MATERIAL_DUAL_TEX_PROP = "s5_dual_tex"
MATERIAL_SPEC_TEXTURE_PROP = "s5_spec_texture"
MESH_SPHERE_NAME_PROP = "sphere_name"
SPHERE_LINKED_MESH_PROP = "linked_mesh"

BONE_NAME_PADDING = 3
BUILDING_BONE_DISPLAY_LENGTH = 100.0
UNIT_BONE_DISPLAY_LENGTH = 10.0
