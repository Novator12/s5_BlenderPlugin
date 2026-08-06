from math import isfinite

import bmesh
import bpy

from bpy.types import Operator, Panel

from .constants import SCENE_UV_VALIDATION_REPORT_PROP


UV_TOLERANCE = 1.0e-6
MAX_DFF_VERTEX_COUNT = 65535


def _ensure_object_mode(context):
    if context.mode == "EDIT_MESH" and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode="OBJECT")


def _entry_mesh_object(entry):
    mesh_object = getattr(entry, "mesh_object", None)
    try:
        if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
            return mesh_object
    except ReferenceError:
        pass
    mesh_object = bpy.data.objects.get(str(getattr(entry, "mesh_name", "") or "").strip())
    if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
        return mesh_object
    return None


def _active_mesh_object(context):
    mesh_object = context.active_object
    if mesh_object is not None and mesh_object.type == "MESH" and mesh_object.data is not None:
        return mesh_object

    index = context.scene.geometry_tool_index
    if 0 <= index < len(context.scene.geometry_tool_items):
        return _entry_mesh_object(context.scene.geometry_tool_items[index])
    return None


def _all_geometry_mesh_objects(scene):
    mesh_objects = []
    seen = set()
    for entry in scene.geometry_tool_items:
        mesh_object = _entry_mesh_object(entry)
        if mesh_object is None or mesh_object.as_pointer() in seen:
            continue
        seen.add(mesh_object.as_pointer())
        mesh_objects.append(mesh_object)
    return mesh_objects


def _pairs_differ(first, second):
    return (
        abs(first[0] - second[0]) > UV_TOLERANCE
        or abs(first[1] - second[1]) > UV_TOLERANCE
    )


def _uv_layer_coordinates(uv_layer, expected_count=None):
    modern_values = getattr(uv_layer, "uv", None)
    legacy_values = getattr(uv_layer, "data", None)

    if expected_count is not None:
        if modern_values is not None and len(modern_values) == expected_count:
            return modern_values, "vector"
        if legacy_values is not None and len(legacy_values) == expected_count:
            return legacy_values, "uv"

    if modern_values is not None and len(modern_values):
        return modern_values, "vector"
    if legacy_values is not None:
        return legacy_values, "uv"
    return (), "vector"


def _add_issue(issues, severity, message, indices=None, index_label="Indices", fixable=False):
    issues.append({
        "severity": severity,
        "message": message,
        "indices": sorted(set(indices or [])),
        "index_label": index_label,
        "fixable": fixable,
    })


