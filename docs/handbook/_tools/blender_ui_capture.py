from __future__ import annotations

import argparse
import bmesh
import ctypes
import json
import os
import sys
import traceback
from ctypes import wintypes
from pathlib import Path

import bpy

bpy.context.preferences.view.show_splash = False


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
ADDON_PARENT = REPO_ROOT / "BlenderPlugin"
ADDON_NAME = "Novator12_DFF_Plugin_Blender_v5"
GAME_ROOT = Path(
    r"D:\Programme (x86)\Ubisoft\Blue Byte\DIE SIEDLER - Das Erbe der Könige - Gold Edition"
)
MODEL_ROOT = GAME_ROOT / "base" / "data" / "graphics" / "models"
ANIM_ROOT = GAME_ROOT / "base" / "data" / "graphics" / "animations"
BUILDING_MODEL = MODEL_ROOT / "pb_farm2.dff"
BUILDING_ANIMATION = ANIM_ROOT / "pb_farm2_600.anm"
UNIT_MODEL = MODEL_ROOT / "cu_banditsoldiersword1.dff"
UNIT_ANIMATION = ANIM_ROOT / "cu_banditsoldiersword1_idle1.anm"
TEST_ROOT = REPO_ROOT / "docs" / "handbook" / "_test"
FOCUSED_BUILDING_BLEND = TEST_ROOT / "PB_Factory.blend"
FOCUSED_UNIT_MODEL = TEST_ROOT / "pu_leadersword4.dff"
FOCUSED_BUILDING_TEXTURE = TEST_ROOT / "textures" / "b_cb_siegeengineworkshop_yard.dds"

FOCUSED_BUILDING_MODES = {
    "detail_factory_overview",
    "detail_factory_topology",
    "detail_factory_uv_layout",
    "detail_factory_material_nodes",
    "detail_factory_geometry_tools",
    "detail_factory_geometry_material",
    "detail_factory_particle_tools",
    "detail_factory_sphere",
    "detail_factory_bone_manager",
    "detail_factory_action_timeline",
}
FOCUSED_UNIT_MODES = {
    "detail_unit_overview",
    "detail_unit_topology",
    "detail_unit_armature",
    "detail_unit_weight_paint",
    "detail_unit_vertex_groups",
    "detail_unit_uv_layout",
    "detail_unit_selection_sphere",
}
FOCUSED_GENERAL_MODES = {"detail_import_menu", "detail_export_menu"}
FOCUSED_MODES = FOCUSED_BUILDING_MODES | FOCUSED_UNIT_MODES | FOCUSED_GENERAL_MODES


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--capture-scope",
        choices=("auto", "whole", "editor", "window", "sidebar", "properties", "outliner", "rect"),
        default="auto",
        help="Lossless crop of the authentic Blender screenshot; focused modes choose a default.",
    )
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--allow-overwrite", action="store_true")
    return parser.parse_args(argv)


ARGS = parse_args()
OUTPUT = Path(ARGS.output).resolve()


def register_addon():
    sys.path.insert(0, str(ADDON_PARENT))
    addon = __import__(ADDON_NAME)
    addon.register()
    return addon


ADDON = register_addon()


CAPTURE_SCOPE = "whole"
CAPTURE_AREA_TYPE = None
CAPTURE_CONTEXT_PIXELS = 0
CAPTURE_RECT = None


def set_capture_target(scope: str, area_type: str | None = None, context_pixels: int = 0):
    global CAPTURE_SCOPE, CAPTURE_AREA_TYPE, CAPTURE_CONTEXT_PIXELS
    CAPTURE_SCOPE = scope if ARGS.capture_scope == "auto" else ARGS.capture_scope
    CAPTURE_AREA_TYPE = area_type
    CAPTURE_CONTEXT_PIXELS = max(0, int(context_pixels))


def set_capture_rect(x0: int, y0: int, x1: int, y1: int):
    global CAPTURE_RECT
    CAPTURE_RECT = (int(x0), int(y0), int(x1), int(y1))
    set_capture_target("rect")


def clear_default_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def activate_object(obj):
    for selected in list(bpy.context.selected_objects):
        selected.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def activate_armature():
    armature = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
    activate_object(armature)
    return armature


def import_building(with_animation=False):
    clear_default_scene()
    result = bpy.ops.import_model.building(filepath=str(BUILDING_MODEL))
    if result != {"FINISHED"}:
        raise RuntimeError(f"Building import failed: {result}")
    if with_animation:
        activate_armature()
        result = bpy.ops.import_anim.building_anm(filepath=str(BUILDING_ANIMATION))
        if result != {"FINISHED"}:
            raise RuntimeError(f"Building animation import failed: {result}")


def import_unit(with_animation=False):
    clear_default_scene()
    result = bpy.ops.import_model.unit(filepath=str(UNIT_MODEL))
    if result != {"FINISHED"}:
        raise RuntimeError(f"Unit import failed: {result}")
    if with_animation:
        activate_armature()
        result = bpy.ops.import_anim.unit_anm(filepath=str(UNIT_ANIMATION))
        if result != {"FINISHED"}:
            raise RuntimeError(f"Unit animation import failed: {result}")


