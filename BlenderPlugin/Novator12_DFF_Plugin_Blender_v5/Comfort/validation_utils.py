from .json_utils import list_or_empty, mapping_or_empty, nested_list, nested_mapping


def format_index_preview(indices, limit=8):
    if not indices:
        return "-"

    preview = ", ".join(str(index) for index in indices[:limit])
    if len(indices) > limit:
        preview += ", ..."
    return preview


def collect_loose_vertex_indices(mesh_object):
    mesh_data = mesh_object.data
    used_vertices = set()
    for polygon in mesh_data.polygons:
        used_vertices.update(polygon.vertices)

    all_vertices = set(range(len(mesh_data.vertices)))
    return sorted(all_vertices - used_vertices)


def validate_mesh_object(mesh_object):
    mesh_data = mesh_object.data
    non_triangle_polygons = []
    degenerate_polygons = []
    loose_vertices = collect_loose_vertex_indices(mesh_object)

    for polygon in mesh_data.polygons:
        polygon_vertices = list(polygon.vertices)
        if len(polygon_vertices) != 3:
            non_triangle_polygons.append(polygon.index)
        if len(set(polygon_vertices)) < len(polygon_vertices):
            degenerate_polygons.append(polygon.index)

    uv_layers = []
    used_vertices = set(range(len(mesh_data.vertices))) - set(loose_vertices)
    tolerance = 1.0e-6
    for layer_index, uv_layer in enumerate(mesh_data.uv_layers):
        vertex_to_uv = {}
        conflicting_vertices = set()

        for polygon in mesh_data.polygons:
            for vertex_index, loop_index in zip(polygon.vertices, polygon.loop_indices):
                uv = uv_layer.data[loop_index].uv
                uv_pair = (float(uv.x), float(uv.y))
                previous_uv = vertex_to_uv.get(vertex_index)
                if previous_uv is None:
                    vertex_to_uv[vertex_index] = uv_pair
                    continue
                if abs(previous_uv[0] - uv_pair[0]) > tolerance or abs(previous_uv[1] - uv_pair[1]) > tolerance:
                    conflicting_vertices.add(vertex_index)

        uv_layers.append({
            "layer_index": layer_index,
            "missing_used_vertices": sorted(vertex for vertex in used_vertices if vertex not in vertex_to_uv),
            "conflicting_vertices": sorted(conflicting_vertices),
        })

    return {
        "mesh_name": mesh_object.name,
        "vertex_count": len(mesh_data.vertices),
        "face_count": len(mesh_data.polygons),
        "uv_layer_count": len(mesh_data.uv_layers),
        "non_triangle_polygons": non_triangle_polygons,
        "degenerate_polygons": degenerate_polygons,
        "loose_vertices": loose_vertices,
        "uv_layers": uv_layers,
    }