def validate_uv_mesh(mesh_object):
    mesh_data = mesh_object.data
    vertex_count = len(mesh_data.vertices)
    face_count = len(mesh_data.polygons)
    loop_count = len(mesh_data.loops)
    issues = []

    used_vertices = set()
    edge_directions = {}
    for polygon in mesh_data.polygons:
        polygon_loops = list(polygon.loop_indices)
        used_vertices.update(polygon.vertices)
        for offset, loop_index in enumerate(polygon_loops):
            next_loop_index = polygon_loops[(offset + 1) % len(polygon_loops)]
            loop = mesh_data.loops[loop_index]
            next_loop = mesh_data.loops[next_loop_index]
            edge_directions.setdefault(loop.edge_index, []).append(
                (loop.vertex_index, next_loop.vertex_index, polygon.index)
            )

    loose_vertices = sorted(set(range(vertex_count)) - used_vertices)
    if loose_vertices:
        _add_issue(
            issues,
            "WARNING",
            "Mesh contains loose vertices.",
            loose_vertices,
            "Vertex indices",
            fixable=True,
        )

    non_manifold_edges = [index for index, uses in edge_directions.items() if len(uses) > 2]
    if non_manifold_edges:
        _add_issue(
            issues,
            "WARNING",
            "Edges are used by more than two faces.",
            non_manifold_edges,
            "Edge indices",
        )

    inconsistent_faces = set()
    for uses in edge_directions.values():
        if len(uses) == 2 and uses[0][:2] == uses[1][:2]:
            inconsistent_faces.update((uses[0][2], uses[1][2]))
    if inconsistent_faces:
        _add_issue(
            issues,
            "WARNING",
            "Adjacent faces have inconsistent winding.",
            inconsistent_faces,
            "Face indices",
            fixable=True,
        )

    invalid_vertex_normals = []
    for vertex in mesh_data.vertices:
        normal = vertex.normal
        if not all(isfinite(float(value)) for value in normal) or normal.length_squared <= UV_TOLERANCE ** 2:
            invalid_vertex_normals.append(vertex.index)
    if invalid_vertex_normals:
        _add_issue(
            issues,
            "ERROR",
            "Vertices have zero or non-finite normals.",
            invalid_vertex_normals,
            "Vertex indices",
            fixable=True,
        )

    invalid_face_normals = []
    for polygon in mesh_data.polygons:
        normal = polygon.normal
        if not all(isfinite(float(value)) for value in normal) or normal.length_squared <= UV_TOLERANCE ** 2:
            invalid_face_normals.append(polygon.index)
    if invalid_face_normals:
        _add_issue(
            issues,
            "ERROR",
            "Faces have zero or non-finite normals.",
            invalid_face_normals,
            "Face indices",
            fixable=True,
        )

    uv_reports = []
    if not mesh_data.uv_layers:
        _add_issue(issues, "ERROR", "Mesh has no UV layers.")
    elif len(mesh_data.uv_layers) > 2:
        _add_issue(
            issues,
            "ERROR",
            f"Mesh has {len(mesh_data.uv_layers)} UV layers, but the DFF exporter supports at most 2.",
        )

    for layer_index, uv_layer in enumerate(mesh_data.uv_layers):
        layer_name = uv_layer.name or f"UV {layer_index}"
        uv_values, coordinate_property = _uv_layer_coordinates(uv_layer, loop_count)
        uv_count = len(uv_values)
        layer_report = {
            "layer_index": layer_index,
            "layer_name": layer_name,
            "uv_count": uv_count,
            "conflicting_vertices": [],
            "invalid_loops": [],
            "discontinuity_edges": [],
            "missing_seam_edges": [],
        }
        uv_reports.append(layer_report)

        if uv_count != loop_count:
            _add_issue(
                issues,
                "ERROR",
                f"UV layer '{layer_name}' has {uv_count} entries, but the mesh has {loop_count} loops.",
            )
            continue

        vertex_to_uv = {}
        conflicting_vertices = set()
        invalid_loops = set()
        edge_uses = {}

        for polygon in mesh_data.polygons:
            polygon_loops = list(polygon.loop_indices)
            for offset, loop_index in enumerate(polygon_loops):
                uv = getattr(uv_values[loop_index], coordinate_property)
                uv_pair = (float(uv.x), float(uv.y))
                if not all(isfinite(value) for value in uv_pair):
                    invalid_loops.add(loop_index)
                    continue

                loop = mesh_data.loops[loop_index]
                previous_uv = vertex_to_uv.get(loop.vertex_index)
                if previous_uv is None:
                    vertex_to_uv[loop.vertex_index] = uv_pair
                elif _pairs_differ(previous_uv, uv_pair):
                    conflicting_vertices.add(loop.vertex_index)

                next_loop_index = polygon_loops[(offset + 1) % len(polygon_loops)]
                next_uv = getattr(uv_values[next_loop_index], coordinate_property)
                next_uv_pair = (float(next_uv.x), float(next_uv.y))
                next_loop = mesh_data.loops[next_loop_index]
                edge_uses.setdefault(loop.edge_index, []).append({
                    loop.vertex_index: uv_pair,
                    next_loop.vertex_index: next_uv_pair,
                })

        discontinuity_edges = set()
        missing_seams = set()
        for edge_index, uses in edge_uses.items():
            if len(uses) != 2:
                continue
            first, second = uses
            discontinuous = any(
                vertex_index not in second or _pairs_differ(uv, second[vertex_index])
                for vertex_index, uv in first.items()
            )
            if discontinuous:
                discontinuity_edges.add(edge_index)
                if not mesh_data.edges[edge_index].use_seam:
                    missing_seams.add(edge_index)

        layer_report["conflicting_vertices"] = sorted(conflicting_vertices)
        layer_report["invalid_loops"] = sorted(invalid_loops)
        layer_report["discontinuity_edges"] = sorted(discontinuity_edges)
        layer_report["missing_seam_edges"] = sorted(missing_seams)

        if invalid_loops:
            _add_issue(
                issues,
                "ERROR",
                f"UV layer '{layer_name}' contains non-finite coordinates.",
                invalid_loops,
                "Loop indices",
                fixable=True,
            )
        if conflicting_vertices:
            _add_issue(
                issues,
                "ERROR",
                f"UV layer '{layer_name}' assigns multiple coordinates to the same mesh vertex.",
                conflicting_vertices,
                "Vertex indices",
                fixable=True,
            )
        if missing_seams:
            _add_issue(
                issues,
                "WARNING",
                f"UV layer '{layer_name}' has discontinuities on edges not marked as seams.",
                missing_seams,
                "Edge indices",
                fixable=True,
            )
    return {
        "mesh_name": mesh_object.name,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "loop_count": loop_count,
        "uv_layer_count": len(mesh_data.uv_layers),
        "uv_layers": uv_reports,
        "issues": issues,
        "valid": not any(issue["severity"] == "ERROR" for issue in issues),
    }