def require_focused_factory_file():
    expected = FOCUSED_BUILDING_BLEND.resolve()
    current = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    if current != expected:
        raise RuntimeError(
            "This mode requires Blender to be launched with "
            f"{expected}; current file is {current or '<unsaved>'}."
        )


def import_focused_unit():
    clear_default_scene()
    result = bpy.ops.import_model.unit(filepath=str(FOCUSED_UNIT_MODEL))
    if result != {"FINISHED"}:
        raise RuntimeError(f"Focused unit import failed: {result}")


def prepare_data():
    mode = ARGS.mode
    if mode in FOCUSED_GENERAL_MODES:
        return
    if mode in FOCUSED_BUILDING_MODES:
        require_focused_factory_file()
    elif mode in FOCUSED_UNIT_MODES:
        import_focused_unit()
    elif mode in {
        "building_overview",
        "bone_tools",
        "sphere_tools",
        "particle_tools",
        "geometry_tools",
        "scene_tools",
        "mesh_basics",
        "mesh_validation",
        "uv_validation",
        "binmesh_validation",
        "sphere_generate_dialog",
        "export_building_dialog",
        "export_building_animation_dialog",
    }:
        import_building(with_animation=mode == "export_building_animation_dialog")
    elif mode in {
        "unit_overview",
        "armature_bones",
        "weight_paint",
        "animation_tool_unit",
        "export_unit_dialog",
        "export_unit_animation_dialog",
    }:
        import_unit(with_animation=mode in {"animation_tool_unit", "export_unit_animation_dialog"})


prepare_data()


def window_and_area(area_type="VIEW_3D"):
    window = bpy.context.window_manager.windows[0]
    screen = window.screen
    area = next((candidate for candidate in screen.areas if candidate.type == area_type), None)
    if area is None:
        area = max(screen.areas, key=lambda candidate: candidate.width * candidate.height)
        area.type = area_type
    region = next((candidate for candidate in area.regions if candidate.type == "WINDOW"), None)
    return window, screen, area, region


def show_sidebar(category: str, area_type="VIEW_3D"):
    window, screen, area, region = window_and_area(area_type)
    space = area.spaces.active
    if hasattr(space, "show_region_ui"):
        space.show_region_ui = True
    ui_region = next((candidate for candidate in area.regions if candidate.type == "UI"), None)
    activated_directly = False
    if ui_region is not None:
        try:
            ui_region.active_panel_category = category
            activated_directly = ui_region.active_panel_category == category
        except (AttributeError, RuntimeError, TypeError):
            activated_directly = False
    if not activated_directly:
        click_sidebar_category(category, area)
    return window, screen, area, region


def current_blender_window():
    if sys.platform != "win32":
        return None, 0, 0

    user32 = ctypes.windll.user32
    current_pid = os.getpid()
    found = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    @enum_proc
    def callback(hwnd, _lparam):
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value == current_pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(callback, 0)
    if not found:
        return None, 0, 0

    hwnd = found[0]
    point = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))
    user32.SetForegroundWindow(hwnd)
    return hwnd, point.x, point.y


def click_sidebar_category(category: str, area):
    if sys.platform != "win32":
        return

    # Blender's View3D sidebar category strip uses stable top offsets at the
    # 2048 x 1088 handbook capture size. Coordinates are inside the client area.
    y_by_category = {
        "Bone Tools": 260,
        "Sphere Tools": 327,
        "Particle Tools": 402,
        "Geometry Tools": 491,
        "Scene Tools": 575,
        "Animation Tool": 135,
    }
    if category not in y_by_category:
        return
    user32 = ctypes.windll.user32
    hwnd, origin_x, origin_y = current_blender_window()
    client_x = area.x + area.width - 9
    client_rect = wintypes.RECT()
    if hwnd:
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))
    capture_scale = ((client_rect.right - client_rect.left) / 2048.0) if client_rect.right else 1.0
    client_y = round(y_by_category[category] * capture_scale)
    click_x = origin_x + client_x
    click_y = origin_y + client_y
    user32.SetCursorPos(click_x, click_y)
    if hwnd:
        lparam = (client_y << 16) | (client_x & 0xFFFF)
        user32.PostMessageW(hwnd, 0x0200, 0, lparam)
        user32.PostMessageW(hwnd, 0x0201, 0x0001, lparam)
        user32.PostMessageW(hwnd, 0x0202, 0, lparam)
    print(
        f"HANDBOOK_UI_CLICK category={category!r} client=({client_x},{client_y}) "
        f"screen=({click_x},{click_y}) hwnd={hwnd}",
        flush=True,
    )


def position_cursor_in_client(client_x: int, client_y: int):
    if sys.platform != "win32":
        return
    _hwnd, origin_x, origin_y = current_blender_window()
    ctypes.windll.user32.SetCursorPos(origin_x + int(client_x), origin_y + int(client_y))