def build_mesh_validation_lines(mesh_report):
    lines = [
        f"Mesh: {mesh_report['mesh_name']}",
        f"Vertices: {mesh_report['vertex_count']} | Faces: {mesh_report['face_count']} | UV-Layers: {mesh_report['uv_layer_count']}",
    ]

    if mesh_report["non_triangle_polygons"]:
        lines.append(
            "ERROR: Nicht-triangulierte Faces gefunden. "
            f"Exporter nimmt nur die ersten 3 Vertices. Face-Indizes: {format_index_preview(mesh_report['non_triangle_polygons'])}"
        )
    else:
        lines.append("OK: Alle Faces sind trianguliert.")

    if mesh_report["degenerate_polygons"]:
        lines.append(
            "ERROR: Degenerierte Faces mit doppelten Vertex-Indizes gefunden. "
            f"Face-Indizes: {format_index_preview(mesh_report['degenerate_polygons'])}"
        )

    if mesh_report["loose_vertices"]:
        lines.append(
            "WARN: Lose/unbenutzte Vertices gefunden. "
            f"Vertex-Indizes: {format_index_preview(mesh_report['loose_vertices'])}"
        )
    else:
        lines.append("OK: Keine losen Vertices gefunden.")

    if mesh_report["uv_layer_count"] == 0:
        lines.append("WARN: Keine UV-Layer vorhanden.")
    else:
        for uv_layer in mesh_report["uv_layers"]:
            layer_index = uv_layer["layer_index"]
            if uv_layer["missing_used_vertices"]:
                lines.append(
                    f"ERROR: UV-Layer {layer_index} hat benutzte Vertices ohne UV. "
                    f"Vertex-Indizes: {format_index_preview(uv_layer['missing_used_vertices'])}"
                )
            else:
                lines.append(f"OK: UV-Layer {layer_index} deckt alle benutzten Vertices ab.")

            if uv_layer["conflicting_vertices"]:
                lines.append(
                    f"WARN: UV-Layer {layer_index} hat Vertex->UV-Konflikte an Seams. "
                    "Der Exporter speichert nur einen UV-Wert pro Vertex. "
                    f"Vertex-Indizes: {format_index_preview(uv_layer['conflicting_vertices'])}"
                )
            else:
                lines.append(f"OK: UV-Layer {layer_index} hat keine Vertex->UV-Konflikte.")

    return lines


def mesh_validation_icon(line):
    if line.startswith("OK:"):
        return "CHECKMARK"
    if line.startswith("ERROR:"):
        return "CANCEL"
    if line.startswith("WARN:"):
        return "ERROR"
    return "INFO"


def _validate_export_geometry(geometry_index, geometry):
    issues = []
    morph_targets = list_or_empty(mapping_or_empty(geometry).get("morphTargets"))
    morph_target = mapping_or_empty(morph_targets[0]) if morph_targets else {}
    vertices = list_or_empty(morph_target.get("vertices"))
    triangles = list_or_empty(mapping_or_empty(geometry).get("triangles"))
    materials = list_or_empty(mapping_or_empty(geometry).get("materials"))
    texture_layers = list_or_empty(mapping_or_empty(geometry).get("textureCoordinates"))
    vertex_count = len(vertices)

    used_vertex_indices = set()
    for triangle_index, triangle in enumerate(triangles):
        for key in ("v1", "v2", "v3"):
            try:
                vertex_index = int(mapping_or_empty(triangle)[key])
            except Exception:
                issues.append(f"ERROR: Geometry {geometry_index} Triangle {triangle_index} hat keinen gueltigen {key}-Index.")
                continue
            if vertex_index < 0 or vertex_index >= vertex_count:
                issues.append(
                    f"ERROR: Geometry {geometry_index} Triangle {triangle_index} referenziert Vertex {vertex_index}, "
                    f"aber es gibt nur {vertex_count} Vertices."
                )
            used_vertex_indices.add(vertex_index)

        material_id = mapping_or_empty(triangle).get("materialId")
        if materials and material_id is not None:
            try:
                material_id = int(material_id)
            except Exception:
                issues.append(f"ERROR: Geometry {geometry_index} Triangle {triangle_index} hat eine ungueltige materialId.")
                continue
            if material_id < 0 or material_id >= len(materials):
                issues.append(
                    f"ERROR: Geometry {geometry_index} Triangle {triangle_index} referenziert Material {material_id}, "
                    f"aber es gibt nur {len(materials)} Materialien."
                )

    if triangles and not materials:
        issues.append(f"ERROR: Geometry {geometry_index} hat Triangles, aber keine Materialdaten.")

    for material_index, material in enumerate(materials):
        if not isinstance(material, dict):
            issues.append(f"ERROR: Geometry {geometry_index} Material {material_index} ist kein gueltiges Objekt.")

    for layer_index, layer in enumerate(texture_layers):
        if not isinstance(layer, list):
            issues.append(f"ERROR: Geometry {geometry_index} UV-Layer {layer_index} ist keine Liste.")
            continue
        if len(layer) != vertex_count:
            issues.append(
                f"ERROR: Geometry {geometry_index} UV-Layer {layer_index} hat {len(layer)} Eintraege, "
                f"aber {vertex_count} Vertices."
            )
        for vertex_index in sorted(used_vertex_indices):
            if vertex_index >= len(layer):
                issues.append(
                    f"ERROR: Geometry {geometry_index} UV-Layer {layer_index} fehlt Vertex {vertex_index}."
                )
                continue
            uv = layer[vertex_index]
            if not isinstance(uv, dict) or "u" not in uv or "v" not in uv:
                issues.append(
                    f"ERROR: Geometry {geometry_index} UV-Layer {layer_index} hat an Vertex {vertex_index} keinen gueltigen UV-Eintrag."
                )

    return issues