def _sanitize_uv_coordinates(mesh_data):
    changed = False
    for uv_layer in mesh_data.uv_layers:
        uv_values, coordinate_property = _uv_layer_coordinates(
            uv_layer,
            expected_count=len(mesh_data.loops),
        )
        for uv_entry in uv_values:
            coordinate = getattr(uv_entry, coordinate_property)
            x = float(coordinate.x)
            y = float(coordinate.y)
            if not isfinite(x) or not isfinite(y):
                setattr(
                    uv_entry,
                    coordinate_property,
                    (x if isfinite(x) else 0.0, y if isfinite(y) else 0.0),
                )
                changed = True
    return changed


def _apply_bmesh_repairs(
    mesh_data,
    split_edge_indices=None,
    split_vertex_indices=None,
    recalculate_normals=False,
):
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    edges_to_split = set()
    for edge_index in split_edge_indices or []:
        if 0 <= edge_index < len(bm.edges):
            edge = bm.edges[edge_index]
            edge.seam = True
            edges_to_split.add(edge)
    for vertex_index in split_vertex_indices or []:
        if 0 <= vertex_index < len(bm.verts):
            for edge in bm.verts[vertex_index].link_edges:
                edge.seam = True
                edges_to_split.add(edge)
    if edges_to_split:
        bmesh.ops.split_edges(bm, edges=list(edges_to_split))

    loose_vertices = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose_vertices:
        bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")
    if recalculate_normals and bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    bm.to_mesh(mesh_data)
    bm.free()
    mesh_data.update(calc_edges=True, calc_edges_loose=True)