def focus_view(selected_objects, *, view_axis="FRONT"):
    window, screen, area, region = window_and_area("VIEW_3D")
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in selected_objects:
        obj.hide_set(False)
        obj.select_set(True)
    if selected_objects:
        bpy.context.view_layer.objects.active = selected_objects[0]
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
        bpy.ops.view3d.view_axis(type=view_axis, align_active=False)
        bpy.ops.view3d.view_selected(use_all_regions=False)


def force_object_mode():
    active = bpy.context.view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass


def hide_all_except(objects):
    wanted = {obj.name_full for obj in objects}
    for obj in bpy.context.scene.objects:
        obj.hide_set(obj.name_full not in wanted)
    for obj in objects:
        obj.hide_set(False)


def configure_viewport(*, shading="SOLID", wire=False, xray=False):
    _window, _screen, area, _region = window_and_area("VIEW_3D")
    space = area.spaces.active
    space.region_3d.view_perspective = "ORTHO"
    space.shading.type = shading
    if hasattr(space.shading, "light"):
        space.shading.light = "STUDIO"
    if hasattr(space.shading, "color_type") and shading == "SOLID":
        space.shading.color_type = "MATERIAL"
    space.overlay.show_overlays = True
    space.overlay.show_wireframes = wire
    if hasattr(space.overlay, "wireframe_threshold"):
        space.overlay.wireframe_threshold = 1.0
    space.overlay.show_text = True
    if hasattr(space, "shading") and hasattr(space.shading, "show_xray"):
        space.shading.show_xray = xray
        space.shading.xray_alpha = 0.35
    return area


def maximize_editor(area_type="VIEW_3D"):
    """Maximize one real Blender editor without saving the temporary UI state."""
    window, screen, area, region = window_and_area(area_type)
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)
    return window_and_area(area_type)


def focus_view_three_quarter(selected_objects):
    window, screen, area, region = window_and_area("VIEW_3D")
    focus_view(selected_objects, view_axis="FRONT")
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
        bpy.ops.view3d.view_orbit(type="ORBITRIGHT")
        bpy.ops.view3d.view_orbit(type="ORBITUP")
    area.spaces.active.region_3d.view_distance *= 1.08


def named_mesh(name: str):
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != "MESH":
        raise RuntimeError(f"Expected mesh {name!r} was not found")
    return obj


def focused_unit_mesh():
    return next(
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and "selectionsphere" not in obj.name.lower()
    )


def focused_unit_sphere():
    return next(
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and "selectionsphere" in obj.name.lower()
    )


def set_geometry_tool_target(mesh):
    scene = bpy.context.scene
    entries = list(getattr(scene, "geometry_tool_items", []))
    for index, item in enumerate(entries):
        if getattr(item, "mesh_object", None) == mesh or getattr(item, "mesh_name", "") == mesh.name:
            scene.geometry_tool_index = index
            return index
    raise RuntimeError(f"No Geometry Tools entry is linked to {mesh.name!r}")


def choose_informative_weight_group(mesh):
    candidates = []
    vertex_count = max(1, len(mesh.data.vertices))
    for group in mesh.vertex_groups:
        weights = []
        for vertex in mesh.data.vertices:
            try:
                weight = group.weight(vertex.index)
            except RuntimeError:
                continue
            if weight > 1.0e-6:
                weights.append(weight)
        if not weights:
            continue
        coverage = len(weights) / vertex_count
        spread = max(weights) - min(weights)
        # Prefer a visible local deformation region with an actual gradient.
        locality = 1.0 if 0.04 <= coverage <= 0.65 else 0.25
        candidates.append((locality * len(weights) * (0.25 + spread), group.index, group.name))
    if not candidates:
        raise RuntimeError(f"No nonzero vertex group was found on {mesh.name!r}")
    _score, group_index, group_name = max(candidates)
    mesh.vertex_groups.active_index = group_index
    print(
        f"HANDBOOK_WEIGHT_GROUP mesh={mesh.name!r} index={group_index} name={group_name!r}",
        flush=True,
    )
    return mesh.vertex_groups[group_index]


def make_uv_editor(mesh, image=None):
    activate_object(mesh)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    window, screen, area, region = window_and_area("VIEW_3D")
    area.type = "IMAGE_EDITOR"
    try:
        area.ui_type = "UV"
    except (AttributeError, TypeError):
        pass
    space = area.spaces.active
    if image is not None:
        space.image = image
    window_region = next(candidate for candidate in area.regions if candidate.type == "WINDOW")
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=window_region):
        bpy.ops.image.view_all(fit_view=True)
    return area


def load_factory_detail_texture():
    expected = FOCUSED_BUILDING_TEXTURE.resolve()
    image = next(
        (
            candidate
            for candidate in bpy.data.images
            if candidate.type == "IMAGE" and "siegeengineworkshop_yard" in candidate.name.lower()
        ),
        None,
    )
    if image is None:
        image = bpy.data.images.load(str(expected), check_existing=True)
    else:
        image.filepath = str(expected)
        try:
            image.reload()
        except RuntimeError:
            pass
    return image