def _validate_hanim_extensions(frames):
    issues = []
    hanim_frame_indices = {}
    hierarchy_roots = []

    for frame_index, frame_entry in enumerate(frames):
        frame_data = nested_mapping(frame_entry, "frame")
        extension = nested_mapping(frame_entry, "extension")
        hanim_plg = nested_mapping(extension, "hanimPLG")
        node_id = hanim_plg.get("nodeID")
        if node_id is not None:
            hanim_frame_indices[frame_index] = int(node_id)

        nodes = nested_list(extension, "hanimPLG", "nodes")
        parents = nested_list(extension, "hanimPLG", "parents")
        if not nodes and not parents:
            continue

        hierarchy_roots.append(frame_index)
        if not nodes or not parents:
            issues.append(f"ERROR: Frame {frame_index} hat eine unvollstaendige HAnim-Hierarchie.")
            continue
        if len(nodes) != len(parents):
            issues.append(
                f"ERROR: Frame {frame_index} HAnim hat {len(nodes)} nodes, aber {len(parents)} parents."
            )
            continue

        node_indices = []
        node_ids = []
        for node in nodes:
            node = mapping_or_empty(node)
            try:
                node_indices.append(int(node["nodeIndex"]))
                node_ids.append(int(node["nodeID"]))
            except Exception:
                issues.append(f"ERROR: Frame {frame_index} HAnim enthaelt ungueltige node-Eintraege.")
                continue

        if len(node_indices) != len(set(node_indices)):
            issues.append(f"ERROR: Frame {frame_index} HAnim hat doppelte nodeIndex-Werte.")
        if len(node_ids) != len(set(node_ids)):
            issues.append(f"ERROR: Frame {frame_index} HAnim hat doppelte nodeID-Werte.")

        root_count = 0
        node_index_set = set(node_indices)
        for parent_index in parents:
            try:
                parent_index = int(parent_index)
            except Exception:
                issues.append(f"ERROR: Frame {frame_index} HAnim enthaelt ungueltige Parent-Eintraege.")
                continue
            if parent_index == -1:
                root_count += 1
            elif parent_index not in node_index_set:
                issues.append(
                    f"ERROR: Frame {frame_index} HAnim referenziert Parent-NodeIndex {parent_index}, der nicht existiert."
                )

        if root_count != 1:
            issues.append(f"ERROR: Frame {frame_index} HAnim hat {root_count} Roots statt genau einem.")

        parent_frame_index = frame_data.get("parentFrameIndex", -1)
        if parent_frame_index in hanim_frame_indices:
            issues.append(
                f"ERROR: Frame {frame_index} traegt eine HAnim-Root-Hierarchie, ist aber Child von HAnim-Frame {parent_frame_index}."
            )

    if len(hierarchy_roots) > 1:
        issues.append(
            "WARN: Mehrere Frames mit vollstaendigen HAnim-Hierarchien gefunden. "
            f"Frame-Indizes: {format_index_preview(hierarchy_roots)}"
        )

    return issues