def fix_uv_mesh(mesh_object):
    if mesh_object.data.shape_keys is not None:
        return {
            "changed": False,
            "before": validate_uv_mesh(mesh_object),
            "after": validate_uv_mesh(mesh_object),
            "errors": ["Automatic UV fixing is disabled for meshes with shape keys."],
        }

    if len(mesh_object.data.loops) > MAX_DFF_VERTEX_COUNT:
        return {
            "changed": False,
            "before": validate_uv_mesh(mesh_object),
            "after": validate_uv_mesh(mesh_object),
            "errors": [f"Fix could exceed the DFF vertex limit of {MAX_DFF_VERTEX_COUNT}."],
        }

    if mesh_object.data.users > 1:
        mesh_object.data = mesh_object.data.copy()
    mesh_data = mesh_object.data
    before = validate_uv_mesh(mesh_object)
    if not mesh_data.uv_layers:
        return {
            "changed": False,
            "before": before,
            "after": before,
            "errors": ["Mesh has no UV layer to repair; create and unwrap a UV layer manually."],
        }
    if any(layer["uv_count"] != before["loop_count"] for layer in before["uv_layers"]):
        return {
            "changed": False,
            "before": before,
            "after": before,
            "errors": ["UV corner data is structurally inconsistent and cannot be repaired safely."],
        }

    changed = _sanitize_uv_coordinates(mesh_data)
    split_edges = {
        edge_index
        for layer in before["uv_layers"]
        for edge_index in layer["discontinuity_edges"]
    }
    recalculate_normals = any(
        issue["fixable"]
        and (
            "normal" in issue["message"].lower()
            or "winding" in issue["message"].lower()
        )
        for issue in before["issues"]
    )
    has_fixable_issues = any(issue["fixable"] for issue in before["issues"])
    if split_edges or has_fixable_issues:
        _apply_bmesh_repairs(
            mesh_data,
            split_edge_indices=split_edges,
            recalculate_normals=recalculate_normals,
        )
        changed = True

    after = validate_uv_mesh(mesh_object)
    for _iteration in range(3):
        conflicting_vertices = {
            vertex_index
            for layer in after["uv_layers"]
            for vertex_index in layer["conflicting_vertices"]
        }
        if not conflicting_vertices:
            break
        _apply_bmesh_repairs(mesh_data, split_vertex_indices=conflicting_vertices)
        changed = True
        after = validate_uv_mesh(mesh_object)

    unresolved = [
        issue["message"]
        for issue in after["issues"]
        if issue["severity"] == "ERROR"
    ]
    return {
        "changed": changed,
        "before": before,
        "after": after,
        "errors": unresolved,
    }


def _format_indices(indices, limit=8):
    preview = ", ".join(str(index) for index in indices[:limit])
    return preview + (", ..." if len(indices) > limit else "")


def _report_lines(report):
    lines = [
        f"Mesh: {report['mesh_name']}",
        (
            f"Vertices: {report['vertex_count']} | Faces: {report['face_count']} | "
            f"Loops: {report['loop_count']} | UV Layers: {report['uv_layer_count']}"
        ),
    ]
    if not report["issues"]:
        lines.append("OK: UV layers, seams, and normals are valid.")
        return lines
    for issue in report["issues"]:
        line = f"{issue['severity']}: {issue['message']}"
        if issue["indices"]:
            line += f" {issue['index_label']}: {_format_indices(issue['indices'])}"
        lines.append(line)
    return lines


def _log_report(report):
    for issue in report["issues"]:
        message = f"[UV Validation] Mesh '{report['mesh_name']}': {issue['message']}"
        if issue["indices"]:
            message += f" {issue['index_label']}: " + ", ".join(str(index) for index in issue["indices"])
        print(message)


def _set_report(scene, reports, title):
    lines = [title]
    for report in reports:
        lines.extend(_report_lines(report))
        lines.append("")
        _log_report(report)
    setattr(scene, SCENE_UV_VALIDATION_REPORT_PROP, "\n".join(lines).rstrip())


def _validate_objects(scene, mesh_objects, title):
    reports = [validate_uv_mesh(mesh_object) for mesh_object in mesh_objects]
    _set_report(scene, reports, title)
    return reports


class GEOMETRY_OT_validate_uv(Operator):
    bl_idname = "geometry_tools.validate_uv"
    bl_label = "Validate UV"
    bl_description = "Validates all UV layers, seams, normals, and UV-to-vertex assignments of the active mesh"

    def execute(self, context):
        _ensure_object_mode(context)
        mesh_object = _active_mesh_object(context)
        if mesh_object is None:
            self.report({"ERROR"}, "No active mesh object.")
            return {"CANCELLED"}
        report = _validate_objects(context.scene, [mesh_object], "UV Validation")[0]
        if report["valid"]:
            self.report({"INFO"}, f"UV validation passed for '{mesh_object.name}'.")
        else:
            self.report({"WARNING"}, f"UV validation found errors in '{mesh_object.name}'.")
        return {"FINISHED"}