def make_material_node_editor(mesh):
    activate_object(mesh)
    if not mesh.data.materials or mesh.active_material is None:
        raise RuntimeError(f"{mesh.name!r} has no active material")
    window, screen, area, _region = window_and_area("VIEW_3D")
    area.type = "NODE_EDITOR"
    try:
        area.ui_type = "ShaderNodeTree"
    except (AttributeError, TypeError):
        pass
    space = area.spaces.active
    space.tree_type = "ShaderNodeTree"
    if hasattr(space, "shader_type"):
        space.shader_type = "OBJECT"
    window_region = next(candidate for candidate in area.regions if candidate.type == "WINDOW")
    with bpy.context.temp_override(window=window, screen=screen, area=area, region=window_region):
        bpy.ops.node.view_all()
    return area


def show_mesh_data_properties(mesh):
    activate_object(mesh)
    _window, screen, _area, _region = window_and_area("VIEW_3D")
    area = next((candidate for candidate in screen.areas if candidate.type == "PROPERTIES"), None)
    if area is None:
        raise RuntimeError("The current screen has no Properties editor")
    try:
        area.spaces.active.context = "DATA"
    except (AttributeError, TypeError):
        pass
    return area


def setup_mode():
    mode = ARGS.mode
    try:
        bpy.context.preferences.view.language = "en_US"
        bpy.context.preferences.view.use_translate_interface = False
        bpy.context.preferences.view.use_translate_tooltips = False
        bpy.context.preferences.view.show_tooltips = False
    except (AttributeError, TypeError):
        pass

    if mode in {"detail_import_menu", "detail_export_menu"}:
        window, screen, area, region = window_and_area("VIEW_3D")
        position_cursor_in_client(430, 90)
        menu_name = "TOPBAR_MT_file_import" if mode == "detail_import_menu" else "TOPBAR_MT_file_export"
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            menu_result = bpy.ops.wm.call_menu(name=menu_name)
        print(f"HANDBOOK_MENU={menu_name} RESULT={sorted(menu_result)}", flush=True)
        screen_height = max(candidate.y + candidate.height for candidate in screen.areas)
        # Blender anchors these top-bar menus against the left side even when
        # wm.call_menu receives a cursor near x=430. Start at the editor edge
        # so no label is clipped, then retain only a narrow strip of authentic
        # viewport context. At the handbook UI scale 820 x 580 contains the
        # complete Blender 5.0.1 menu, including all four Novator entries.
        popup_x0 = area.x
        popup_x1 = min(area.x + area.width, popup_x0 + 820)
        popup_y1 = screen_height
        popup_y0 = max(area.y, popup_y1 - 580)
        set_capture_rect(popup_x0, popup_y0, popup_x1, popup_y1)
    elif mode == "detail_factory_overview":
        force_object_mode()
        image = load_factory_detail_texture()
        image.reload()
        names = {
            "Kran",
            "Krangestell",
            "Kran_Schere1",
            "Kran_Schere2",
            "Kran_Seil1",
            "Kran_Seil2",
            "Kran_Seil3",
            "Kran_Halter",
        }
        objects = [obj for obj in bpy.context.scene.objects if obj.name in names]
        if not objects:
            raise RuntimeError("PB_Factory detail objects were not found")
        hide_all_except(objects)
        configure_viewport(shading="MATERIAL")
        focus_view_three_quarter(objects)
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_factory_topology":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        activate_object(mesh)
        configure_viewport(shading="SOLID", wire=True)
        focus_view_three_quarter([mesh])
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)
        bpy.ops.mesh.select_all(action="SELECT")
        area = window_and_area("VIEW_3D")[2]
        area.spaces.active.overlay.show_face_center = True
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_factory_uv_layout":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        image = load_factory_detail_texture()
        make_uv_editor(mesh, image=image)
        set_capture_target("editor", "IMAGE_EDITOR")
    elif mode == "detail_factory_material_nodes":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        load_factory_detail_texture()
        make_material_node_editor(mesh)
        set_capture_target("editor", "NODE_EDITOR")
    elif mode == "detail_factory_geometry_tools":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        activate_object(mesh)
        set_geometry_tool_target(mesh)
        configure_viewport(shading="MATERIAL")
        focus_view_three_quarter([mesh])
        show_sidebar("Geometry Tools")
        set_capture_target("sidebar", "VIEW_3D", context_pixels=360)
    elif mode == "detail_factory_geometry_material":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        activate_object(mesh)
        set_geometry_tool_target(mesh)
        configure_viewport(shading="MATERIAL")
        focus_view_three_quarter([mesh])
        # PB_Factory's saved workspace leaves only about 670 px for this
        # editor. Maximize it in the disposable process so the selected
        # Geometry entry and its complete DFF material fields fit together.
        maximize_editor("VIEW_3D")
        show_sidebar("Geometry Tools")
        set_capture_target("sidebar", "VIEW_3D", context_pixels=220)
    elif mode == "detail_factory_particle_tools":
        force_object_mode()
        meshes = [
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH" and not obj.name.endswith("_Sphere") and len(obj.data.vertices) > 0
        ]
        hide_all_except(meshes)
        configure_viewport(shading="SOLID")
        focus_view(meshes, view_axis="FRONT")
        show_sidebar("Particle Tools")
        set_capture_target("sidebar", "VIEW_3D", context_pixels=300)
    elif mode == "detail_factory_sphere":
        force_object_mode()
        mesh = named_mesh("Kran")
        sphere = named_mesh("Kran_Sphere")
        sphere.display_type = "WIRE"
        sphere.show_in_front = True
        hide_all_except([mesh, sphere])
        activate_object(mesh)
        sphere.select_set(True)
        configure_viewport(shading="SOLID", wire=False)
        focus_view_three_quarter([mesh, sphere])
        show_sidebar("Sphere Tools")
        set_capture_target("sidebar", "VIEW_3D", context_pixels=720)
    elif mode == "detail_factory_bone_manager":
        force_object_mode()
        mesh = named_mesh("Kran")
        hide_all_except([mesh])
        activate_object(mesh)
        scene = bpy.context.scene
        scene.bone_items.clear()
        item = scene.bone_items.add()
        item.bone_index = "62"
        item.bone_name = "615"
        item.bone_type = "BUILDING"
        item.include_tag = True
        scene.bone_active_index = 0
        configure_viewport(shading="MATERIAL")
        focus_view_three_quarter([mesh])
        show_sidebar("Bone Tools")
        set_capture_target("sidebar", "VIEW_3D", context_pixels=420)
    elif mode == "detail_factory_action_timeline":
        force_object_mode()
        armature = activate_armature()
        if armature.animation_data is None:
            armature.animation_data_create()
        if armature.animation_data.action is None and bpy.data.actions:
            armature.animation_data.action = bpy.data.actions[0]
        action = armature.animation_data.action
        if action is None:
            raise RuntimeError("PB_Factory.blend has no Action for the Action Editor capture")
        scene = bpy.context.scene
        scene.frame_start = int(action.frame_range[0])
        scene.frame_end = int(action.frame_range[1])
        scene.frame_set(scene.frame_start)
        window, screen, main_area, _region = window_and_area("VIEW_3D")
        main_area.type = "DOPESHEET_EDITOR"
        main_area.spaces.active.ui_mode = "ACTION"
        if hasattr(main_area.spaces.active, "show_region_ui"):
            main_area.spaces.active.show_region_ui = False
        main_region = next(candidate for candidate in main_area.regions if candidate.type == "WINDOW")
        with bpy.context.temp_override(window=window, screen=screen, area=main_area, region=main_region):
            bpy.ops.action.view_all()
        timeline_area = min(
            (
                candidate
                for candidate in screen.areas
                if candidate != main_area and candidate.type == "DOPESHEET_EDITOR"
            ),
            key=lambda candidate: candidate.y,
        )
        timeline_area.type = "DOPESHEET_EDITOR"
        timeline_area.ui_type = "TIMELINE"
        x0 = min(main_area.x, timeline_area.x)
        y0 = min(main_area.y, timeline_area.y)
        x1 = max(main_area.x + main_area.width, timeline_area.x + timeline_area.width)
        y1 = max(main_area.y + main_area.height, timeline_area.y + timeline_area.height)
        set_capture_rect(x0, y0, x1, y1)
    elif mode == "detail_unit_overview":
        force_object_mode()
        mesh = focused_unit_mesh()
        hide_all_except([mesh])
        activate_object(mesh)
        configure_viewport(shading="SOLID", wire=False)
        focus_view_three_quarter([mesh])
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_unit_topology":
        force_object_mode()
        mesh = focused_unit_mesh()
        hide_all_except([mesh])
        activate_object(mesh)
        configure_viewport(shading="SOLID", wire=True, xray=False)
        focus_view_three_quarter([mesh])
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.context.tool_settings.mesh_select_mode = (True, False, False)
        bpy.ops.mesh.select_all(action="SELECT")
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_unit_armature":
        force_object_mode()
        mesh = focused_unit_mesh()
        armature = activate_armature()
        armature.show_in_front = True
        armature.data.display_type = "OCTAHEDRAL"
        armature.data.show_names = False
        hide_all_except([mesh, armature])
        for selected in list(bpy.context.selected_objects):
            selected.select_set(False)
        mesh.select_set(True)
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        configure_viewport(shading="SOLID", xray=False)
        focus_view_three_quarter([mesh, armature])
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_unit_weight_paint":
        force_object_mode()
        mesh = focused_unit_mesh()
        choose_informative_weight_group(mesh)
        hide_all_except([mesh])
        activate_object(mesh)
        configure_viewport(shading="SOLID")
        focus_view_three_quarter([mesh])
        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
        set_capture_target("window", "VIEW_3D")
    elif mode == "detail_unit_vertex_groups":
        force_object_mode()
        mesh = focused_unit_mesh()
        choose_informative_weight_group(mesh)
        hide_all_except([mesh])
        show_mesh_data_properties(mesh)
        set_capture_target("properties", "PROPERTIES")
    elif mode == "detail_unit_uv_layout":
        force_object_mode()
        mesh = focused_unit_mesh()
        hide_all_except([mesh])
        make_uv_editor(mesh)
        set_capture_target("editor", "IMAGE_EDITOR")
    elif mode == "detail_unit_selection_sphere":
        force_object_mode()
        mesh = focused_unit_mesh()
        sphere = focused_unit_sphere()
        sphere.display_type = "WIRE"
        sphere.show_in_front = True
        hide_all_except([mesh, sphere])
        for selected in list(bpy.context.selected_objects):
            selected.select_set(False)
        mesh.select_set(True)
        sphere.select_set(True)
        bpy.context.view_layer.objects.active = sphere
        configure_viewport(shading="SOLID")
        focus_view_three_quarter([mesh, sphere])
        bpy.context.view_layer.objects.active = sphere
        set_capture_target("window", "VIEW_3D")
    elif mode == "import_menu":
        window, screen, area, region = window_and_area("VIEW_3D")
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            bpy.ops.wm.call_menu(name="TOPBAR_MT_file_import")
    elif mode == "export_menu":
        window, screen, area, region = window_and_area("VIEW_3D")
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            bpy.ops.wm.call_menu(name="TOPBAR_MT_file_export")
    elif mode in {
        "bone_tools",
        "sphere_tools",
        "particle_tools",
        "geometry_tools",
        "scene_tools",
        "mesh_validation",
        "uv_validation",
        "binmesh_validation",
    }:
        category = {
            "bone_tools": "Bone Tools",
            "sphere_tools": "Sphere Tools",
            "particle_tools": "Particle Tools",
            "geometry_tools": "Geometry Tools",
            "scene_tools": "Scene Tools",
            "mesh_validation": "Geometry Tools",
            "uv_validation": "Geometry Tools",
            "binmesh_validation": "Geometry Tools",
        }[mode]
        show_sidebar(category)
        meshes = [
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and obj.name.startswith("Mesh")
        ]
        if meshes:
            activate_object(meshes[0])
        if mode == "mesh_validation" and meshes:
            bpy.ops.geometry_tools.validate_selected_mesh()
        if mode == "uv_validation" and meshes:
            bpy.ops.geometry_tools.validate_uv()
        if mode == "binmesh_validation" and meshes:
            bpy.ops.geometry_tools.validate_bin_mesh()
        for armature in [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]:
            armature.hide_set(True)
        visible_meshes = [obj for obj in meshes if not obj.hide_get()]
        focus_view(visible_meshes or meshes)
    elif mode == "sphere_generate_dialog":
        show_sidebar("Sphere Tools")
        meshes = [
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and obj.name.startswith("Mesh")
        ]
        if not meshes:
            raise RuntimeError("No imported building mesh available for sphere dialog")
        mesh = max(meshes, key=lambda item: len(item.data.vertices))
        activate_object(mesh)
        for armature in [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]:
            armature.data.show_names = False
            armature.hide_set(True)
        focus_view([mesh], view_axis="FRONT")
        window, screen, area, region = window_and_area("VIEW_3D")
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            result = bpy.ops.object.create_and_parent_sphere("INVOKE_DEFAULT")
            print(f"HANDBOOK_DIALOG mode={mode} result={sorted(result)}", flush=True)
    elif mode == "building_overview":
        for obj in bpy.data.objects:
            if "sphere" in obj.name.lower() or obj.type == "ARMATURE":
                obj.hide_set(True)
        meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.hide_get()]
        focus_view(meshes, view_axis="FRONT")
    elif mode == "unit_overview":
        for obj in bpy.data.objects:
            if "sphere" in obj.name.lower() or obj.type == "ARMATURE":
                obj.hide_set(True)
        meshes = [obj for obj in bpy.data.objects if obj.type == "MESH" and not obj.hide_get()]
        focus_view(meshes, view_axis="FRONT")
    elif mode == "armature_bones":
        armature = activate_armature()
        armature.show_in_front = True
        armature.data.display_type = "BBONE"
        armature.data.show_names = False
        for obj in bpy.data.objects:
            if "sphere" in obj.name.lower():
                obj.hide_set(True)
        meshes = [
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and "selectionsphere" not in obj.name.lower()
        ]
        window, screen, area, region = window_and_area("VIEW_3D")
        for selected in list(bpy.context.selected_objects):
            selected.select_set(False)
        for obj in meshes + [armature]:
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active = armature
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            bpy.ops.view3d.view_axis(type="FRONT", align_active=False)
            bpy.ops.view3d.view_selected(use_all_regions=False)
        bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="SELECT")
    elif mode == "weight_paint":
        mesh = next(
            obj
            for obj in bpy.data.objects
            if obj.type == "MESH" and "selectionsphere" not in obj.name.lower()
        )
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE" or "sphere" in obj.name.lower():
                obj.hide_set(True)
        activate_object(mesh)
        if mesh.vertex_groups:
            mesh.vertex_groups.active_index = 0
        focus_view([mesh], view_axis="FRONT")
        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    elif mode == "mesh_basics":
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE" or "sphere" in obj.name.lower():
                obj.hide_set(True)
        mesh = max(
            (
                obj
                for obj in bpy.data.objects
                if obj.type == "MESH" and obj.name.startswith("Mesh")
            ),
            key=lambda item: len(item.data.vertices),
        )
        activate_object(mesh)
        focus_view([mesh], view_axis="FRONT")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
    elif mode == "animation_tool_unit":
        armature = activate_armature()
        window, screen, area, region = window_and_area("VIEW_3D")
        area.type = "DOPESHEET_EDITOR"
        area.spaces.active.ui_mode = "ACTION"
        show_sidebar("Animation Tool", area_type="DOPESHEET_EDITOR")
        bpy.context.scene.frame_set(20)
        if armature.animation_data and armature.animation_data.action:
            bpy.context.scene.frame_start = int(armature.animation_data.action.frame_range[0])
            bpy.context.scene.frame_end = int(armature.animation_data.action.frame_range[1])
    elif mode.startswith("import_") and mode.endswith("_dialog"):
        window, screen, area, region = window_and_area("VIEW_3D")
        operator, source_path = {
            "import_building_dialog": (bpy.ops.import_model.building, BUILDING_MODEL),
            "import_unit_dialog": (bpy.ops.import_model.unit, UNIT_MODEL),
            "import_building_animation_dialog": (
                bpy.ops.import_anim.building_anm,
                BUILDING_ANIMATION,
            ),
            "import_unit_animation_dialog": (bpy.ops.import_anim.unit_anm, UNIT_ANIMATION),
        }[mode]
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            result = operator("INVOKE_DEFAULT", filepath=str(source_path))
            print(f"HANDBOOK_DIALOG mode={mode} result={sorted(result)}", flush=True)
    elif mode.startswith("export_") and mode.endswith("_dialog"):
        window, screen, area, region = window_and_area("VIEW_3D")
        output_root = REPO_ROOT / "docs" / "handbook" / "_test_output"
        output_root.mkdir(parents=True, exist_ok=True)
        operator, kwargs = {
            "export_building_dialog": (
                bpy.ops.export_model.building,
                {"filepath": str(output_root / "manual-building.dff")},
            ),
            "export_unit_dialog": (
                bpy.ops.export_model.unit,
                {"filepath": str(output_root / "manual-unit.dff")},
            ),
            "export_building_animation_dialog": (
                bpy.ops.export_anim.building_anm,
                {"filepath": str(output_root / "manual-building_600.anm")},
            ),
            "export_unit_animation_dialog": (
                bpy.ops.export_anim.unit_anm,
                {"filepath": str(output_root / "manual-unit-animation.anm")},
            ),
        }[mode]
        if "animation" in mode:
            activate_armature()
        with bpy.context.temp_override(window=window, screen=screen, area=area, region=region):
            result = operator("INVOKE_DEFAULT", **kwargs)
            print(f"HANDBOOK_DIALOG mode={mode} result={sorted(result)}", flush=True)
    elif mode == "preferences_addon":
        window, screen, area, region = window_and_area("VIEW_3D")
        area.type = "PREFERENCES"
        bpy.context.preferences.active_section = "ADDONS"
        area.spaces.active.filter_text = "Novator12"
    else:
        raise ValueError(f"Unknown capture mode: {mode}")

    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    return None


