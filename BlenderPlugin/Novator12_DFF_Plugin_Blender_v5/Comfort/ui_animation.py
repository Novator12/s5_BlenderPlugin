import bpy

from bpy.app.handlers import persistent
from bpy.types import Operator, Panel

from .anim_utils import (
    ensure_action_anim_format,
    ensure_action_stashed_in_muted_nla,
    parse_action_anim_fps,
    parse_action_start_prev_keyframe,
)
from .constants import (
    ACTION_ANIM_FPS_PROP,
    ACTION_ANIM_FORMAT_PROP,
    ACTION_START_PREV_KEYFRAME_PROP,
    DEFAULT_ANIM_FORMAT,
    DEFAULT_S5_FPS,
    DEFAULT_START_PREV_KEYFRAME,
)


_LAST_ACTION_SYNC_KEY = None
_LAST_ACTION_BY_OBJECT = {}


def reset_animation_ui_state():
    global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT
    _LAST_ACTION_SYNC_KEY = None
    _LAST_ACTION_BY_OBJECT = {}


def _get_active_armature_action(context):
    active_object = getattr(context, "object", None)
    if active_object is None or active_object.type != "ARMATURE":
        return None, None

    animation_data = getattr(active_object, "animation_data", None)
    if animation_data is None:
        return active_object, None

    return active_object, animation_data.action


def _resolve_active_action(context):
    space_data = getattr(context, "space_data", None)
    action = getattr(space_data, "action", None)
    if action is not None:
        return action

    _armature_object, action = _get_active_armature_action(context)
    return action


def _collect_action_fcurves(action):
    fcurves = []
    seen = set()

    def _append_fcurve(fc):
        if fc is None:
            return
        identifier = getattr(fc, "as_pointer", None)
        key = identifier() if callable(identifier) else id(fc)
        if key in seen:
            return
        seen.add(key)
        fcurves.append(fc)

    try:
        for fc in action.fcurves:
            _append_fcurve(fc)
    except Exception:
        pass

    try:
        slots = list(getattr(action, "slots", []))
        layers = list(getattr(action, "layers", []))
        for layer in layers:
            for strip in getattr(layer, "strips", []):
                if slots:
                    for slot in slots:
                        try:
                            channelbag = strip.channelbag(slot)
                        except Exception:
                            continue
                        if channelbag:
                            for fc in getattr(channelbag, "fcurves", []):
                                _append_fcurve(fc)
                else:
                    try:
                        channelbag = strip.channelbag(action_slot=None)
                    except Exception:
                        channelbag = None
                    if channelbag:
                        for fc in getattr(channelbag, "fcurves", []):
                            _append_fcurve(fc)
    except Exception:
        pass

    return fcurves


def _sync_scene_range_to_action(scene, action):
    if action is None:
        return

    try:
        action_start = float(action.frame_range[0])
        action_end = float(action.frame_range[1])
    except Exception:
        return

    frame_length = max(0, int(round(action_end - action_start)))
    scene.frame_start = 0
    scene.frame_end = frame_length
    scene.frame_set(0)
    bpy.context.view_layer.update()


class ACTION_OT_apply_animation_fps(Operator):
    bl_idname = "action.apply_animation_fps"
    bl_label = "Apply FPS"

    def execute(self, context):
        action = _resolve_active_action(context)
        if action is None:
            self.report({"ERROR"}, "Keine aktive Action gefunden.")
            return {"CANCELLED"}

        try:
            target_fps = parse_action_anim_fps(action, DEFAULT_S5_FPS)
            parse_action_start_prev_keyframe(action, DEFAULT_START_PREV_KEYFRAME)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        current_fps = int(round(context.scene.render.fps)) if context.scene.render.fps > 0 else DEFAULT_S5_FPS
        if current_fps <= 0:
            current_fps = DEFAULT_S5_FPS

        scale = float(target_fps) / float(current_fps)
        if abs(scale - 1.0) > 1.0e-9:
            for fcurve in _collect_action_fcurves(action):
                for keyframe in getattr(fcurve, "keyframe_points", []):
                    keyframe.co.x *= scale
                    keyframe.handle_left.x *= scale
                    keyframe.handle_right.x *= scale
                try:
                    fcurve.update()
                except Exception:
                    pass

        scene = context.scene
        scene.render.fps = target_fps
        scene.render.fps_base = 1.0
        _sync_scene_range_to_action(scene, action)

        self.report({"INFO"}, "Animation FPS auf {} angewendet.".format(target_fps))
        return {"FINISHED"}


class ACTION_PT_animation_fps(Panel):
    bl_idname = "DOPESHEET_PT_animation_fps"
    bl_label = "Animation Tool"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_category = "Animation Tool"

    def draw(self, context):
        layout = self.layout
        try:
            action = _resolve_active_action(context)

            if action is None:
                layout.label(text="Keine aktive Action gefunden.")
                return

            col = layout.column(align=True)
            row = col.row(align=True)
            row.label(text="Animation:")
            row.label(text=action.name)
            ensure_action_anim_format(action, DEFAULT_ANIM_FORMAT)
            col.prop(action, ACTION_ANIM_FPS_PROP, text="FPS", slider=False)
            col.prop(action, ACTION_ANIM_FORMAT_PROP, text="Anim-Type")
            col.prop(action, ACTION_START_PREV_KEYFRAME_PROP, text="Start-Prev-Keyframe", slider=False)
            layout.separator()
            layout.operator(ACTION_OT_apply_animation_fps.bl_idname, text="Apply FPS")
        except Exception as exc:
            layout.label(text="UI-Fehler im Animation Tool.")
            layout.label(text=str(exc))


@persistent
def sync_timeline_to_selected_action(_scene=None):
    global _LAST_ACTION_SYNC_KEY, _LAST_ACTION_BY_OBJECT

    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None:
        return

    armature_object, action = _get_active_armature_action(context)
    action_name = None if action is None else action.name_full
    object_name = None if armature_object is None else armature_object.name_full
    action_key = (object_name, action_name)

    if action_key == _LAST_ACTION_SYNC_KEY:
        return

    if armature_object is not None:
        previous_action = _LAST_ACTION_BY_OBJECT.get(object_name)
        if previous_action is not None and previous_action != action:
            try:
                ensure_action_stashed_in_muted_nla(armature_object, previous_action, clear_active=False)
            except Exception:
                pass

    _LAST_ACTION_SYNC_KEY = action_key
    if object_name is not None:
        if action is None:
            _LAST_ACTION_BY_OBJECT.pop(object_name, None)
        else:
            _LAST_ACTION_BY_OBJECT[object_name] = action
    if action is not None:
        _sync_scene_range_to_action(scene, action)
