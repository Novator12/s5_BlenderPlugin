# The Settlers 5 - Novator12 DFF - Tool Handbook

## Verification Test Report

**Blender:** 5.0.1  
**Add-on:** Novator12 DFF Plugin Blender v5, version 3.2.1  
**Language:** English  
**Report date:** 2026-08-11  
**Runtime platform:** Windows

## 1. Purpose

This report records the revised runtime evidence used by the handbook. It separates the configured PB_Factory Building results from the pu_leadersword4 Unit results so that a successful building round trip cannot be mistaken for unit support.

The report covers Blender/add-on/converter integration. It does not certify game behavior.

## 2. Status definitions

| Status | Meaning |
|---|---|
| **PASS** | The stated operation completed and produced the stated inspectable result. |
| **FAIL** | The operation was executed and ended with the recorded error or missing required result. |
| **NOT RUN** | A prerequisite result did not exist, so the dependent test could not be performed. |
| **NOT TESTED** | No suitable test input was supplied or the operation was outside this revised audit. |

A non-empty exported file is useful integration evidence, but it is not automatically semantically correct. Binary output is accepted only as a Blender-side round trip when it can be imported into a clean matching scene and compared with the source structure.

## 3. Method and evidence boundaries

The revised checks used the actual add-on in Blender 5.0.1 and the bundled `S5Converter.exe` for binary output.

The method was:

1. preserve the source asset or configured `.blend`;
2. inspect and record the imported/configured Blender state;
3. export readable JSON;
4. attempt the matching binary export;
5. when binary output existed, import it into a clean matching Blender state; and
6. compare principal object, hierarchy, geometry, bound, and Action evidence.

The checks did not compare binary files byte for byte. They did not test every asset, every possible edit, or every Blender version.

> **No in-game test was performed.** No result in this report proves rendering, culling, collision, selection, animation timing, or gameplay behavior inside *The Settlers 5*.

---

# 4. PB_Factory Building Results

## 4.1 Test asset and configured source state

**Source scene:** `docs/handbook/_test/PB_Factory.blend`

PB_Factory is a configured Blender building example, not a claim that every imported building has the same structure.

| Inventory item | Verified source value |
|---|---:|
| Blender objects | 73 |
| Armature objects | 1 (`Armature_Skin`) |
| Mesh objects | 72 |
| Geometry-record meshes | 36 |
| Sphere/helper meshes | 36 |
| Geometry vertices | 9,200 |
| Geometry edges | 13,067 |
| Geometry faces | 5,660 |
| Triangulation | All 36 Geometry meshes triangulated |
| Armature bones | 82; root `frame_000` |
| Assigned materials | 8 |
| Geometry Tools records | 36 |
| Bone Manager records | 3 |
| Particle Tools records | 2 |
| Actions | 1 (`Armature_SkinAction`) |

The 36 helper meshes represent building bounds/helpers and are not included in the 9,200-vertex or 5,660-face render-Geometry totals.

## 4.2 PB_Factory model export and re-import

| ID | Test | Status | Evidence |
|---|---|---|---|
| B-M01 | Open and inspect configured source | **PASS** | `Armature_Skin`, 36 Geometry records, 3 Bone Manager mappings, 2 Particle records, and 36 sphere/helpers present |
| B-M02 | Export building JSON | **PASS** | `_revision_test_output/building/PB_Factory_revision.json`, 8,673,678 bytes |
| B-M03 | Export building DFF | **PASS** | `_revision_test_output/building/PB_Factory_revision.dff`, 468,825 bytes |
| B-M04 | Import exported DFF into a clean Blender state | **PASS** | Import completed and recreated the principal building structure |
| B-M05 | Compare clean re-import counts | **PASS** | 73 objects, 82 bones, 36 Geometry records, 9,200 Geometry vertices, 5,660 Geometry faces, and 36 spheres |

### Building model conclusion

The PB_Factory model JSON export, DFF export, and clean DFF re-import passed. The principal source and re-import counts agree for the recorded structure.

This is a structural Blender/add-on/converter result for PB_Factory. It is not evidence of byte identity or universal building compatibility.

## 4.3 PB_Factory Action baseline

The configured source contains `Armature_SkinAction`:

| Action property | Verified value |
|---|---|
| Frame range | `0–144` |
| Scene playback rate | 24 FPS |
| F-curves | 30 |
| Keyframe points | 150 |
| Key times | `0`, `24`, `64`, `104`, `144` |
| Animated bones | `frame_052_605`, `frame_053_606`, `frame_054_607` |
| NLA tracks | None |
| Stored `s5_*` Action metadata | None |

The Action contains location, quaternion-rotation, and scale curves. The current exporter writes translation and quaternion rotation; the test does not claim preservation of scale curves.

## 4.4 PB_Factory animation export and re-import

| ID | Test | Status | Evidence |
|---|---|---|---|
| B-A01 | Export building animation JSON | **PASS** | `_revision_test_output/building/PB_Factory_600_revision.json`, 2,652,031 bytes |
| B-A02 | Export building ANM | **PASS** | `_revision_test_output/building/PB_Factory_600_revision.anm`, 167,612 bytes |
| B-A03 | Import exported ANM onto a clean matching PB_Factory rig | **PASS** | Import completed and created an Action |
| B-A04 | Compare imported Action range | **PASS** | Re-imported range `0–144` |

Automatic root resolution selected node ID `603` for this hierarchy. That is an asset-specific result, not a universal root value.

### Building animation conclusion

PB_Factory animation JSON/ANM creation and clean ANM re-import passed. The re-imported Action range matched `0–144`.