def _area_for_capture(screen, scope: str):
    requested_type = CAPTURE_AREA_TYPE
    if scope == "properties":
        requested_type = "PROPERTIES"
    elif scope == "outliner":
        requested_type = "OUTLINER"
    candidates = [area for area in screen.areas if requested_type is None or area.type == requested_type]
    if not candidates:
        raise RuntimeError(
            f"No capture area of type {requested_type!r}; available: "
            + ", ".join(sorted({area.type for area in screen.areas}))
        )
    return max(candidates, key=lambda area: area.width * area.height)


def _region_screen_rect(area, region):
    # Region x/y are normally window-relative. Some Blender builds expose
    # area-relative values, so accept either representation defensively.
    x = region.x
    y = region.y
    if x < area.x or x + region.width > area.x + area.width:
        x = area.x + region.x
    if y < area.y or y + region.height > area.y + area.height:
        y = area.y + region.y
    return x, y, region.width, region.height


def authentic_crop_spec(window, scope: str):
    screen = window.screen
    screen_width = max(area.x + area.width for area in screen.areas)
    screen_height = max(area.y + area.height for area in screen.areas)
    if screen_width <= 0 or screen_height <= 0:
        raise RuntimeError("Blender screen has invalid dimensions")
    if scope == "rect":
        if CAPTURE_RECT is None:
            raise RuntimeError("Rect capture requested without a configured rectangle")
        x0, y0, x1, y1 = CAPTURE_RECT
        x0 = max(0, min(screen_width, x0))
        y0 = max(0, min(screen_height, y0))
        x1 = max(0, min(screen_width, x1))
        y1 = max(0, min(screen_height, y1))
        if x1 - x0 < 80 or y1 - y0 < 80:
            raise RuntimeError(f"Refusing implausibly small rect capture: {CAPTURE_RECT}")
        return {
            "scope": scope,
            "screen_width": screen_width,
            "screen_height": screen_height,
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
        }
    area = _area_for_capture(screen, scope)

    if scope in {"editor", "properties", "outliner"}:
        x, y, width, height = area.x, area.y, area.width, area.height
    else:
        region_type = "UI" if scope == "sidebar" else "WINDOW"
        region = next((candidate for candidate in area.regions if candidate.type == region_type), None)
        if region is None:
            raise RuntimeError(f"Area {area.type} has no {region_type} region")
        x, y, width, height = _region_screen_rect(area, region)
        if scope == "sidebar":
            context = min(CAPTURE_CONTEXT_PIXELS, max(0, x - area.x))
            x -= context
            width += context

    padding = 6
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(screen_width, x + width + padding)
    y1 = min(screen_height, y + height + padding)
    if x1 - x0 < 80 or y1 - y0 < 80:
        raise RuntimeError(
            f"Refusing implausibly small Blender crop {(x0, y0, x1, y1)} "
            f"from screen {(screen_width, screen_height)} for {scope}"
        )
    return {
        "scope": scope,
        "screen_width": screen_width,
        "screen_height": screen_height,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
    }


