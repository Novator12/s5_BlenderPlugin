# The Settlers 5 - Novator12 DFF - Tool Handbook

## Requirement Coverage Matrix

**Blender:** 5.0.1  
**Add-on:** Novator12 DFF Plugin Blender v5, version 3.2.1  
**Language:** English  
**Matrix date:** 2026-08-11

This matrix maps the handbook requirements to the final chapter structure, authentic Blender 5.0.1 figures, and verifiable evidence. Figure paths are defined in Appendix A of the final Markdown handbook. UI figures are genuine Blender 5.0.1 captures of the actual add-on or tested asset state; the menu close-ups use only editorial red outlines to identify the relevant captured rows.

| Requirement | Handbook coverage | Figure coverage | Test or source evidence | Status / acceptance criterion |
|---|---|---|---|---|
| Exact handbook title | Cover: **The Settlers 5 - Novator12 DFF - Tool Handbook** | None | Static Markdown/PDF metadata check | Covered; title must match exactly. |
| Clean cover metadata | Final handbook cover | None; splash image intentionally removed | Blender 5.0.1, add-on 3.2.1, English, edition date 2026-08-11 | Covered; contains only the listed public handbook metadata. |
| Table of contents | `# Contents` before Part I | None | Literal `<!-- PDF_TOC -->`; PDF builder uses multi-pass `TableOfContents` | Covered; generated TOC must resolve chapter page numbers. |
| Beginner-first explanation of Blender objects and data | 2.1–2.2 | Figure 1, `fig-01-mesh-components-detail.png` | Official Blender 5.0 Data-blocks, Outliner, Collections, and Modes documentation | Covered; reader can distinguish Scene, Collection, Object, data-block, and editing modes. |
| Mesh, vertices, edges, faces, and loops | 2.3 | Figure 1 | Blender 5.0 Mesh Introduction, Mesh Structure, and Mesh API | Covered; authentic Edit Mode close-up must label vertex, edge, triangular face, and face-corner/loop concept. |
| Topology, triangles, normals, and winding | 2.4 | Figure 1 | Blender mesh cleanup/normals documentation; Geometry validation rules | Covered; explains triangulation, indices, degenerates, loose geometry, normals, and winding. |
| Materials, textures, and UVs | 2.5; Building chapters 6–7 | Figures 7–8 | PB_Factory material/UV inventory; Geometry metadata and UV validator behavior | Covered; connects Blender slots/UV loops to export metadata and BinMesh. |
| Armatures, bones, frames, and hierarchy | 2.6 | Figure 2, `fig-02-armature-bones-detail.png` | Blender Armature/Bone/Posing manuals; PB_Factory and pu_leadersword4 inventories | Covered; authentic close-up must identify Armature Object, bone, parent/child, head/tail, and frame/node distinction. |
| Vertex groups, weights, rigid versus skinned connection | 2.7; Building chapter 6; Unit chapter 12 | Figure 3, `fig-03-vertex-groups-weights-detail.png`; Figures 18–19 | Building first-group rule; unit export keeps four strongest valid positive influences and normalizes them | Covered; conceptual comparison appears before model-specific operations. |
| Transforms and export space | 2.8; workflow cautions in Parts II–III | Figures 6, 16–18 where relevant | Source behavior: raw mesh/rig data rather than arbitrary evaluated modifier stack | Covered; warns that viewport transforms/modifiers are not automatic export output. |
| Bounds and sphere distinctions | 2.9; 7.2; 13.1–13.2 | Figures 10 and 20 | PB_Factory has 36 building sphere helpers; pu_leadersword4 has one marked SelectionSphere | Covered; does not claim precise in-game collision behavior. |
| DFF/RenderWare structure | 2.10 | Figures 1–3 as Blender-side illustrations | EA RenderWare Graphics 3.5 manuals; add-on Geometry/HAnim/Skin/BinMesh behavior | Covered; Clump, Frame, Geometry, Atomic, Material, BinMesh, HAnim, SkinPLG, and UserData explained. |
| Animation and file-format fundamentals | 2.11–2.12 | Figures 12, 14, 21 | Blender Keyframes/Action Editor/Timeline manuals; S5Converter bridge | Covered; distinguishes DFF, ANM, JSON, Actions, FPS, and converter boundary. |
| Installation and interface tour | Chapter 3 | Figures 4–5, `fig-04-import-menu-detail.png` and `fig-05-export-menu-detail.png` | Blender 5.0 Add-ons documentation; add-on menu registration | Covered; authentic menu close-ups must show all four exact import and export labels. |
| Complete Buildings workflow before Units | Part II, Chapters 4–9 | Figures 6–14 | Heading-order/static review; PB_Factory integration evidence | Covered; no operational Unit workflow interrupts Building import through round trip. |
| PB_Factory worked example and inventory | 4.2–4.4 | Figure 6, `fig-06-pb-factory-overview.png` | 73 objects, 82 bones, 36 Geometry meshes/records, 9,200 vertices, 5,660 triangular faces, 36 spheres, 3 Bone mappings, 2 particles, 1 Action | Covered and verified for the configured scene. |
| Building import, editing, validation, materials, effects, particles, and bounds | Chapters 5–7 | Figures 7–11 | PB_Factory component baselines; Mesh/UV/BinMesh and sphere rules; Bone/Particle records | Covered; workflow steps include prerequisites, expected result, verification, and recovery. |
| Building Action and animation | Chapter 8 | Figure 12 | `Armature_SkinAction`: range 0–144, 24 FPS scene, 30 F-curves, 150 keys, three animated bones | Covered for PB_Factory. |
| Building JSON/DFF export and clean model re-import | Chapter 9 | Figure 13 | JSON PASS 8,673,678 bytes; DFF PASS 468,825 bytes; clean re-import PASS with principal counts matching | Covered and verified structurally. |
| Building JSON/ANM export and clean animation re-import | Chapter 9 | Figure 14 | Animation JSON PASS 2,652,031 bytes; ANM PASS 167,612 bytes; ANM re-import PASS, Action range 0–144 | Covered and verified structurally. |
| Units appear only after complete Building workflow | Part III, Chapters 10–14 | Figures 15–22 | Heading-order/static review | Covered; Units follow Chapter 9. |
| pu_leadersword4 import and inventory | 10.2; Chapter 11 | Figures 15–16 | DFF import PASS; 3 objects, 41 bones, body 752 vertices/1,622 edges/905 triangles, 39 groups, marked selection sphere | Covered and verified. |
| Unit topology, armature, groups, and weights | Chapter 12 | Figures 17–19 | Imported Armature modifier, stored unit payloads, group and four-influence export rules | Covered; edits are explicitly topology-preserving unless metadata is rebuilt and tested. |
| Unit SelectionSphere | 13.1–13.2 | Figure 20 | Imported marked helper parented to body; unit exporter uses marker/location/X dimension | Covered; building Sphere Tools are explicitly excluded as a replacement. |
| Unit animation scope | 13.3–13.5 | Figure 21 | No matching pu_leadersword4 ANM sample; imported model has no Action | Covered as **NOT TESTED**; no false PASS claim. |
| Unit JSON export | 14.2 | Figure 22 | PASS; 1,057,469 bytes | Covered and verified. |
| Unit DFF export limitation | 14.3–14.6; 16.2; 18.5 | Figure 22 | FAIL; exact `System.Text.Json.JsonException` for unmapped `RpSkin.NumBones`; no DFF produced, so re-import NOT RUN | Covered as a confirmed converter-schema limitation, not a bone-count limit. |
| Complete menus and controls reference | Chapter 15 | No additional figure required; workflow figures supply UI context | Static source audit of File, Bone, Sphere, Particle, Geometry, Mesh, UV, BinMesh, Scene, and Animation controls | Covered with exact defaults, required context, Undo, confirmation, and destructive effects. |
| Correct BinMesh terminology | 2.10; 6; 15.10; 16; 17 | Figures 7 where visible | Validator requires indexed data with `Flags.UnIndexed=false`, `Type=TriStrip` | Covered; no “unindexed TriStrip” contradiction. |
| Troubleshooting and limitations, Buildings first | Chapter 16 | None required | Building issues first, followed by Units, Animations, and shared setup/safety | Covered and ordered as required. |
| Glossary | Chapter 17 | None | Cross-check against all technical terms used in Parts I–IV | Covered. |
| References and test evidence | Chapter 18 | None | Official Blender 5.0 docs, EA RenderWare manuals, S5Converter repository, local audit artifacts | Covered with sources and reproducible evidence paths. |
| Authentic Blender 5.0.1 close-ups | Figures 1–22 in the final handbook and Appendix A | Especially Figures 1–5, 7–12, and 15–22 | Screenshot provenance is Blender 5.0.1 with actual add-on/assets; captions define the visible details and identify editorial outlines | Covered; no synthetic UI. |
| No unsupported in-game claim | Chapters 1, 9, 14, 16, and 18; Test Report | None | No in-game test was performed | Covered; Blender/converter round trips are minimum integration evidence only. |

## Acceptance summary

- The final handbook is merged into one English source and one 91-page PDF.
- Chapter order must remain Foundations/Setup → complete Buildings → complete Units → Reference.
- The final PDF must render the TOC, retain readable tables and captions, and contain no missing-image markers.
- All revised figures must be authentic Blender 5.0.1 captures matching their captions.
- PB_Factory Building PASS results and pu_leadersword4 Unit PASS/FAIL/NOT TESTED results must remain clearly separated.
- No unit ANM PASS or in-game PASS may be introduced without new runtime evidence.