class GEOMETRY_OT_fix_uv(Operator):
    bl_idname = "geometry_tools.fix_uv"
    bl_label = "Fix UV"
    bl_description = "Repairs safe UV, seam, loose-geometry, and normal problems on the active mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        mesh_object = _active_mesh_object(context)
        if mesh_object is None:
            self.report({"ERROR"}, "No active mesh object.")
            return {"CANCELLED"}
        result = fix_uv_mesh(mesh_object)
        _set_report(context.scene, [result["after"]], "UV Fix Result")
        if result["errors"]:
            self.report({"WARNING"}, f"UV fix for '{mesh_object.name}' left {len(result['errors'])} errors.")
        elif result["changed"]:
            self.report({"INFO"}, f"UV data for '{mesh_object.name}' was fixed and validated.")
        else:
            self.report({"INFO"}, f"No fixable UV problems found in '{mesh_object.name}'.")
        return {"FINISHED"}


class GEOMETRY_OT_validate_all_uv(Operator):
    bl_idname = "geometry_tools.validate_all_uv"
    bl_label = "Validate All UVs"
    bl_description = "Validates UV layers, seams, and normals for all linked Geometry meshes"

    def execute(self, context):
        _ensure_object_mode(context)
        mesh_objects = _all_geometry_mesh_objects(context.scene)
        if not mesh_objects:
            self.report({"ERROR"}, "No linked Geometry meshes found.")
            return {"CANCELLED"}
        reports = _validate_objects(context.scene, mesh_objects, "UV Validation - All Geometry Meshes")
        invalid_count = sum(not report["valid"] for report in reports)
        if invalid_count:
            self.report({"WARNING"}, f"UV validation found errors in {invalid_count} of {len(reports)} meshes.")
        else:
            self.report({"INFO"}, f"UV validation passed for all {len(reports)} meshes.")
        return {"FINISHED"}


class GEOMETRY_OT_fix_all_uv(Operator):
    bl_idname = "geometry_tools.fix_all_uv"
    bl_label = "Fix All UVs"
    bl_description = "Repairs safe UV, seam, loose-geometry, and normal problems on all linked Geometry meshes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ensure_object_mode(context)
        mesh_objects = _all_geometry_mesh_objects(context.scene)
        if not mesh_objects:
            self.report({"ERROR"}, "No linked Geometry meshes found.")
            return {"CANCELLED"}

        results = [fix_uv_mesh(mesh_object) for mesh_object in mesh_objects]
        reports = [result["after"] for result in results]
        _set_report(context.scene, reports, "UV Fix Result - All Geometry Meshes")
        changed_count = sum(result["changed"] for result in results)
        error_count = sum(bool(result["errors"]) for result in results)
        if error_count:
            self.report(
                {"WARNING"},
                f"Fixed {changed_count} meshes; {error_count} meshes still have non-fixable UV errors.",
            )
        else:
            self.report({"INFO"}, f"Fixed and validated {changed_count} of {len(results)} meshes.")
        return {"FINISHED"}


class GEOMETRY_PT_uv_validation(Panel):
    bl_idname = "VIEW3D_PT_geometry_uv_validation"
    bl_label = "UV Validation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Geometry Tools"

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator(GEOMETRY_OT_validate_uv.bl_idname, icon="CHECKMARK", text="Validate")
        row.operator(GEOMETRY_OT_fix_uv.bl_idname, icon="TOOL_SETTINGS", text="Fix UV")
        row = layout.row(align=True)
        row.operator(GEOMETRY_OT_validate_all_uv.bl_idname, icon="CHECKMARK", text="Validate All")
        row.operator(GEOMETRY_OT_fix_all_uv.bl_idname, icon="TOOL_SETTINGS", text="Fix All")

        report = getattr(context.scene, SCENE_UV_VALIDATION_REPORT_PROP, "")
        if report:
            box = layout.box()
            for line in report.splitlines():
                if not line:
                    box.separator(factor=0.5)
                    continue
                if line.startswith("OK:"):
                    icon = "CHECKMARK"
                elif line.startswith("ERROR:"):
                    icon = "CANCEL"
                elif line.startswith("WARNING:"):
                    icon = "ERROR"
                else:
                    icon = "INFO"
                box.label(text=line, icon=icon)
