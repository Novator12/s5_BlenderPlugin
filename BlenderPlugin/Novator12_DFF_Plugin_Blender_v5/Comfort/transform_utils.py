import math
import os

import bpy
import mathutils as mu
from mathutils import Matrix, Vector

from .constants import CONVERTER_EXE_NAME


NEGATIVE_Y_THRESHOLD = 1.0e-9
NEGATIVE_Y_CLOSE_THRESHOLD = 1.0e-5
FALLBACK_BONE_AXIS = Vector((0.0, 1.0, 0.0))
EXPORT_BONE_SCALE = 100.0


def get_converter_exe_location():
    addon_dir = os.path.dirname(__file__)
    return os.path.join(addon_dir, CONVERTER_EXE_NAME)


def set_clipping_for_all_screens(clip_start, clip_end):
    for screen in bpy.data.screens:
        for area in screen.areas:
            for space in area.spaces:
                if hasattr(space, "clip_start") and hasattr(space, "clip_end"):
                    space.clip_start = clip_start
                    space.clip_end = clip_end


def compose_matrix(left, right):
    return left @ right


def frame_dict_to_matrix(frame_data):
    rotation_rows = frame_data["rotationMatrix"]
    position = frame_data["position"]

    matrix = Matrix.Identity(4)
    for row_index, row in enumerate(rotation_rows):
        matrix[row_index][0] = row["x"]
        matrix[row_index][1] = row["y"]
        matrix[row_index][2] = row["z"]

    matrix[3][0] = position["x"]
    matrix[3][1] = position["y"]
    matrix[3][2] = position["z"]
    return matrix


def bone_axis_to_matrix(axis, roll):
    normalized_axis = axis.normalized()
    orientation = Matrix().to_3x3()
    theta = 1.0 + normalized_axis.y

    if theta > NEGATIVE_Y_CLOSE_THRESHOLD or ((normalized_axis.x or normalized_axis.z) and theta > NEGATIVE_Y_THRESHOLD):
        orientation[1][0] = -normalized_axis.x
        orientation[0][1] = normalized_axis.x
        orientation[1][1] = normalized_axis.y
        orientation[2][1] = normalized_axis.z
        orientation[1][2] = -normalized_axis.z

        if theta > NEGATIVE_Y_CLOSE_THRESHOLD:
            orientation[0][0] = 1.0 - normalized_axis.x * normalized_axis.x / theta
            orientation[2][2] = 1.0 - normalized_axis.z * normalized_axis.z / theta
            orientation[0][2] = -normalized_axis.x * normalized_axis.z / theta
            orientation[2][0] = orientation[0][2]
        else:
            denominator = normalized_axis.x * normalized_axis.x + normalized_axis.z * normalized_axis.z
            orientation[0][0] = (normalized_axis.x + normalized_axis.z) * (normalized_axis.x - normalized_axis.z) / -denominator
            orientation[2][2] = -orientation[0][0]
            orientation[0][2] = 2.0 * normalized_axis.x * normalized_axis.z / denominator
            orientation[2][0] = orientation[0][2]
    else:
        orientation[0][0] = -1.0
        orientation[1][1] = -1.0

    roll_matrix = mu.Matrix.Rotation(roll, 3, normalized_axis)
    return compose_matrix(roll_matrix, orientation)


def matrix_to_bone_axis_roll(matrix):
    axis = matrix.col[1]
    if axis.length < 1.0e-8:
        return FALLBACK_BONE_AXIS.copy(), 0.0

    axis_matrix = bone_axis_to_matrix(axis, 0.0)
    try:
        inverse_axis_matrix = axis_matrix.inverted()
    except Exception:
        return FALLBACK_BONE_AXIS.copy(), 0.0

    roll_matrix = compose_matrix(inverse_axis_matrix, matrix)
    roll = math.atan2(roll_matrix[0][2], roll_matrix[2][2])
    return axis, roll


def link_object_in_active_collection(obj):
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj


def edit_bone_to_matrix(edit_bone):
    head_position = edit_bone.head
    tail_axis = (edit_bone.tail - head_position) / EXPORT_BONE_SCALE
    orientation_matrix = bone_axis_to_matrix(tail_axis, edit_bone.roll)

    transform_matrix = orientation_matrix.to_4x4()
    transform_matrix.translation = head_position
    return transform_matrix


def bone_name_to_node_id(bone_name):
    node_suffix = bone_name[10:]
    return int(node_suffix) if node_suffix else -1


def accumulate_rest_matrix(rest_matrices, hierarchy, frame_index):
    accumulated_matrix = rest_matrices[frame_index]
    parent_index = hierarchy[frame_index]
    visited = set()

    while parent_index != -1 and parent_index not in visited:
        visited.add(parent_index)
        accumulated_matrix = rest_matrices[parent_index] @ accumulated_matrix
        parent_index = hierarchy[parent_index]

    return accumulated_matrix