def _validate_atomic_extensions(atomics, geometries):
    issues = []

    for atomic_index, atomic in enumerate(atomics):
        atomic_mapping = mapping_or_empty(atomic)
        extension = mapping_or_empty(atomic_mapping.get("extension"))
        if not extension:
            extension = {}

        right_to_render = extension.get("RightToRender")
        if isinstance(right_to_render, str):
            issues.append(
                f"ERROR: Atomic {atomic_index} verwendet RightToRender als String ('{right_to_render}'). "
                "Der Converter erwartet hier kein String-Format."
            )

        geometry_index = atomic_mapping.get("geometryIndex", -1)
        geometry = geometries[geometry_index] if isinstance(geometry_index, int) and 0 <= geometry_index < len(geometries) else {}
        geometry_material_fx = False
        for material in list_or_empty(mapping_or_empty(geometry).get("materials")):
            material_extension = mapping_or_empty(mapping_or_empty(material).get("extension"))
            if "MaterialFXMat" in material_extension or "MaterialUVAnim" in material_extension:
                geometry_material_fx = True
                break

        if geometry_material_fx and "MaterialFXAtomic_EffectsEnabled" not in extension:
            issues.append(
                f"ERROR: Atomic {atomic_index} referenziert Geometry {geometry_index} mit MaterialFX-Material, "
                "hat aber kein MaterialFXAtomic_EffectsEnabled im Atomic-Extension-Block."
            )

        particle_payload = None
        if "ParticleStandard" in extension:
            particle_payload = mapping_or_empty(extension.get("ParticleStandard"))
        elif "Emitters" in extension:
            particle_payload = extension
            issues.append(
                f"ERROR: Atomic {atomic_index} verwendet Flags/Emitters direkt in atomic.extension. "
                "Der S5Converter erwartet hier extension.ParticleStandard."
            )

        if not particle_payload:
            continue

        for emitter_index, emitter in enumerate(list_or_empty(particle_payload.get("Emitters"))):
            emitter_standard = mapping_or_empty(mapping_or_empty(emitter).get("EmitterStandard"))
            if not emitter_standard:
                continue

            particle_texture = mapping_or_empty(emitter_standard.get("ParticleTexture"))
            if particle_texture:
                if "TexPadding" not in particle_texture:
                    issues.append(
                        f"ERROR: Atomic {atomic_index} Emitter {emitter_index} hat keine ParticleTexture.TexPadding."
                    )
                if "TextureAlphaPadding" not in particle_texture:
                    issues.append(
                        f"ERROR: Atomic {atomic_index} Emitter {emitter_index} hat keine ParticleTexture.TextureAlphaPadding."
                    )

            if "ParticleSize_SeriMisstake" in emitter_standard:
                issues.append(
                    f"ERROR: Atomic {atomic_index} Emitter {emitter_index} verwendet den Legacy-Key "
                    "'ParticleSize_SeriMisstake'. Erwartet wird 'ParticleSizeSeriMisstake'."
                )
            elif "ParticleSize" in emitter_standard and "ParticleSizeSeriMisstake" not in emitter_standard:
                issues.append(
                    f"WARN: Atomic {atomic_index} Emitter {emitter_index} hat ParticleSize, aber kein "
                    "ParticleSizeSeriMisstake."
                )

    return issues


def validate_export_payload(payload):
    issues = []
    clump = nested_mapping(payload, "clump")
    geometries = nested_list(clump, "geometries")
    frames = nested_list(clump, "frames")
    atomics = nested_list(clump, "atomics")

    for geometry_index, geometry in enumerate(geometries):
        issues.extend(_validate_export_geometry(geometry_index, geometry))

    issues.extend(_validate_hanim_extensions(frames))
    issues.extend(_validate_atomic_extensions(atomics, geometries))
    return issues


def raise_for_export_preflight(payload, prefix):
    issues = validate_export_payload(payload)
    errors = [issue for issue in issues if issue.startswith("ERROR:")]
    if errors:
        preview = "\n".join(errors[:12])
        raise RuntimeError(f"{prefix}:\n{preview}")