def capture():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        if ARGS.mode in FOCUSED_MODES and OUTPUT.exists() and not ARGS.allow_overwrite:
            raise FileExistsError(
                f"Focused capture output already exists: {OUTPUT}. "
                "Pass --allow-overwrite only after reviewing the target."
            )
        windows = list(bpy.context.window_manager.windows)
        target_window = next(
            (
                window
                for window in windows
                if any(area.type == "FILE_BROWSER" for area in window.screen.areas)
            ),
            windows[0],
        )
        scope = CAPTURE_SCOPE if ARGS.capture_scope == "auto" else ARGS.capture_scope
        print(
            "HANDBOOK_WINDOWS="
            + repr([[area.type for area in window.screen.areas] for window in windows]),
            flush=True,
        )
        print(
            "HANDBOOK_ACTIVE_CATEGORIES="
            + repr(
                [
                    region.active_panel_category
                    for window in windows
                    for area in window.screen.areas
                    for region in area.regions
                    if region.type == "UI"
                ]
            ),
            flush=True,
        )
        if scope == "whole":
            screenshot_path = OUTPUT
            crop_spec_path = None
        else:
            screenshot_path = OUTPUT.with_name(f".{OUTPUT.stem}-full.png")
            crop_spec_path = OUTPUT.with_name(f".{OUTPUT.stem}-crop.json")
        with bpy.context.temp_override(window=target_window):
            result = bpy.ops.screen.screenshot(filepath=str(screenshot_path), check_existing=False)
        if scope == "whole":
            capture_result = f"FULL={screenshot_path}"
        else:
            crop_spec = authentic_crop_spec(target_window, scope)
            crop_spec_path.write_text(json.dumps(crop_spec, indent=2), encoding="utf-8")
            capture_result = f"FULL={screenshot_path} CROP_SPEC={crop_spec_path}"
        print(
            f"HANDBOOK_SCREENSHOT={OUTPUT} MODE={ARGS.mode} SCOPE={scope} "
            f"{capture_result} RESULT={sorted(result)}",
            flush=True,
        )
    except Exception:
        traceback.print_exc()
    finally:
        bpy.ops.wm.quit_blender()
    return None


def safe_setup_mode():
    try:
        # Register the capture before invoking modal file-browser/export helpers.
        # Some export helpers retain control until their modal browser closes.
        # Export browsers are captured by the companion PowerShell window-capture
        # helper because Blender 5.0.1 can crash when screen.screenshot is called
        # while an ExportHelper file browser is modal.
        external_capture_mode = (
            (ARGS.mode.startswith("export_") and ARGS.mode.endswith("_dialog"))
            or ARGS.mode == "sphere_generate_dialog"
        )
        if not external_capture_mode:
            if ARGS.delay is not None:
                delay = max(0.5, ARGS.delay)
            elif ARGS.mode in FOCUSED_GENERAL_MODES:
                # Popup menus are modal and can disappear while a longer
                # timer waits. Capture promptly after the redraw so the four
                # add-on entries are deterministically present.
                delay = 0.65
            elif ARGS.mode in FOCUSED_MODES:
                delay = 3.0 if "material" in ARGS.mode or "overview" in ARGS.mode else 1.8
            else:
                delay = 4.0 if ARGS.mode.endswith("_dialog") else 1.5
            bpy.app.timers.register(capture, first_interval=delay)
        return setup_mode()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(safe_setup_mode, first_interval=1.0)