The source scene uses 24 FPS. The result does not prove correct game duration, scale-channel preservation, or in-game motion.

## 4.5 PB_Factory overall status

| Area | Result |
|---|---|
| Configured building scene inspection | **PASS** |
| Building JSON export | **PASS** |
| Building DFF export | **PASS** |
| Clean DFF re-import | **PASS** |
| Principal model count comparison | **PASS** |
| Building animation JSON export | **PASS** |
| Building ANM export | **PASS** |
| Clean ANM re-import | **PASS** |
| In-game building test | **NOT TESTED** |

---

# 5. pu_leadersword4 Unit Results

## 5.1 Test asset and imported inventory

**Source model:** `docs/handbook/_test/pu_leadersword4.dff`

The source was imported with the dedicated Unit importer.

| Inventory item | Verified imported value |
|---|---:|
| Blender objects | 3 |
| Armature object | `Armature_UnitSkin` |
| Armature bones | 41 |
| Body object | `pu_leadersword4` |
| Body vertices | 752 |
| Body edges | 1,622 |
| Body faces | 905, all triangles |
| Vertex groups | 39 |
| Armature modifier | Present; targets `Armature_UnitSkin` |
| Marked selection sphere | Present |
| Geometry Tools records | None; unit import does not populate the building list |
| Action | None |

## 5.2 Unit model import and JSON export

| ID | Test | Status | Evidence |
|---|---|---|---|
| U-M01 | Import original `pu_leadersword4.dff` | **PASS** | Three imported objects, 41-bone armature, body inventory above, and marked selection sphere |
| U-M02 | Export unit JSON | **PASS** | `_revision_test_output/unit/pu_leadersword4_revision.json`, 1,057,469 bytes |

The JSON result is the successful diagnostic model output for this sample.

## 5.3 Unit DFF export failure

| ID | Test | Status | Evidence |
|---|---|---|---|
| U-M03 | Export unit DFF | **FAIL** | Bundled converter rejected generated `RpSkin.NumBones`; no DFF file was produced |
| U-M04 | Re-import exported unit DFF | **NOT RUN** | Dependent test could not start because U-M03 produced no DFF |

The first line of the recorded exception is:

```text
System.Text.Json.JsonException: The JSON property 'NumBones' could not be mapped to any .NET member contained in type 'S5Converter.Geometry.RpSkin'.
```

### Failure interpretation

This is a confirmed schema-compatibility failure between the generated unit JSON and the bundled converter's `RpSkin` mapping. It is **not** evidence of a maximum-bone limit.

Do not rename the successful JSON to `.dff` or create a placeholder binary. A unit DFF round trip can be claimed only after schema compatibility is corrected, a real DFF is produced, and that DFF is imported into a clean Blender state successfully.

## 5.4 Unit animation scope

No matching unit ANM sample was supplied for `pu_leadersword4.dff`. The imported model contained no Action and retained the default Blender scene timing state.

| ID | Test | Status | Reason |
|---|---|---|---|
| U-A01 | Import matching unit ANM | **NOT TESTED** | No unit ANM sample was available |
| U-A02 | Export unit animation JSON | **NOT TESTED** | No imported or authored sample Action was available |
| U-A03 | Export unit ANM | **NOT TESTED** | No sample Action was available |
| U-A04 | Re-import exported unit ANM | **NOT TESTED** | No unit ANM output existed |

No output size, PASS status, root behavior, compression behavior, or round-trip claim is made for revised unit animation testing.

## 5.5 pu_leadersword4 overall status

| Area | Result |
|---|---|
| Unit DFF import | **PASS** |
| Unit inventory inspection | **PASS** |
| Unit JSON export | **PASS** — 1,057,469 bytes |
| Unit DFF export | **FAIL** — exact `RpSkin.NumBones` converter-schema error |
| Unit DFF re-import | **NOT RUN** — no DFF produced |
| Unit ANM import/export/re-import | **NOT TESTED** — no sample |
| In-game unit test | **NOT TESTED** |

---

# 6. Consolidated Results

| Asset family | JSON | Binary export | Clean binary re-import | Animation | In-game |
|---|---|---|---|---|---|
| PB_Factory Building model | **PASS** | DFF **PASS** | DFF **PASS** | JSON/ANM export **PASS**; ANM re-import **PASS** | **NOT TESTED** |
| pu_leadersword4 Unit model | **PASS** | DFF **FAIL** on `RpSkin.NumBones` | **NOT RUN** | Unit ANM **NOT TESTED**; no sample | **NOT TESTED** |

The PB_Factory PASS results must not be generalized to unit binary output. The pu_leadersword4 JSON PASS must not be reported as DFF PASS.

# 7. Final Evidence Statement

The revised evidence supports these precise statements:

- PB_Factory Building JSON and DFF export passed.
- The exported PB_Factory DFF re-imported cleanly with matching principal structural counts.
- PB_Factory building animation JSON and ANM export passed.
- The exported PB_Factory ANM re-imported on a clean matching rig with Action range `0–144`.
- pu_leadersword4 DFF import passed and produced the recorded three-object, 41-bone unit inventory.
- pu_leadersword4 JSON export passed and produced 1,057,469 bytes.
- pu_leadersword4 DFF export failed with the exact unmapped `RpSkin.NumBones` exception, produced no DFF, and therefore had no DFF re-import.
- No unit ANM sample was available, so revised unit animation behavior was not tested.
- No in-game test was performed for either asset.

Any broader compatibility claim requires additional assets, edit round trips, converter validation, clean re-imports, and isolated in-game testing.
