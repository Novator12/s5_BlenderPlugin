import bpy
import os
import sys
import bmesh
import os.path
import mathutils as mu
import mathutils
import math
import re
import os
import json
import subprocess

from collections import OrderedDict

#Novator Adds:
#UserDataPlg Menü und Im- & Export + UI Panel Stuff
from bpy.types import PropertyGroup
from bpy.props import StringProperty, EnumProperty
from bpy.types import UIList
from bpy.types import Panel
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import CollectionProperty, IntProperty,StringProperty, EnumProperty, BoolProperty

#Spherengenerator
from mathutils import Vector

#Zusatzskripte
#from particle_effects_data import PARTICLE_EFFECT_LUT  #Aktivieren wenn Plugin

#Gobals 
AtomicMaterialFX_Data = {} 
ParticleDataList = {}



# -------------------------------------------------------Import Functions------------------------------------------
# -----------------------------------------------------------------------------------------------------------------
def mul_matrix(mat, mat2):
    if (2, 80, 0) <= bpy.app.version:
        return mat @ mat2;
    else:
        return mat * mat2;

# https://blender.stackexchange.com/questions/9318/set-a-bones-matrix-to-a-custom-matrix

def vec_roll_to_mat3(vec, roll):
    #port of the updated C function from armature.c
    #https://developer.blender.org/T39470
    #note that C accesses columns first, so all matrix indices are swapped compared to the C version

    nor = vec.normalized()
    THETA_THRESHOLD_NEGY = 1.0e-9
    THETA_THRESHOLD_NEGY_CLOSE = 1.0e-5

    #create a 3x3 matrix
    bMatrix = mathutils.Matrix().to_3x3()

    theta = 1.0 + nor[1];

    if (theta > THETA_THRESHOLD_NEGY_CLOSE) or ((nor[0] or nor[2]) and theta > THETA_THRESHOLD_NEGY):

        bMatrix[1][0] = -nor[0];
        bMatrix[0][1] = nor[0];
        bMatrix[1][1] = nor[1];
        bMatrix[2][1] = nor[2];
        bMatrix[1][2] = -nor[2];
        if theta > THETA_THRESHOLD_NEGY_CLOSE:
            #If nor is far enough from -Y, apply the general case.
            bMatrix[0][0] = 1 - nor[0] * nor[0] / theta;
            bMatrix[2][2] = 1 - nor[2] * nor[2] / theta;
            bMatrix[0][2] = bMatrix[2][0] = -nor[0] * nor[2] / theta;

        else:
            #If nor is too close to -Y, apply the special case.
            theta = nor[0] * nor[0] + nor[2] * nor[2];
            bMatrix[0][0] = (nor[0] + nor[2]) * (nor[0] - nor[2]) / -theta;
            bMatrix[2][2] = -bMatrix[0][0];
            bMatrix[0][2] = bMatrix[2][0] = 2.0 * nor[0] * nor[2] / theta;

    else:
        #If nor is -Y, simple symmetry by Z axis.
        bMatrix = mathutils.Matrix().to_3x3()
        bMatrix[0][0] = bMatrix[1][1] = -1.0;

    #Make Roll matrix
    rMatrix = mathutils.Matrix.Rotation(roll, 3, nor)

    #Combine and output result
    mat = mul_matrix(rMatrix, bMatrix)
    return mat

def mat3_to_vec_roll(mat):
    #this hasn't changed
    vec = mat.col[1]
    vecmat = vec_roll_to_mat3(mat.col[1], 0)
    vecmatinv = vecmat.inverted()
    rollmat = mul_matrix(vecmatinv, mat)
    roll = math.atan2(rollmat[0][2], rollmat[2][2])
    return vec, roll  

def set_material(material):
    ob = bpy.context.object
    
    mat = bpy.data.materials.get(material)
    
    if mat is None:
        mat = bpy.data.materials.new(name=material)
    
    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)
    
    return mat

    

def link_object_and_set_active(obj):
    if (2, 80, 0) <= bpy.app.version:
        bpy.context.collection.objects.link(obj)
      #  bpy.context.collection.objects.active = obj
        bpy.context.view_layer.objects.active = obj
    else:
        bpy.context.scene.objects.link(obj)
        bpy.context.scene.objects.active = obj
    
def convert_frame_matrix(frame):
    mat = mu.Matrix()
    mat[0][0] = frame['rotationMatrix'][0]['x']
    mat[0][1] = frame['rotationMatrix'][0]['y']
    mat[0][2] = frame['rotationMatrix'][0]['z']
    mat[1][0] = frame['rotationMatrix'][1]['x']
    mat[1][1] = frame['rotationMatrix'][1]['y']
    mat[1][2] = frame['rotationMatrix'][1]['z']
    mat[2][0] = frame['rotationMatrix'][2]['x']
    mat[2][1] = frame['rotationMatrix'][2]['y']
    mat[2][2] = frame['rotationMatrix'][2]['z']
    mat[0][3] = 0;
    mat[1][3] = 0;
    mat[2][3] = 0;
    mat[3][0] = 0;
    mat[3][1] = 0;
    mat[3][2] = 0;
    mat[3][3] = 1;

    mat[3][0] = frame['position']['x'];
    mat[3][1] = frame['position']['y'];
    mat[3][2] = frame['position']['z'];
    
    return mat

def make_armature_from_frames(js_frames, use_connect):
    print("make_armature_from_frames-Func")
    frames = []
    hierarchy = []
    nodeIDs = []

    userDatas = []
    hanimPLGDatas = []

    for index, frameContainer in enumerate(js_frames):
        frame = frameContainer["frame"];
        
        parent = frame['parentFrameIndex']
        frameMatrix = convert_frame_matrix(frame)

        frameMatrix = frameMatrix.transposed()
        
        frames.append(frameMatrix)
        hierarchy.append(parent)

        extension = frameContainer["extension"]

        nodeID = None
        if extension != None and "hanimPLG" in extension:
            nodeID = extension["hanimPLG"]["nodeID"]

        nodeIDs.append(nodeID)

        userData = None
        # Novator: Wenn User Data vorhanden beim Import wird auch diese verwendet
        if extension != None and "userDataPLG" in extension:
            userDataPLG = extension["userDataPLG"]
            userData = userDataPLG
            
            #for property in userDataPLG:
                #print(property)
                #for value in userDataPLG[property]:
                #    print(value)
        
        userDatas.append(userData)
        #print("Frameindex: {} for UserData : {}".format(parent, userData))   
        
        hanimData = None
        # Novator: Wenn hanimPLG vorhanden beim Import wird auch diese verwendet
        if extension != None and "hanimPLG" in extension:
            hanim_save = extension["hanimPLG"]
            hanimData = hanim_save
            
            #for property in userDataPLG:
                #print(property)
                #for value in userDataPLG[property]:
                #    print(value)
        
        hanimPLGDatas.append(hanimData)
        #print("Frameindex: {} for hanimPLG : {}".format(parent, hanimData))    
        
        # === BoneManager-Eintrag automatisch erzeugen ===
        if hasattr(bpy.context.scene, "bone_items"):
            if nodeID is not None and userData is not None:
                user_props = userData.get("3dsmax User Properties", [])
                bone_type = None

                for prop in user_props:
                    if "Effect=BuildingDecalWithSnow" in prop or "decal=flat" in prop:
                        bone_type = "DECAL"
                        break
                    elif "Effect=SimpleObjectWithSnow" in prop:
                        bone_type = "BUILDING"
                        break

                if bone_type is not None:
                    # Duplikat-Prüfung
                    existing_ids = [b.bone_name for b in bpy.context.scene.bone_items]
                    if str(nodeID) not in existing_ids:
                        new_bone = bpy.context.scene.bone_items.add()
                        new_bone.bone_index = str(index)
                        new_bone.bone_name = str(nodeID)
                        new_bone.bone_type = bone_type
                        print("Neuer Bone gefunden: {}".format(new_bone))
                        bpy.context.scene.bone_active_index = len(bpy.context.scene.bone_items) - 1

                        print("[DEBUG] AutoBoneManager: Hinzugefügt -> ID={}, Typ={}, Index={}".format(nodeID, bone_type, index))

                
        
    arm = bpy.data.armatures.new("Armature_Skin")
    arm_o = bpy.data.objects.new("Armature_Skin", arm)
    link_object_and_set_active(arm_o)
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = arm.edit_bones

    lengthOfNumbers = 3#len(str(len(frames)))

    boneNames = []

    for index in range(len(frames)):
            name = "frame_"
            name = name + str(index).zfill(lengthOfNumbers)
            if (nodeIDs[index] != None):
                name = name + "_" + str(nodeIDs[index])

            boneNames.append(name)
            
            joint = ebs.new(name)
            
            parentFrameIndex = hierarchy[index]
            
            mat4x4 = frames[index]            

            while parentFrameIndex != -1:
                mat4x4 = frames[parentFrameIndex] * mat4x4
                parentFrameIndex = hierarchy[parentFrameIndex]
            
            mat3x3 = mat4x4.to_3x3()
            
            tail, roll = mat3_to_vec_roll(mat3x3)
            boneLength = 100
            joint.head = mat4x4.to_translation()
            joint.tail = tail*boneLength + joint.head
            joint.roll = roll
            
            parent = hierarchy[index]
            if (parent != -1):
                joint.parent = ebs[parent]
                if use_connect:
                    joint.use_connect = True

            if userDatas[index] != None:
                joint["userData"] = userDatas[index]
                
            if hanimPLGDatas[index] != None:
                joint["hanimData"] = hanimPLGDatas[index]


            
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='OBJECT')

    arm.show_names = True
    if (2, 80, 0) <= bpy.app.version:
        arm_o.show_in_front = True;
    else:
        arm_o.show_x_ray = True
    
    return arm_o, boneNames, frames, hierarchy


def read_rigid_geometry(js_geometry, js_clump, arm_o, frameIndex, frameRestMatrix, boneName, use_connect):
    print("read_rigid_geometry-Func")
    print("FrameIndex:{}".format(frameIndex))
    empty_geometry = False 
    
    if len(js_geometry["morphTargets"][0])<=1: #Check auf leere Geometry, wie bei bspw. Particle Effects
        empty_geometry = True     
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='OBJECT')
        
    num_morph_targets = len(js_geometry.get("morphTargets", []))
    if num_morph_targets != 1:
        print("Skipping geometry – expected 1 morphTarget, got", num_morph_targets)
        return
    
        
    bm = bmesh.new()
    wd = bm.verts.layers.deform.verify()
    uvs = bm.loops.layers.uv.verify() #HauptUVLayer 
    
    uvs_snow = None
    
    #Meshname setzen
    mesh = bpy.data.meshes.new("mesh")
    
    uv_coordinates = []
    uv_coordinates_snow = [] #Novator add
    
    if not empty_geometry:
        for textureCoords in js_geometry["textureCoordinates"][0]: # assume one set of texture coordinates...
            uv_coordinates.append((textureCoords["u"], textureCoords["v"]))
        #Novator Additional stuff
        if len(js_geometry["textureCoordinates"]) > 1:
            uvs_snow = bm.loops.layers.uv.new("UVMap_Snow")  # Name des neuen UV-Layers Novator
            for textureCoords in js_geometry["textureCoordinates"][1]: # assume one set of two...
                uv_coordinates_snow.append((textureCoords["u"], textureCoords["v"]))
            
    
    vertex_index = 0;

    if not empty_geometry:
        for json_vertex in js_geometry["morphTargets"][0]["vertices"]:
            x = json_vertex["x"]
            y = json_vertex["y"]
            z = json_vertex["z"]
            
            # geometrie an rest position verschieben...
            xyz = (frameRestMatrix * mu.Vector((x,y,z, 1))).to_3d()
            vertex = bm.verts.new(xyz)
            
            normal = mu.Vector((
                js_geometry["morphTargets"][0]["normals"][vertex_index]["x"],
                js_geometry["morphTargets"][0]["normals"][vertex_index]["y"],
                js_geometry["morphTargets"][0]["normals"][vertex_index]["z"]
            ))
            
            ## TODO does this work?
            vertex.normal = normal
            
            bm.verts.index_update()

            vertex[wd][0] = 1
                    
            vertex_index = vertex_index + 1

        
        
    bm.verts.ensure_lookup_table()

    if not empty_geometry:
        for json_triangle in js_geometry["triangles"]:
            v = json_triangle["v1"]
            v2 = json_triangle["v2"]
            v3 = json_triangle["v3"]
            ## TODO material
            #matIndex = json_triangle["matID"]
            try:
                tvs = [bm.verts[v], bm.verts[v2], bm.verts[v3]]
                face = bm.faces.new(tvs)
                bm.faces.index_update()
                
                for vn in tvs:
                    ln = [l for l in face.loops if l.vert == vn][0] # bei mehreren faces an einem vert schaut das ob es das richtige face ist
                    u0, v0 = [uv_coordinates[vn.index][0], uv_coordinates[vn.index][1]]
                    ln[uvs].uv = (u0, 1.0 - v0)
                    if uv_coordinates_snow:
                        u1, v1 = [uv_coordinates_snow[vn.index][0], uv_coordinates_snow[vn.index][1]]
                        ln[uvs_snow].uv = (u1, 1.0 - v1)
                
            except ValueError as valueError:
                print("caught Error: " + valueError.__str__())
            
  


    bm.to_mesh(mesh)
    bm.free()
    global mesh_count
    mesh_o_name = "Mesh" + str(mesh_count)
    mesh_o = bpy.data.objects.new(mesh_o_name, mesh)
    mesh_count += 1
    
    vgs = mesh_o.vertex_groups

    vgs.new(name=boneName)#"frame_"+str(frameIndex).zfill(stringLengthOfFrames))
        
    arm_mod = mesh_o.modifiers.new(type='ARMATURE', name="skeleton")
    arm_mod.object = arm_o
    
    
    link_object_and_set_active(mesh_o)
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bpy.ops.object.mode_set()
    
    #Material Texture auslesen
    if not empty_geometry:
        tex_name = js_geometry["materials"][0]["textures"][0]["texture"]
        material = set_material(tex_name)
        mesh_o.data.name = tex_name
    else:
        tex_name = "Empty-Geometry"
        mesh_o.data.name = tex_name
        

    
    #Novator Additional stuff: Sphere
    if "sphere" in js_geometry["morphTargets"][0]:
        sphere = js_geometry["morphTargets"][0]["sphere"]
        sphere_center = (sphere["x"], sphere["y"], sphere["z"])
        sphere_radius = sphere["radius"]
        
        if not empty_geometry:
            # Namensgebung basierend auf dem Material-String
            material_texture = js_geometry["materials"][0]["textures"][0]["texture"]
            if "Decals" in material_texture:
                sphere_name = "Decal-Sphere"
            else:
                sphere_name = "Building-Sphere"
        else:
            sphere_name = "Empty-Geometry-Sphere"
            
        # Sphere erstellen
        bpy.ops.mesh.primitive_uv_sphere_add(size=sphere_radius, location=sphere_center)
        sphere_obj = bpy.context.object
        sphere_obj.name = sphere_name

        # Custom Property hinzufügen, um die Sphere mit dem Mesh zu verknüpfen
        #mesh_o["sphere_name"] = sphere_obj.name  # Speichert den Namen der Sphere im Mesh
        #sphere_obj["linked_mesh"] = mesh_o.name  # Speichert den Namen des Meshes in der Sphere

        # Sphere dem Mesh zuordnen (Parenting)
        sphere_obj.parent = mesh_o
        
        # Zusätzliche Eigenschaften der Sphere setzen
        sphere_obj.hide_render = True  # Unsichtbar im Render
        sphere_obj.draw_type = 'WIRE'  # Drahtmodell für Übersicht
        
    # MaterialDataPLG (muss vorher über rwinline erst importiert werden)
    if not empty_geometry:
        geo_tool_item = bpy.context.scene.geometry_tool_items.add()
        geo_tool_item.mesh_name = mesh_o_name
        geo_tool_item.materials.clear()

        # BinMesh nur 1x pro Geometry
        if js_geometry.get('extension') and 'BinMeshPLG' in js_geometry['extension']:
            binmesh = js_geometry['extension']['BinMeshPLG']
            bin_mesh_data = {
                'Flags': binmesh.get('Flags', {}),
                'Meshes': binmesh.get('Meshes', [])
            }
            geo_tool_item.bin_mesh_data = json.dumps(bin_mesh_data)
        else:
            geo_tool_item.bin_mesh_data = "No data"

        # Materials einlesen und auf das GeometryToolItem mappen
        for mat in js_geometry.get('materials', []):
            mat_entry = geo_tool_item.materials.add()

            # Materialname (Textur)
            mat_entry.name = mat.get("textures", [{}])[0].get("texture", "Unknown")
            mat_entry.texture_alpha = mat.get("textures", [{}])[0].get("textureAlpha", "")

            # Surface Props
            mat_entry.ambient = bool(mat.get("SurfaceProps", {}).get("ambient", 1))
            mat_entry.specular = bool(mat.get("SurfaceProps", {}).get("specular", 0))
            mat_entry.diffuse = bool(mat.get("SurfaceProps", {}).get("diffuse", 1))

            # MaterialFX-Erkennung
            mat_fx = mat.get("extension", {}).get("MaterialFXMat", {})
            fx_type = mat_fx.get("Data1", {}).get("Type", "")

            if fx_type == "DualTexture":
                mat_entry.dual_tex = True
                mat_entry.snow_texture = mat_fx.get("Data1", {}).get("Texture1", {}).get("texture", "No data")
            elif fx_type == "UVTransformMat":
                mat_entry.uv_trans = True
                mat_entry.snow_texture = "UVTransformMat"
            else:
                mat_entry.snow_texture = "No data"

    # Leere Geometry (Empty)
    elif empty_geometry:
        geo_tool_item = bpy.context.scene.geometry_tool_items.add()
        geo_tool_item.mesh_name = mesh_o_name
        geo_tool_item.bin_mesh_data = "Empty-Geometry"
        geo_tool_item.materials.clear()

        # Add empty material entry to maintain structure
        mat_entry = geo_tool_item.materials.add()
        mat_entry.name = "Empty-Geometry"
        mat_entry.ambient = False
        mat_entry.specular = False
        mat_entry.diffuse = False
        mat_entry.uv_trans = False
        mat_entry.dual_tex = False
        mat_entry.snow_texture = "Empty-Geometry"
        mat_entry.texture_alpha = ""


    
def read_json_rigid(js, use_connect):
    print("read_json_rigid-Func")
    js_clump = js["clump"]
    arm_o, boneNames, frames, hierarchy = make_armature_from_frames(js_clump["frames"], use_connect)    
    vertexGroups = []
    
    global mesh_count
    mesh_count = 1
    
    for atomic in js_clump["atomics"]:
        frameIndex = atomic["frameIndex"] # frameIndex ist in diesem Kontext gleich dem BoneIndex
        geometryIndex = atomic["geometryIndex"]

        # rest matrix für aktuelles geometry ermitteln
        mat = frames[frameIndex]
        index = hierarchy[frameIndex]
        while hierarchy[index] != -1:
            mat = frames[index] * mat
            index = hierarchy[index]
        frameRestMatrix = mat

        # aktuelle geometry lesen und erstellen
        geometry = js_clump["geometries"][geometryIndex]
        read_rigid_geometry(geometry, js_clump, arm_o, frameIndex, frameRestMatrix, boneNames[frameIndex], use_connect)
        
    # ----------------- Particle Effect Auto-Detection -------------------
    global ParticleDataList
     
    if hasattr(bpy.context.scene, "particle_effects"):
        used_frame_indices = set()

        # Enum-kompatible Effekt-Namen → immer exakt so schreiben wie in EnumProperty
        known_effects = {
            "smoke10",
            "fire02",
            "woodchip",
            "PB_Weathermachine_lightning",
            "sulfur_spray",
            "salimTrapIcon",
            "TMP_resourceGold_Sparkle",
            "XD_StoneSparkles",
            "smoke11",
            "XF_Leaves",
            "smoke12",
            "fire01",
            "firewheel"
        }
        

        for atomic in js_clump["atomics"]:
            frame_index = atomic.get("frameIndex")
            if frame_index in used_frame_indices:
                continue

            extension = atomic.get("extension", {})
            particle_std = extension.get("ParticleStandard", None) 

            if "ParticleStandard" in extension:
                particle_std = extension["ParticleStandard"]
                ParticleDataList[frame_index] = particle_std

                # Ubisoft-Effekt setzen
                new_effect = bpy.context.scene.particle_effects.add()
                new_effect.bone_index = str(frame_index)
                new_effect.effect_type = "Ubisoft"
                bpy.context.scene.particle_effects_index = len(bpy.context.scene.particle_effects) - 1
                used_frame_indices.add(frame_index)
                continue

            elif particle_std and "Emitters" in particle_std:
                for emitter in particle_std["Emitters"]:
                    particle_texture = emitter.get("EmitterStandard", {}).get("ParticleTexture", {})
                    texture_name = particle_texture.get("texture", "").lower()

                    for effect_type in known_effects:
                        if effect_type.lower() in texture_name:
                            new_effect = bpy.context.scene.particle_effects.add()
                            new_effect.bone_index = str(frame_index)
                            new_effect.effect_type = effect_type
                            bpy.context.scene.particle_effects_index = len(bpy.context.scene.particle_effects) - 1
                            used_frame_indices.add(frame_index)

                            print("[DEBUG] Particle Effect erkannt: BoneIndex={}, Type={}".format(
                                new_effect.bone_index, effect_type))
                            break
                    else:
                        continue
                    break

        
    # ----------------- Atomic Entry Auto-Detection -------------------
    global AtomicMaterialFX_Data
    AtomicMaterialFX_Data = globals().get("AtomicMaterialFX_Data", {}) 

    for atomic in js_clump["atomics"]:  
        extension = atomic.get("extension")
        frame_index = atomic.get("frameIndex")

        if extension and "MaterialFXAtomic_EffectsEnabled" in extension:
            if frame_index not in AtomicMaterialFX_Data:
                AtomicMaterialFX_Data[frame_index] = {
                    "MaterialFXAtomic_EffectsEnabled": extension["MaterialFXAtomic_EffectsEnabled"]
                }

                
    # ----------------- Sphären nachträglich ausblenden -------------------
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "Sphere" in obj.name:
            obj.hide = True
            obj.hide_render = True
            print("[DEBUG] Sphere {} wurde ausgeblendet.".format(obj.name))









# -------------------------------------------------------Export Functions------------------------------------------
# ----------------------------------------------------------------------------------------------------------------- 

def generateMatrixFlags(parents):
    print("generateMatrixFlags-Func")
    matrixNeededMoreThanOnce = [None] * len(parents)
    ops = [None] * len(parents)
    
    for i, parent in enumerate(parents):
        n = 0
        for j, parent in enumerate(parents):
            if parents[j] == i:
                n = n + 1
        matrixNeededMoreThanOnce[i] = n
    
    for i, p in enumerate(parents):
        op = None
        
        parent = parents[i]
        
        if parent != -1:
            matrixNeededMoreThanOnce[parent] = matrixNeededMoreThanOnce[parent] - 1
            
            parentneeded = matrixNeededMoreThanOnce[parent]
            selfneeded = matrixNeededMoreThanOnce[i]
            
            if selfneeded == 0 and parentneeded == 0:
                op = 1
            elif selfneeded == 0:
                op = 3
            elif parentneeded == 0:
                op = 0
            else:
                op = 2
        else:
            op = 0
        
        ops[i] = op;
        
    return ops;



def editBoneToMatrix(bone):
    translation = bone.head
    tail = bone.tail - translation
    tail = tail / 100
    roll = bone.roll
    mat3x3 = vec_roll_to_mat3(tail, roll)

    mat4x4 = mat3x3.to_4x4()
    mat4x4.translation = translation

    return mat4x4

def vec3_to_js(vec3):
    val = OrderedDict()
    val["x"] = vec3[0]
    val["y"] = vec3[1]
    val["z"] = vec3[2]
    return val


def bone_name_to_id(boneName):
    nodeID = boneName[10:]
    #print(nodeID, len(nodeID), boneName)
    if len(nodeID) > 0:
        return int(nodeID)
    else:
        return -1
    
def add_to_export_order(nodeIds, exportOrder, startingBoneID):
    for i in range(startingBoneID, startingBoneID + 100):
        if i not in exportOrder:
            if i in nodeIds:
                exportOrder.append(i)

def getAllChildrenBones(hierarchy, parentId):
    ids = []
    for i in range(len(hierarchy)):
        if (hierarchy[i] == parentId):
            ids.append(i)
    return ids

def calculateBoneIds(hierarchy, firstIndex):
    nodeToBoneId = []
    nodeToBoneId.append(firstIndex)

    children = getAllChildrenBones(hierarchy, nodeToBoneId[0])
    for child in reversed(children):
        res = calculateBoneIds(hierarchy, child)
        for j in res:
            nodeToBoneId.append(j)

def calculateBoneIdsByLength(hierarchy, numKeyframes):
    firstBone = len(hierarchy) - numKeyframes
    return calculateBoneIds(hierarchy, firstBone)

def generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas, bone_type_data, hanimPLGDatas):
    print("generate_frame_list-Func")
    frameList = []
    nodeIds = []

    for bone in boneNamesSorted:
        nodeIds.append(bone_name_to_id(bone))

    frameIndexToNodeId = {}
    nodeIdToFrameIndex = {}
    for i in range(len(nodeIds)):
        frameIndexToNodeId[i] = nodeIds[i]
        nodeIdToFrameIndex[nodeIds[i]] = i

    exportOrderAuto = []
    firstBone = nodeIds[1]

    if firstBone >= 500 and firstBone < 600:
        animationBoneIndexToBoneIndex = calculateBoneIdsByLength(hierarchy, len(hierarchy) - 1)
        for i in range(len(animationBoneIndexToBoneIndex)):
            boneID = nodeIds[animationBoneIndexToBoneIndex[i]]
            if boneID in nodeIds and not boneID in exportOrderAuto:
                    exportOrderAuto.append(boneID)
    else:
        exportOrderAuto.append(firstBone)

    add_to_export_order(nodeIds, exportOrderAuto, 600)
    add_to_export_order(nodeIds, exportOrderAuto, 400)
    add_to_export_order(nodeIds, exportOrderAuto, 300)
    add_to_export_order(nodeIds, exportOrderAuto, 200)

    hierarchyRebasedToOne = []
    for parent in hierarchy:
        hierarchyRebasedToOne.append(parent - 1)

    parents = []
    for j, nodeID in enumerate(exportOrderAuto):
        frameIndex = nodeIdToFrameIndex[nodeID]
        #print(nodeID, nodeIdToFrameIndex[nodeID], hierarchy[frameIndex], hierarchyRebasedToOne[frameIndex])

        parent = hierarchy[frameIndex]
        if parent == -1:
            #print(nodeID, nodeIdToFrameIndex[nodeID], "no parent -> -1")
            parents.append(-1)
        else:
            parentNodeID = frameIndexToNodeId[parent]

            index = -1
            for i, nodeID2 in enumerate(exportOrderAuto):
                if parentNodeID == nodeID2:
                    index = i

            parents.append(index)

    for frameIndex in range(len(hierarchy)):
        frame = OrderedDict()
        
        translation = restMatrices[frameIndex].to_translation()
        mat3x3 = restMatrices[frameIndex].to_3x3()

        frame["frame"] = OrderedDict()
        frame["frame"]["parentFrameIndex"] = hierarchy[frameIndex]
        frame["frame"]["position"] = vec3_to_js(translation)
        frame["frame"]["position"]["x"] = translation[0]
        frame["frame"]["position"]["y"] = translation[1]
        frame["frame"]["position"]["z"] = translation[2]
        mat3x3 = mat3x3.transposed()

        frame["frame"]["rotationMatrix"] = []
        frame["frame"]["rotationMatrix"].append(vec3_to_js(mat3x3[0]))
        frame["frame"]["rotationMatrix"].append(vec3_to_js(mat3x3[1]))
        frame["frame"]["rotationMatrix"].append(vec3_to_js(mat3x3[2]))


        extension = OrderedDict()
        
        userData = userDatas[frameIndex]
        hanimData = hanimPLGDatas[frameIndex]
        
        # Novator Update UserDataPLG:
        found_bone = False
        if userData != None:
            extension['userDataPLG'] = userData
        elif bone_type_data != None:
            for bone in bone_type_data:
                if bone['name'] == str(nodeIds[frameIndex]):
                    found_bone = True  # Ein passender Bone wurde gefunden
                    bone_type = bone['type']
                    bone_id = bone['name']
                    bone_index = bone['index']
                    if bone_type == 'DECAL':
                        extension['userDataPLG'] = {'3dsmax User Properties': ['decal=flat', 'Effect=BuildingDecalWithSnow']}
                    elif bone_type == 'BUILDING':
                        extension['userDataPLG'] = {'3dsmax User Properties': ['Effect=SimpleObjectWithSnow']}

                # Standardwert nur setzen, wenn kein passender Bone gefunden wurde
                elif not found_bone and nodeIds[frameIndex] >= 200:
                    extension['userDataPLG'] = {'3dsmax User Properties': ["tag = {}".format(nodeIds[frameIndex])]}
        elif userData == None and nodeIds[frameIndex] >= 200: #Standardwerte setzen wenn keine Bones händisch gesetzt wurden und es keine vorherigen Einträge gibt
            extension['userDataPLG'] = {'3dsmax User Properties': ["tag = {}".format(nodeIds[frameIndex])]}
        
        if frameIndex != 0:
            if hanimData != None:
                extension['hanimPLG'] = hanimData
            else:
                extension['hanimPLG'] = {}
                extension['hanimPLG']['flags'] = {
                    "SubHierarchy": False,
                    "NoMatrices": False,
                    "UpdateModellingMatrices": False,
                    "UpdateLTMs": False,
                    "LocalSpaceMatrices": False
                }
                extension['hanimPLG']['keyFrameSize'] = 0
                extension['hanimPLG']['nodeID'] = nodeIds[frameIndex]
                extension['hanimPLG']['numNodes'] = 0
        
        if frameIndex == 1:
            if hanimData != None:
                extension['hanimPLG'] = hanimData
            else:
                extension['hanimPLG']['numNodes'] = len(parents)
                print("Bone -{} Parents: {}".format(nodeIds[frameIndex],parents))
                extension['hanimPLG']['parents'] = parents
                extension['hanimPLG']['nodes'] = []
                extension['hanimPLG']['flags'] = {
                    "SubHierarchy": False,
                    "NoMatrices": False,
                    "UpdateModellingMatrices": False,
                    "UpdateLTMs": False,
                    "LocalSpaceMatrices": False
                } #28672
                extension['hanimPLG']['keyFrameSize'] = 36

                matrixflags = generateMatrixFlags(parents)

                flag_map = {
                    0: "Deformable",
                    1: "NubBone",
                    2: "Unknown",
                    3: "Rigid"
                }

                for j, nodeID in enumerate(exportOrderAuto):
                    boneIndex = nodeIdToFrameIndex[nodeID]
                    node = OrderedDict()
                    
                    flag_val = matrixflags[j]

                    if flag_val in flag_map:
                        node['flags'] = flag_map[flag_val]
                    else:
                        print("[WARN] Ungültiger HAnimNodeFlags-Wert: {} für NodeID {}".format(flag_val,nodeID))
                        continue  # oder setze Default, z. B. 'Deformable'

                    node['nodeID'] = nodeID
                    node['nodeIndex'] = j
                    
                    extension['hanimPLG']['nodes'].append(node)

                

        frame["extension"] = extension

        frameList.append(frame)

    return frameList


def determine_bone_names_sorted(ob):
    boneNames = determine_bone_names(ob)
    # TODO: Why do they need to be sorted? Why are they unordered in the first place??
    boneNames.sort(key=lambda bone: bone)
    return boneNames

def determine_bone_names(ob):
    
    numBones = len(ob.pose.bones)
    bpy.ops.object.mode_set(mode='EDIT')

    boneNames = []


    for frameIndex in range(numBones):
        bone = ob.data.edit_bones[frameIndex]
        boneNames.append(bone.name)

    bpy.ops.object.mode_set()

    return boneNames

def get_bone_index_by_bone_name(boneNames, name):
    for i in range(len(boneNames)):
        if boneNames[i] == name:
            return i
        
def new_mesh_obj_to_json(mesh_obj, invertedRestMatrix, bone_type_data, geometry_data):
    print("new_mesh_obj_to_json-Func")
    verts_local = [v.co for v in mesh_obj.data.vertices.values()]

    dimensions = mesh_obj.dimensions


    data = OrderedDict()
    data['numMorphTargets'] = 1
    data['numVertices'] = len(verts_local)
        
    mesh_name = mesh_obj.name
    if geometry_data and mesh_obj.name in geometry_data:
        mat_data = geometry_data[mesh_obj.name]
    else:
        mat_data = None    
    # print("Aktuelles Material Data: {}".format(mat_data))
    
    js_vertices = []
    js_normals = []
    
    for vert in verts_local:
        vertex = OrderedDict()

        vtx = vert
        vtx = invertedRestMatrix * vert

        vertex['x'] = vtx[0]
        vertex['y'] = vtx[1]
        vertex['z'] = vtx[2]
        js_vertices.append(vertex)
        
    for vertex in mesh_obj.data.vertices:
        normal = OrderedDict()
        normal['x'] = vertex.normal.x;
        normal['y'] = vertex.normal.y;
        normal['z'] = vertex.normal.z;
        js_normals.append(normal)
    
    data['morphTargets'] = []
    has_vertices = len(js_vertices) > 0
    has_normals = len(js_normals) > 0

    js_morphTarget = {}
    if has_vertices and has_normals:
        js_morphTarget['has_vertices'] = 1
        js_morphTarget['has_normals'] = 1
        js_morphTarget['vertices'] = js_vertices
        js_morphTarget['normals'] = js_normals
    else:
        js_morphTarget['has_vertices'] = 0
        js_morphTarget['has_normals'] = 0
    
    # Novator Export Sphere Stuff
    # Iteriere durch die Kinder des Hauptmeshes
    for sphere in mesh_obj.children:
        # Prüfen, ob die Kinder Sphärendaten enthalten
        if sphere.type == "MESH" and sphere.data and sphere.data.name.startswith("Sphere"):
            js_morphTarget['sphere'] = OrderedDict()
            js_morphTarget['sphere']['x'] = sphere.location.x
            js_morphTarget['sphere']['y'] = sphere.location.y
            js_morphTarget['sphere']['z'] = sphere.location.z
            js_morphTarget['sphere']['radius'] = sphere.dimensions.x / 2  # Radius = Durchmesser / 2
            print("Spheren-Daten {}: x = {}, y = {}, z = {}, radius = {}".format(sphere.name, sphere.location.x, sphere.location.y, sphere.location.z, sphere.dimensions.x / 2))

    data['morphTargets'].append(js_morphTarget)
    
    # Novator12 – Texture Coordinates
    data['textureCoordinates'] = []
    for uv_layer in mesh_obj.data.uv_layers:
        js_textureCoordinates = [None] * data['numVertices']
        has_uvs = False  # Tracke, ob überhaupt gültige UVs gesetzt wurden

        for face in mesh_obj.data.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_coords = uv_layer.data[loop_idx].uv
                uv = OrderedDict()
                uv['u'] = uv_coords.x
                uv['v'] = 1 - uv_coords.y  # Y-Koordinate invertieren
                js_textureCoordinates[vert_idx] = uv
                has_uvs = True

        if has_uvs:
            data['textureCoordinates'].append(js_textureCoordinates)
    
    
    #data['format'] = 65591 # TODO, depends on texture stuff...
    if len(mesh_obj.data.uv_layers) > 1:
        # Mehr als ein UV-Layer | Datenformat: 131251 
        data['format'] = {
            "TriStrip": True,
            "Positions": True,
            "NumTextureCoordinates": 2,
            "PreLit": False,
            "Normals": True,
            "Light": True,
            "ModulateMaterialColor": False,
            "Native": False,
            "NativeInstance": False
        }
    else:
        # Nur ein UV-Layer | Datenformat: 65591
        data['format'] = {
            "TriStrip": True,
            "Positions": True,
            "NumTextureCoordinates": 1,
            "PreLit": False,
            "Normals": True,
            "Light": True,
            "ModulateMaterialColor": False,
            "Native": False,
            "NativeInstance": False
        }
        
    if data['textureCoordinates'] == []: #Wenn leeres Mesh stuff erledigen
        data['format'] = {
          "TriStrip": False,
          "Positions": False,
          "NumTextureCoordinates": 0,
          "PreLit": False,
          "Normals": False,
          "Light": False,
          "ModulateMaterialColor": False,
          "Native": False,
          "NativeInstance": False
        }
    
    #Bin Mesh Data 
    default_flags = {
        "UnIndexed": False,
        "Type": "TriList"
    }
    if mat_data != None:
        bin_mesh_raw = mat_data.get("bin_mesh_data", "No data")
    else:
        bin_mesh_raw = "No data"
    data['extension'] = {}
    if bin_mesh_raw and bin_mesh_raw != "No data":
        try:
            bin_mesh_parsed = json.loads(bin_mesh_raw)
            data['extension']['BinMeshPLG'] = {
                "Flags": bin_mesh_parsed.get("Flags", default_flags),
                "Meshes": bin_mesh_parsed.get("Meshes", [])
            }
        except json.JSONDecodeError:
            print("[WARN] Ungültiges JSON in bin_mesh_data für {}, fallback auf leer.".format(mesh_name))
            data['extension']['BinMeshPLG'] = {
                "Flags": default_flags,
                "Meshes": []
            }
    else:
        data['extension']['BinMeshPLG'] = {
            "Flags": {
              "UnIndexed": False,
              "Type": "TriList"
            },
            "Meshes": []
        }
    
    data['triangles'] = []
    for face in mesh_obj.data.polygons:
        triangle = OrderedDict()
        triangle['v1'] = face.vertices[0]
        triangle['v2'] = face.vertices[1]
        triangle['v3'] = face.vertices[2]
        
        # TODO Material ID
        triangle['materialId'] = 0
    
        data['triangles'].append(triangle)
        
    data['numTris'] = len(data['triangles'])
    
    
    # Anlegen der Material und Texture Einträge in der Geometry
    
    data["materials"] = []

    geo_entry = None
    for item in bpy.context.scene.geometry_tool_items:
        if item.mesh_name == mesh_obj.name:
            geo_entry = item
            break

    if geo_entry is None:
        print("[WARN] Kein Geometry-Eintrag für Mesh '{}' gefunden.".format(mesh_obj.name))
        return data  # oder leeres Material setzen

    
    if any(m.name == "Empty-Geometry" for m in geo_entry.materials):
        data["materials"] = []
    else:
        material_entries = geo_entry.materials

        for mat in material_entries:
            material = OrderedDict()
            material["color"] = {"alpha": 255, "red": 255, "green": 255, "blue": 255}
            material["UnknownInt1"] = 0
            material["UnknownInt2"] = 237627844
            material["SurfaceProps"] = {
                "Ambient": int(mat.ambient),
                "Specular": int(mat.specular),
                "Diffuse": int(mat.diffuse)
            }

            material["extension"] = OrderedDict()

            # FX-Material
            if mat.uv_trans:
                material["extension"]["MaterialFXMat"] = {
                    "Data1": {
                        "Type": "UVTransformMat",
                        "Texture1": None, "Texture2": None,
                        "Coefficient": None, "FrameBufferAlpha": None,
                        "SrcBlendMode": None, "DstBlendMode": None
                    },
                    "Data2": {
                        "Type": "None",
                        "Texture1": None, "Texture2": None,
                        "Coefficient": None, "FrameBufferAlpha": None,
                        "SrcBlendMode": None, "DstBlendMode": None
                    },
                    "Flags": "UVTransform"
                }
                material["extension"]["MaterialUVAnim"] = {
                    "Name": ["13 - Default"]
                }

            elif mat.dual_tex:
                material["extension"]["MaterialFXMat"] = {
                    "Data1": {
                        "Type": "DualTexture",
                        "Texture1": {
                            "texture": mat.snow_texture,
                            "TexPadding": [0],
                            "textureAlpha": "",
                            "TextureAlphaPadding": [0, 116, 28, 196],
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "Texture2": None,
                        "Coefficient": None,
                        "FrameBufferAlpha": None,
                        "SrcBlendMode": "rwBLENDSRCALPHA",
                        "DstBlendMode": "rwBLENDINVSRCALPHA"
                    },
                    "Data2": {
                        "Type": "None",
                        "Texture1": None, "Texture2": None,
                        "Coefficient": None, "FrameBufferAlpha": None,
                        "SrcBlendMode": None, "DstBlendMode": None
                    },
                    "Flags": "DualTexture"
                }

            # TEXTURE
            texture = OrderedDict()
            base_tex_name = re.sub(r'\.\d+$', '', mat.name)
            texture["texture"] = base_tex_name
            texture["textureAlpha"] = mat.texture_alpha
            texture["FilterAddressing"] = 4358
            texture["UnusedInt1"] = 0
            texture["extension"] = {}

            # Padding-Logik
            if mat.texture_alpha == base_tex_name + "alpha":
                texture["TextureAlphaPadding"] = [0, 0]
                texture["TexPadding"] = [0, 0, 0]
            elif mat.uv_trans:
                texture["TextureAlphaPadding"] = [0, 183, 81, 184]
                texture["TexPadding"] = [0, 0]
            else:
                texture["TextureAlphaPadding"] = [0, 7, 46, 196]
                texture["TexPadding"] = [0, 0]

            material["textures"] = [texture]
            data["materials"].append(material)

                
    return data

def get_bone_by_name_(bones, name):
    for bone in bones:
        if bone.name == name:
            return bone
        
def append_atomic(frameIndex,geometryIndex, particle_data, bone_type_data):  #Atomic-Func Novator
    print("append_atomic-Func")

    atomic = OrderedDict()
    atomic["frameIndex"] = frameIndex
    atomic["geometryIndex"] = geometryIndex
    atomic["Flags"] = {
        "CollisionTest": True,
        "RenderShadow": False,
        "Render": True
    }
    atomic["UnknownInt1"] = 0 # ggf. noch anpassen wenn bekannt
    atomic["extension"] = {} 
    
    #----------------Atomic Extension Writer------------------------------
    # Fügt importierte Atomic-Data ein:
    global AtomicMaterialFX_Data
    #print("[DEBUG:] Atomic-Data: {}".format(AtomicMaterialFX_Data))
    if frameIndex in AtomicMaterialFX_Data and "MaterialFXAtomic_EffectsEnabled" in AtomicMaterialFX_Data[frameIndex]:
        atomic["extension"] = {"MaterialFXAtomic_EffectsEnabled": True}
        return atomic
    
    # Bone Match prüfen
    
    #Fügt selbst gesetzte Atomic-Data ein:
    if bone_type_data:
        for bone_data in bone_type_data:
            if str(frameIndex) == bone_data['index']:
                atomic["extension"] = {"MaterialFXAtomic_EffectsEnabled": True}
                return atomic
    
    # Particle Match prüfen
    
    #Fügt importierte Particle-Data ein:
    global ParticleDataList
    if frameIndex in ParticleDataList:
        particle_std = ParticleDataList[frameIndex]
        atomic["extension"]["ParticleStandard"] = particle_std
        return atomic
    
    #Fügt selbst gesetzte Particle-Data ein:    
    if particle_data:
        for particle in particle_data:
            if str(frameIndex) == particle['name']:
                effect_type = particle['type']
                if effect_type in PARTICLE_EFFECT_LUT:
                    atomic["extension"] = PARTICLE_EFFECT_LUT[effect_type]
                    print("[DEBUG] Particle Match: frameIndex={}, type={}".format(frameIndex, effect_type))
                else:
                    print("[WARN] Unbekannter Partikeleffekt: '{}' – kein Eintrag im LUT".format(effect_type))
                return atomic
    
    return atomic
    

def get_json_rigid(bone_type_data, particle_data, geometry_data):
    print("get_json_rigid-Func")
    # armature must be selected!

    sce = bpy.context.scene
    ob = bpy.context.object

        
    #os.system("cls")

    #print(ob)

    #hierarchy, restMatrices = determine_hierarchy_and_rest_matrices(ob)
    boneNamesSorted = determine_bone_names_sorted(ob)
    
    numBones = len(ob.pose.bones)
    # Rest Matrices ermitteln
    bpy.ops.object.mode_set(mode='EDIT')
    hierarchy = []
    restMatrices = []

    userDatas = []
    hanimPLGDatas = []

    sortedBoneList = []
    for bone in ob.data.edit_bones:
        sortedBoneList.append(bone)
    sortedBoneList.sort(key=lambda bone: bone.name)


    for frameIndex in range(len(boneNamesSorted)):



        bone = get_bone_by_name_(ob.data.edit_bones, boneNamesSorted[frameIndex])

        if "userData" in bone:
            userDatas.append(bone["userData"].to_dict())
        else:
            userDatas.append(None)  
        
        if "hanimPLG" in bone:
            hanimPLGDatas.append(bone["hanimPLG"].to_dict())
        else:
            hanimPLGDatas.append(None)  

        parentIndex = -1
        if bone.parent:
            
            for index in range(len(sortedBoneList)):
                if sortedBoneList[index] == bone.parent:
                    parentIndex = index
                    #print(frameIndex, index, bone.parent)
        hierarchy.append(parentIndex)

      #  print(frameIndex, parentIndex)

        mat4x4 = editBoneToMatrix(bone)
        if bone.parent:
            mat4x4 = editBoneToMatrix(bone.parent).inverted() * mat4x4
        restMatrices.append(mat4x4)

        #print(frameIndex, bone)

    bpy.ops.object.mode_set()
    # Rest Matrices & Hierarchy ermittelt


    meshesToExport = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and ob in [m.object for m in obj.modifiers if m.type == 'ARMATURE']:
            meshesToExport.append(obj)


   # print(skin_obj_to_parents(ob))
   # print(hierarchy)


    clump = OrderedDict()
    clump["frames"] = generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas,bone_type_data, hanimPLGDatas)
    clump["atomics"] = []
    clump["geometries"] = []

    #return

    
    geometryIndex = 0
    for mesh in meshesToExport:
        frameIndex = get_bone_index_by_bone_name(boneNamesSorted, mesh.vertex_groups[0].name)


        #print("FrameIndex", frameIndex, mesh.vertex_groups[0].name)

       # print(get_bone_by_name(ob, mesh.vertex_groups[0].name))
       # xyz = (frameRestMatrix * mu.Vector((x,y,z, 1))).to_3d()


        # rest matrix für aktuelles geometry ermitteln
        mat = restMatrices[frameIndex]
        index = hierarchy[frameIndex]
        while hierarchy[index] != -1:
            mat = restMatrices[index] * mat
            #print("parent", index)

            index = hierarchy[index]


        frameRestMatrix = mat

        clump["geometries"].append(new_mesh_obj_to_json(mesh, frameRestMatrix.inverted(), bone_type_data, geometry_data))
        # print("Geometrie-Data {}: {}".format(mesh, clump["geometries"])) # --Debug
        # add geometry to atomics
        atomic = append_atomic(frameIndex,geometryIndex, particle_data, bone_type_data)

        clump["atomics"].append(atomic)
        
        geometryIndex = geometryIndex + 1
    

    js = {}
    js["clump"] = clump

    return js

#------------------------------------------Plugin Info -----------------------------------------------------------------------------------

bl_info = {
    "name": "Novators changed DFF-JSON & ANM-JSON Rigid Model/Animation Imp-/Exporter",
    "location": "File > Import-Export",
    "blender": (2, 80, 0), # meh...
    "category": "Import-Export",
}
    
#-------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------Import Classes-------------------------------------------------------------

class ModelImporterDFF(Operator, ImportHelper):
    bl_idname = "import_model.rigid_dff"
    bl_label = "Novator-Import-Dff (.dff)" #Novator (Wegen multiplen UV Maps)
    filename_ext = "*.dff"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )   
    def execute(self, context):
        print("ModelImporterDFF-Func")
        set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0) # Nova
        read_model(self.filepath)
        return {'FINISHED'}
    
class ModelImporterJSON(Operator, ImportHelper):
    bl_idname = "import_model.rigid_json"
    bl_label = "Novator-Import-JSON (.json)"
    filename_ext = "*.json"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )   
    def execute(self, context):
        print("ModelImporterJSON-Func")
        set_clipping_for_all_screens(clip_start=0.1, clip_end=10000.0)  # Nova
        read_model(self.filepath)
        return {'FINISHED'}
    

#-------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------Export Classes-------------------------------------------------------------

class ModelExporterDFF(Operator, ExportHelper):
    bl_idname = "export_model.rigid_dff"
    bl_label = "Novator-Export-Dff (.dff)"
    bl_description = "Exportiere ein Model im DFF-Format mit User Data PLG | "
    filename_ext = ".dff"

    def execute(self, context):
        # Bone UserDaten exportieren
        bone_type_data = [
            {"index": bone.bone_index, "name": bone.bone_name, "type": bone.bone_type}
            for bone in context.scene.bone_items
        ]
        if bone_type_data == []:
            bone_type_data = None;
        
        # Partikel Daten exportieren
        particle_data = [
            {"name": particle.bone_index, "type": particle.effect_type}
            for particle in context.scene.particle_effects
        ]
        if particle_data == []:
            particle_data = None;
            
        # Material Daten exportieren
        geometry_data = {
            geo.mesh_name: {
                "materials": [
                    {
                        "name": mat.name,
                        "ambient": mat.ambient,
                        "specular": mat.specular,
                        "diffuse": mat.diffuse,
                        "uv_trans": mat.uv_trans,
                        "dual_tex": mat.dual_tex,
                        "snow_texture": mat.snow_texture,
                        "texture_alpha": mat.texture_alpha
                    }
                    for mat in geo.materials
                ],
                "bin_mesh_data": geo.bin_mesh_data
            }
            for geo in context.scene.geometry_tool_items
        }


        if not geometry_data:
            geometry_data = None

        #print("[DEBUG] Exporting with bone data: {}".format(bone_type_data))
        #print("[DEBUG] Exporting with particle data: {}".format(particle_data))
        #print("[DEBUG] Exporting with material data: {}".format(geometry_data))
        write_model(self.filepath, bone_type_data, particle_data, geometry_data)  # Deine Exportfunktion
        return {'FINISHED'}

class ModelExporterJSON(Operator, ExportHelper):
    bl_idname = "export_model.rigid_json"
    bl_label = "Novator-Export-Json (.json)"
    filename_ext = ".json"
    filter_glob = StringProperty(
            default="*" + filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        bone_type_data = [
            {"index": bone.bone_index, "name": bone.bone_name, "type": bone.bone_type}
            for bone in context.scene.bone_items
        ]
        if bone_type_data == []:
            bone_type_data = None;
        
         # Partikel Daten exportieren
        particle_data = [
            {"name": particle.bone_index, "type": particle.effect_type}
            for particle in context.scene.particle_effects
        ]
        if particle_data == []:
            particle_data = None;
        
        # Material Daten exportieren
        geometry_data = {
            geo.mesh_name: {
                "materials": [
                    {
                        "name": mat.name,
                        "ambient": mat.ambient,
                        "specular": mat.specular,
                        "diffuse": mat.diffuse,
                        "uv_trans": mat.uv_trans,
                        "dual_tex": mat.dual_tex,
                        "snow_texture": mat.snow_texture,
                        "texture_alpha": mat.texture_alpha
                    }
                    for mat in geo.materials
                ],
                "bin_mesh_data": geo.bin_mesh_data
            }
            for geo in context.scene.geometry_tool_items
        }


        if not geometry_data:
            geometry_data = None

        #print("[DEBUG] Exporting with bone data: {}".format(bone_type_data))
        #print("[DEBUG] Exporting with particle data: {}".format(particle_data))
        #print("[DEBUG] Exporting with material data: {}".format(geometry_data))
        
        write_model(self.filepath, bone_type_data, particle_data, geometry_data)
        return {'FINISHED'}
    
#----------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------Novator Bone Structur-Handler-------------------------------------------------------------

class DynamicBoneItem(PropertyGroup):
    """Repräsentiert einen Bone-Eintrag"""
    bone_index = StringProperty(name="Bone Index", default="")
    bone_name = StringProperty(name="Bone Name", default="")
    bone_type = EnumProperty(
        name="Type",
        items=[
            ('DECAL', "Decal", "Markiert den Bone als Decal"),
            ('BUILDING', "Building", "Markiert den Bone als Building")
        ],
        default='DECAL'
    )



class DynamicBoneListUIList(UIList):
    """UIList zur Anzeige der Bones"""
    bl_idname = "DYNAMIC_UL_bone_list"  # Dies ist der Name, auf den Blender verweist

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "bone_index", text="Idx")
            layout.prop(item, "bone_name", text="Num")
            layout.prop(item, "bone_type", text="Mat")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'



class BoneManagerPanel(Panel):
    """Panel zur Verwaltung der Bones"""
    bl_idname = "VIEW3D_PT_bone_manager"
    bl_label = "Bone Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Tools"

    def draw(self, context):
        layout = self.layout

        # UIList anzeigen
        layout.label(text="User-Data Bones (3dsmax User Properties):")
        row = layout.row()
        row.template_list(
            "DYNAMIC_UL_bone_list",  # ID der UIList
            "", 
            context.scene, "bone_items", 
            context.scene, "bone_active_index"
        )

        # Buttons für Hinzufügen und Entfernen
        row = layout.row()
        row.operator("export_model.add_bone_item", text="Add Bone", icon="PLUS")
        row.operator("export_model.remove_bone_item", text="Remove Bone", icon="X")
        row.operator("export_model.reset_bone_items", text="Reset", icon="LOOP_BACK")


class AddBoneItem(Operator):
    bl_idname = "export_model.add_bone_item"
    bl_label = "Add Bone Item"

    def execute(self, context):
        new_bone = context.scene.bone_items.add()
        new_bone.bone_index = "999"
        new_bone.bone_name = "999"
        new_bone.bone_type = 'DECAL'
        context.scene.bone_active_index = len(context.scene.bone_items) - 1
        return {'FINISHED'}


class RemoveBoneItem(Operator):
    bl_idname = "export_model.remove_bone_item"
    bl_label = "Remove Bone Item"

    def execute(self, context):
        index = context.scene.bone_active_index
        if 0 <= index < len(context.scene.bone_items):
            context.scene.bone_items.remove(index)
            context.scene.bone_active_index = min(index, len(context.scene.bone_items) - 1)
        return {'FINISHED'}

class ResetBoneItems(Operator):
    bl_idname = "export_model.reset_bone_items"
    bl_label = "Reset Bones"

    def execute(self, context):
        context.scene.bone_items.clear()
        context.scene.bone_active_index = 0
        return {'FINISHED'}

# ---------------------------------------------- Novator Spheren Generator --------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class CreateSphereOperator(bpy.types.Operator):
    """Erstellt eine Sphere und parentet sie an das ausgewählte Mesh"""
    bl_idname = "object.create_and_parent_sphere"
    bl_label = "Generate"

    # Eigenschaften für den Operator (ohne Typannotationen)
    sphere_x = bpy.props.FloatProperty(name="X", default=0.0)
    sphere_y = bpy.props.FloatProperty(name="Y", default=0.0)
    sphere_z = bpy.props.FloatProperty(name="Z", default=0.0)
    sphere_radius = bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01)

    def execute(self, context):
        obj = context.object

        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Please select a mesh!")
            return {'CANCELLED'}

        # Erstelle die Sphere
        bpy.ops.mesh.primitive_uv_sphere_add(
            size=self.sphere_radius,
            location=(self.sphere_x, self.sphere_y, self.sphere_z)
        )
        sphere = bpy.context.object
        sphere.name = "{}_Sphere".format(obj.name)
        sphere.draw_type = 'WIRE'
        
        # Sphere parenten
        sphere.parent = obj

        # Custom Property hinzufügen
        obj["sphere_name"] = sphere.name
        sphere["linked_mesh"] = obj.name

        self.report({'INFO'}, "Sphere '{}' ceated and parented to '{}'.".format(sphere.name, obj.name))
        return {'FINISHED'}


    def invoke(self, context, event):
        obj = context.object

        if obj and obj.type == 'MESH':
            # Berechne die Weltkoordinaten der Vertices
            mesh_world_coords = [(obj.matrix_world * Vector((v.co.x, v.co.y, v.co.z, 1.0))).to_3d() for v in obj.data.vertices]

            # Berechne den Mittelpunkt des Meshes
            center_x = sum(coord.x for coord in mesh_world_coords) / len(mesh_world_coords)
            center_y = sum(coord.y for coord in mesh_world_coords) / len(mesh_world_coords)
            center_z = sum(coord.z for coord in mesh_world_coords) / len(mesh_world_coords)
            center = Vector((center_x, center_y, center_z))

            # Berechne den Radius der Sphere (maximale Entfernung vom Mittelpunkt zu den Vertices)
            max_distance = max((coord - center).length for coord in mesh_world_coords)

            # Setze die Standardwerte
            self.sphere_x = center.x
            self.sphere_y = center.y
            self.sphere_z = center.z
            self.sphere_radius = max_distance

        return context.window_manager.invoke_props_dialog(self)


class SpherePanel(bpy.types.Panel):
    """Panel im N-Reiter"""
    bl_label = "Sphere Menu"
    bl_idname = "OBJECT_PT_create_sphere"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sphere Tools"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Create Sphere:")

        # Button für die Operator-Dialogbox
        layout.operator(CreateSphereOperator.bl_idname)


# ---------------------------------------------- Novator Particle Menü ------------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class ParticleEffectItem(PropertyGroup):
    """Repräsentiert einen Partikeleffekt-Eintrag"""
    bone_index = StringProperty(name="Bone Index", default="")
    effect_type = EnumProperty(
        name="Effekte",
        items=[
            ('Ubisoft', "Ubisoft", "Vom Import gefundener Particle-Effect wird verwendet."),
            ('smoke10', "smoke10", "Erzeugt eine Rauchwolke am Bone mit passendem Index"),
            ('fire02', "fire02", "Feuer-Effekt"),
            ('woodchip', "woodchip", "Holzsplitter-Effekt"),
            ('PB_Weathermachine_lightning', "PB_Weathermachine_lightning", "Blitz-Effekt der Wettermaschine"),
            ('sulfur_spray', "sulfur_spray", "Schwefel-Spray-Effekt"),
            ('salimTrapIcon', "salimTrapIcon", "Effekt für Salims Falle"),
            ('TMP_resourceGold_Sparkle', "TMP_resourceGold_Sparkle", "Gold-Funkeln-Effekt"),
            ('XD_StoneSparkles', "XD_StoneSparkles", "Stein-Funkeln-Effekt"),
            ('smoke11', "smoke11", "Alternative Rauchwolke"),
            ('XF_Leaves', "XF_Leaves", "Blätterwirbel-Effekt"),
            ('smoke12', "smoke12", "Weitere Rauchvariante"),
            ('fire01', "fire01", "Feuer-Effekt (Variante 1)"),
            ('firewheel', "firewheel", "Feuerrad-Effekt (Yuki-Shurikens")
        ],
        default='smoke10'
    )


# UI-Liste
class PARTICLE_UL_effects(UIList):
    """UIList zur Anzeige der Partikeleffekte"""
    bl_idname = "DYNAMIC_UL_particle_effect_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "bone_index", text="Index")
            layout.prop(item, "effect_type", text="Type")
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'

            
# Panel mit Liste und Plus/Minus
class PARTICLE_PT_tools(Panel):
    """Panel zur Verwaltung der Partikeleffekte"""
    bl_idname = "VIEW3D_PT_particle_manager"
    bl_label = "Particle Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Particle Tools"

    def draw(self, context):
        layout = self.layout

        layout.label(text="Atomic-Effekte (ParticleStandard):")
        row = layout.row()
        row.template_list(
            "DYNAMIC_UL_particle_effect_list",
            "",
            context.scene, "particle_effects",
            context.scene, "particle_effects_index"
        )

        row = layout.row()
        row.operator("export_model.add_particle_effect", text="Add Effect", icon="PLUS")
        row.operator("export_model.remove_particle_effect", text="Remove Effect", icon="X")
        row.operator("export_model.reset_particle_effects", text="Reset", icon="LOOP_BACK")

# Add Operator
class PARTICLE_OT_add_effect(Operator):
    bl_idname = "export_model.add_particle_effect"
    bl_label = "Add Particle Effect"

    def execute(self, context):
        new_effect = context.scene.particle_effects.add()
        new_effect.bone_index = "999"
        new_effect.effect_type = 'smoke10'
        context.scene.particle_effects_index = len(context.scene.particle_effects) - 1
        return {'FINISHED'}


# Remove Operator
class PARTICLE_OT_remove_effect(Operator):
    bl_idname = "export_model.remove_particle_effect"
    bl_label = "Remove Particle Effect"

    def execute(self, context):
        index = context.scene.particle_effects_index
        if 0 <= index < len(context.scene.particle_effects):
            context.scene.particle_effects.remove(index)
            context.scene.particle_effects_index = min(index, len(context.scene.particle_effects) - 1)
        return {'FINISHED'}

class PARTICLE_OT_reset_effects(Operator):
    bl_idname = "export_model.reset_particle_effects"
    bl_label = "Reset Particle Effects"

    def execute(self, context):
        context.scene.particle_effects.clear()
        context.scene.particle_effects_index = 0
        return {'FINISHED'}

# ---------------------------------------------- Novator Geometry Menü ------------------------------------------
# ---------------------------------------------------------------------------------------------------------------

class GeometryMaterialEntry(PropertyGroup):
    name = StringProperty(name="Material Name")
    uv_trans = BoolProperty(name="UVTrans", default=False)
    dual_tex = BoolProperty(name="DualTex", default=False)
    ambient = BoolProperty(name="Ambient", default=True)
    specular = BoolProperty(name="Specular", default=False)
    diffuse = BoolProperty(name="Diffuse", default=True)
    snow_texture = StringProperty(name="Snow Texture", default="No data")
    texture_alpha = StringProperty(name="Texture Alpha", default="")



class GeometryToolItem(PropertyGroup):
    mesh_name = StringProperty(name="Mesh Name", default="No data")
    materials = CollectionProperty(type=GeometryMaterialEntry)
    bin_mesh_data = StringProperty(name="BinMesh Data", default="No data")


class GEOMETRY_UL_tool_entries(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item is None:
            return
        
            
        box_main = layout.box()
        
        # Sichtbarer Header in der Box
        box_main.label(text=" Geometry {} --------------------------------------------------------------------------------------------------------------------------------------------------".format(index + 1))

        # Mesh-Name
        box_main.prop(item, "mesh_name", text="Mesh")

        # Materialien mit eigener Box & Checkboxen
        for idx, mat in enumerate(item.materials):
            mat_box = box_main.box()
            mat_box.prop(mat, "name", text="Material {}:".format(idx + 1))

            row = mat_box.row(align=True)
            row.prop(mat, "uv_trans")
            row.prop(mat, "dual_tex")

            row = mat_box.row(align=True)
            row.prop(mat, "ambient")
            row.prop(mat, "specular")
            row.prop(mat, "diffuse")

            row = mat_box.row()
            row.prop(mat, "snow_texture")
            row.prop(mat, "texture_alpha")

        # Plus / Minus Buttons für Materials
        row = box_main.row(align=True)
        add_op = row.operator("geometry_tools.add_material", icon="PLUS", text="")
        add_op.index = index
        rem_op = row.operator("geometry_tools.remove_material", icon="X", text="")
        rem_op.index = index

        # BinMesh Property
        row = box_main.row()
        row.prop(item, "bin_mesh_data", text="BinMesh")
        








class GEOMETRY_PT_tools(Panel):
    bl_idname = "VIEW3D_PT_geometry_tools"
    bl_label = "Geometry Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Geometry Tools'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Geometry Data:")
        scene = context.scene

        layout.template_list("GEOMETRY_UL_tool_entries", "", scene, "geometry_tool_items", scene, "geometry_tool_index")

        row = layout.row()
        row.operator("geometry_tools.add_entry", icon="PLUS")
        row.operator("geometry_tools.remove_entry", icon="X")
        row.operator("geometry_tools.reset_entries", icon="LOOP_BACK")



class GEOMETRY_OT_add_entry(Operator):
    bl_idname = "geometry_tools.add_entry"
    bl_label = "Add Geometry Entry"
    def execute(self, context):
        context.scene.geometry_tool_items.add()
        context.scene.geometry_tool_index = len(context.scene.geometry_tool_items) - 1
        return {'FINISHED'}

class GEOMETRY_OT_remove_entry(Operator):
    bl_idname = "geometry_tools.remove_entry"
    bl_label = "Remove Geometry Entry"
    def execute(self, context):
        index = context.scene.geometry_tool_index
        if 0 <= index < len(context.scene.geometry_tool_items):
            context.scene.geometry_tool_items.remove(index)
            context.scene.geometry_tool_index = min(index, len(context.scene.geometry_tool_items) - 1)
        return {'FINISHED'}

class GEOMETRY_OT_reset_entries(Operator):
    bl_idname = "geometry_tools.reset_entries"
    bl_label = "Reset Geometry Entries"
    def execute(self, context):
        context.scene.geometry_tool_items.clear()
        context.scene.geometry_tool_index = 0
        return {'FINISHED'}
    
class GEOMETRY_OT_add_material(Operator):
    bl_idname = "geometry_tools.add_material"
    bl_label = "Add Material"
    index = IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        geo.materials.add()
        return {'FINISHED'}


class GEOMETRY_OT_remove_material(Operator):
    bl_idname = "geometry_tools.remove_material"
    bl_label = "Remove Material"
    index = IntProperty()

    def execute(self, context):
        geo = context.scene.geometry_tool_items[self.index]
        if geo.materials:
            geo.materials.remove(len(geo.materials) - 1)
        return {'FINISHED'}




# ---------------------------------------------- Register/ Unregister Classes -----------------------------------
# ---------------------------------------------------------------------------------------------------------------

def menu_func_import_ModelDFF(self, context):
    self.layout.operator(ModelImporterDFF.bl_idname, ModelImporterDFF.bl_label)
def menu_func_import_ModelJSON(self, context):
    self.layout.operator(ModelImporterJSON.bl_idname, ModelImporterJSON.bl_label)
def menu_func_export_ModelDFF(self, context):
    self.layout.operator(ModelExporterDFF.bl_idname, ModelExporterDFF.bl_label)
def menu_func_export_ModelJSON(self, context):
    self.layout.operator(ModelExporterJSON.bl_idname, ModelExporterJSON.bl_label)

def safe_register_class(cls):
    """Registers a class only if it's not already registered."""
    if cls.__name__ in dir(bpy.types):
        print("[DEBUG] Class {} is already registered. Skipping.".format(cls.__name__))
    else:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
        print("[DEBUG] Registered class: {}".format(cls.__name__))

def safe_unregister_class(cls):
    """Unregisters a class only if it is currently registered."""
    try:
        if cls.__name__ in dir(bpy.types):
            bpy.utils.unregister_class(cls)
            print("[DEBUG] Unregistered class: {}".format(cls.__name__))
        else:
            print("[DEBUG] Class {} is not registered. Skipping.".format(cls.__name__))
    except RuntimeError as e:
        print("[DEBUG] Failed to unregister {}: {}".format(cls.__name__, e))

def register_menu_functions():
    """Safely append menu functions to prevent duplicates."""
    try:
        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelDFF)
    except ValueError:
        pass
    bpy.types.INFO_MT_file_import.append(menu_func_import_ModelDFF)
    print("[DEBUG] Appended menu_func_import_ModelDFF to INFO_MT_file_import")

    try:
        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelJSON)
    except ValueError:
        pass
    bpy.types.INFO_MT_file_import.append(menu_func_import_ModelJSON)
    print("[DEBUG] Appended menu_func_import_ModelJSON to INFO_MT_file_import")

    try:
        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelDFF)
    except ValueError:
        pass
    bpy.types.INFO_MT_file_export.append(menu_func_export_ModelDFF)
    print("[DEBUG] Appended menu_func_export_ModelDFF to INFO_MT_file_export")

    try:
        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelJSON)
    except ValueError:
        pass
    bpy.types.INFO_MT_file_export.append(menu_func_export_ModelJSON)
    print("[DEBUG] Appended menu_func_export_ModelJSON to INFO_MT_file_export")

def unregister_menu_functions():
    """Safely remove menu functions."""
    try:
        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelDFF)
        print("[DEBUG] Removed menu_func_import_ModelDFF from INFO_MT_file_import")
    except ValueError:
        print("[DEBUG] menu_func_import_ModelDFF was not registered in INFO_MT_file_import")

    try:
        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelJSON)
        print("[DEBUG] Removed menu_func_import_ModelJSON from INFO_MT_file_import")
    except ValueError:
        print("[DEBUG] menu_func_import_ModelJSON was not registered in INFO_MT_file_import")

    try:
        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelDFF)
        print("[DEBUG] Removed menu_func_export_ModelDFF from INFO_MT_file_export")
    except ValueError:
        print("[DEBUG] menu_func_export_ModelDFF was not registered in INFO_MT_file_export")

    try:
        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelJSON)
        print("[DEBUG] Removed menu_func_export_ModelJSON from INFO_MT_file_export")
    except ValueError:
        print("[DEBUG] menu_func_export_ModelJSON was not registered in INFO_MT_file_export")

def register():
    print("[DEBUG] Starting register process")
    if (2, 80, 0) <= bpy.app.version:
        from bpy.utils import register_class
        classes = ( 
            DynamicBoneItem,
            DynamicBoneListUIList,
            BoneManagerPanel,
            ModelExporterDFF,
            AddBoneItem,
            RemoveBoneItem,
            ResetBoneItems,
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect,
            PARTICLE_OT_reset_effects,
            GeometryMaterialEntry,
            GeometryToolItem,
            GEOMETRY_UL_tool_entries,
            GEOMETRY_PT_tools,
            GEOMETRY_OT_add_entry,
            GEOMETRY_OT_remove_entry,
            GEOMETRY_OT_reset_entries,
            GEOMETRY_OT_add_material,
            GEOMETRY_OT_remove_material
        )
        for cls in classes:
            print("[DEBUG] Registering class: {}".format(cls.__name__))
            safe_register_class(cls)

        register_menu_functions()
    
    else:
        print("[DEBUG] Registering for Blender < 2.80")
        bpy.utils.register_module(__name__)
        
        # Register custom classes
        custom_classes = (
            DynamicBoneItem,
            DynamicBoneListUIList,
            BoneManagerPanel,
            ModelExporterDFF,
            AddBoneItem,
            RemoveBoneItem,
            ResetBoneItems,
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect,
            PARTICLE_OT_reset_effects,
            GeometryMaterialEntry,
            GeometryToolItem,
            GEOMETRY_UL_tool_entries,
            GEOMETRY_PT_tools,
            GEOMETRY_OT_add_entry,
            GEOMETRY_OT_remove_entry,
            GEOMETRY_OT_reset_entries,
            GEOMETRY_OT_add_material,
            GEOMETRY_OT_remove_material
        )
        for cls in custom_classes:
            print("[DEBUG] Registering class: {}".format(cls.__name__))
            safe_register_class(cls)
        
        # Register Scene property
        if not hasattr(bpy.types.Scene, "bone_items"):
            bpy.types.Scene.bone_items = CollectionProperty(type=DynamicBoneItem)
            print("[DEBUG] Registered Scene.bone_items")
        
        if not hasattr(bpy.types.Scene, "bone_active_index"):
            bpy.types.Scene.bone_active_index = IntProperty(default=0)
            print("[DEBUG] Registered Scene.bone_active_index")
        
        if not hasattr(bpy.types.Scene, "particle_effects"):
            bpy.types.Scene.particle_effects = CollectionProperty(type=ParticleEffectItem)
            print("[DEBUG] Registered Scene.particle_effects")

        if not hasattr(bpy.types.Scene, "particle_effects_index"):
            bpy.types.Scene.particle_effects_index = IntProperty(default=0)
            print("[DEBUG] Registered Scene.particle_effects_index")
            
        if not hasattr(bpy.types.Scene, "geometry_tool_items"):
            bpy.types.Scene.geometry_tool_items = CollectionProperty(type=GeometryToolItem)
            print("[DEBUG] Registered Scene.geometry_tool_items")

        if not hasattr(bpy.types.Scene, "geometry_tool_index"):
            bpy.types.Scene.geometry_tool_index = IntProperty(default=0)
            print("[DEBUG] Registered Scene.geometry_tool_index")
            
            
            
        
        register_menu_functions()


def unregister():
    print("[DEBUG] Starting unregister process")
    if (2, 80, 0) <= bpy.app.version:
        classes = ( 
            DynamicBoneItem,
            DynamicBoneListUIList,
            BoneManagerPanel,
            ModelExporterDFF,
            AddBoneItem,
            RemoveBoneItem,
            ResetBoneItems,
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect,
            PARTICLE_OT_reset_effects,
            GeometryMaterialEntry,
            GeometryToolItem,
            GEOMETRY_UL_tool_entries,
            GEOMETRY_PT_tools,
            GEOMETRY_OT_add_entry,
            GEOMETRY_OT_remove_entry,
            GEOMETRY_OT_reset_entries,
            GEOMETRY_OT_add_material,
            GEOMETRY_OT_remove_material
        )
        from bpy.utils import unregister_class
        for cls in reversed(classes):
            safe_unregister_class(cls)

        unregister_menu_functions()
    
    else:
        print("[DEBUG] Unregistering for Blender < 2.80")
        bpy.utils.unregister_module(__name__)
    
        if hasattr(bpy.types.Scene, "bone_items"):
            del bpy.types.Scene.bone_items
            print("[DEBUG] Unregistered Scene.bone_items")
        
        if hasattr(bpy.types.Scene, "bone_active_index"):
            del bpy.types.Scene.bone_active_index
            print("[DEBUG] Unregistered Scene.bone_active_index")
        
        if hasattr(bpy.types.Scene, "particle_effects"):
            del bpy.types.Scene.particle_effects
            print("[DEBUG] Unregistered Scene.particle_effects")


        if hasattr(bpy.types.Scene, "particle_effect_index"):
            del bpy.types.Scene.particle_effect_index
            print("[DEBUG] Unregistered Scene.particle_effect_index")
            
        if hasattr(bpy.types.Scene, "geometry_tool_items"):
            del bpy.types.Scene.geometry_tool_items
            print("[DEBUG] Unregistered Scene.geometry_tool_items")
            
        if hasattr(bpy.types.Scene, "geometry_tool_index"):
            del bpy.types.Scene.geometry_tool_index
            print("[DEBUG] Unregistered Scene.geometry_tool_index")
            
        custom_classes = (
            DynamicBoneItem,
            DynamicBoneListUIList,
            BoneManagerPanel,
            ModelExporterDFF,
            AddBoneItem,
            RemoveBoneItem,
            ResetBoneItems,
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect,
            PARTICLE_OT_reset_effects,
            GeometryMaterialEntry,
            GeometryToolItem,
            GEOMETRY_UL_tool_entries,
            GEOMETRY_PT_tools,
            GEOMETRY_OT_add_entry,
            GEOMETRY_OT_remove_entry,
            GEOMETRY_OT_reset_entries,
            GEOMETRY_OT_add_material,
            GEOMETRY_OT_remove_material
        )
        for cls in custom_classes:
            safe_unregister_class(cls)
        
        unregister_menu_functions()


# Novator Clipping Extension

def set_clipping_for_all_screens(clip_start, clip_end):
    """Setze Clipping-Werte für alle Bildschirme und relevante Bereiche"""
    for screen in bpy.data.screens:  # Iteriere durch alle Bildschirme (Layouts)
        for area in screen.areas:  # Iteriere durch alle Bereiche in jedem Bildschirm
            for space in area.spaces:  # Iteriere durch die Spaces in jedem Bereich
                if hasattr(space, 'clip_start') and hasattr(space, 'clip_end'):
                    space.clip_start = clip_start
                    space.clip_end = clip_end


def get_converter_exe_location():
    # offset = __file__.rfind("\\")
    # exe_loc = __file__[:offset] + "\\RW_inline.exe"
   # exe_loc = "C:\\Users\\Simon\\AppData\\Roaming\\Blender Foundation\\Blender\\2.79\\scripts\\addons" + "\\RW_inline.exe"
   # exe_loc = "G:\\Test\\DFF-ANM-Converter\\RW\\RW\\Debug\\RW.exe"
    exe_loc = "C:\\Program Files (x86)\\Ubisoft\\Blue Byte\\DIE SIEDLER - Das Erbe der Könige - Gold Edition\\GitRepo\\s5_BlenderPlugin\\BlenderPlugin\\RW_inline_mcb.exe"
    return exe_loc


def convert_to_js_external(binary_data):
    print("convert_to_js_external-Func")
    p = subprocess.Popen([get_converter_exe_location(),"--import"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    outs, errs = p.communicate(input=binary_data)
    
    #print("STDOUT:", outs)
    #print("STDERR:", errs)
    
    return outs.decode('utf-8')
    
def read_model(path):
    print("read_model-Func")
    print(path)

    js = None

    if path.endswith(".dff"):
        with open(path, 'rb') as file:
            data = convert_to_js_external(file.read())
            js = json.loads(data)
    else:
        fh = open(path, "r")
        js = json.load(fh)
        fh.close()

    read_json_rigid(js, False)

def write_model(path,bone_type_data, particle_data, geometry_data):
    print("write_model-Func")
    js = get_json_rigid(bone_type_data, particle_data, geometry_data)
    
    if path.endswith(".json"):
        with open(path, "w") as outfile:
            json.dump(js, outfile, indent=4)
    else:
        p = subprocess.Popen([get_converter_exe_location(),"--export"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        js_str = json.dumps(js)
        bytes_data = js_str.encode('utf-8')

        outs, errs = p.communicate(input=bytes_data)

        if errs:
            print("[Exporter STDERR]", errs.decode("utf-8"))

        
        #DEBUG: Eingabe in Datei schreiben
        with open("C:\\Program Files (x86)\\Ubisoft\\Blue Byte\\DIE SIEDLER - Das Erbe der Könige - Gold Edition\\GitRepo\\s5_BlenderPlugin\\TestEnv\\debug_export.json", "w", encoding="utf-8") as debugfile:
            debugfile.write(js_str)
            
        #Export
        try:
            with open(path, "wb") as outfile:
                outfile.write(outs)
        except BrokenPipeError as e:
            print("[ERROR] BrokenPipe beim Schreiben in Datei {path}: {}".format(e))

if __name__ == "__main__":
    #Novator Test Stuff
    os.system("cls")
    print("[DEBUG] Reloading script and re-registering plugin")
    unregister()
    register()
    keep_script = "Novator12-DFF-Plugin-mcb.py"

    # Entfernt alle Text-Daten außer dem angegebenen Skript
    for text in bpy.data.texts:
        if text.name != keep_script:
            bpy.data.texts.remove(text)
         
            
#  --------------------------------------------------------------------- LUTs -----------------------------------------------------------------

    # particle_effects_data.py

    PARTICLE_EFFECT_LUT = {
        "smoke10": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                        "ParticlePropsId": 64672,
                        "EmitterPropsId": 49328,
                        "EmitterFlags": 127,
                        "MaxParticlesPerBatch": 75,
                        "EmitterStandard": {
                            "Seed": 0,
                            "MaxParticles": 75,
                            "Force": {
                                "x": 50.71419,
                                "y": -5.2453665E-06,
                                "z": -108.756935
                            },
                            "EmitterPosition": {"x": 0, "y": 0, "z": 0},
                            "EmitterSize": {"x": 0.5, "y": 0.5, "z": 0.5},
                            "TimeBetweenEmissions": 0.5,
                            "TimeBetweenEmissionsRandom": 0.33333334,
                            "NumParticlesPerEmission": 5,
                            "NumParticlesPerEmissionRandom": 1,
                            "InitialVelocity": 200,
                            "InitialVelocityRandom": 100,
                            "ParticleLife": 2,
                            "ParticleLifeRandom": 0.33333334,
                            "InitialDirection": {"x": 0, "y": 0, "z": 32},
                            "InitialDirectionRandom": {"x": 2, "y": 2, "z": 0.02},
                            "ParticleSize": {"x": 1, "y": 1, "z": -2.3509886e-38},
                            "Color": {"red": 128, "green": 255, "blue": 255, "alpha": 255},
                            "TextureCoordinates": [
                                {"x": 0, "y": 0},
                                {"x": 1, "y": 1},
                                {"x": 1.33e-42, "y": 1.309e-42},
                                {"x": 1.345e-42, "y": 1.28e-42}
                            ],
                            "ParticleTexture": {
                                "texture": "smoke10",
                                "textureAlpha": "",
                                "FilterAddressing": 4358,
                                "UnusedInt1": 0,
                                "extension": {}
                            },
                            "ParticleRotation": 0
                        },
                        "Color": {
                            "StartColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                            "StartColorRandom": {"red": 0, "green": 0, "blue": 0, "alpha": 0},
                            "EndColor": {"red": 69, "green": 69, "blue": 69, "alpha": 25.5},
                            "EndColorRandom": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                        },
                        "TextureCoordinates": {
                            "StartUV0": {"x": 0, "y": 0},
                            "StartUV0Random": {"x": 0, "y": 0},
                            "EndUV0": {"x": 0.90000004, "y": 0},
                            "EndUV0Random": {"x": 0, "y": 0},
                            "StartUV1": {"x": 0.1, "y": 1},
                            "StartUV1Random": {"x": 0, "y": 0},
                            "EndUV1": {"x": 1, "y": 1},
                            "EndUV1Random": {"x": 0, "y": 0}
                        },
                        "Matrix": None,
                        "ParticleSize": {
                            "StartSize": {"x": 50, "y": 50},
                            "StartSizeRandom": {"x": 0, "y": 0},
                            "EndSize": {"x": 300, "y": 600},
                            "EndSizeRandom": {"x": 200, "y": 400}
                        },
                        "Rotate": {
                            "StartRotate": 0,
                            "StartRotateRandom": 5,
                            "EndRotate": 0,
                            "EndRotateRandom": 45
                        },
                        "Tank": {
                            "UpdateFlags": -1,
                            "EmitterFlags": -1,
                            "SourceBlend": 2,
                            "DestinationBlend": 2,
                            "VertexAlphaBlending": True
                        },
                        "AdvPointList": None,
                        "AdvCircle": None,
                        "AdvSphere": None,
                        "AdvEmittingEmitter": None,
                        "AdvMultiColor": {
                            "List": [
                                {
                                    "Time": 0.1,
                                    "TimeBias": 0,
                                    "MidColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                                    "MidColorBias": {"red": 2, "green": 2, "blue": 2, "alpha": 0}
                                },
                                {
                                    "Time": 0.25,
                                    "TimeBias": 0,
                                    "MidColor": {"red": 38, "green": 38, "blue": 38, "alpha": 127.5},
                                    "MidColorBias": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                                },
                                {
                                    "Time": 0.5,
                                    "TimeBias": 0,
                                    "MidColor": {"red": 55.000004, "green": 55.000004, "blue": 55.000004, "alpha": 51},
                                    "MidColorBias": {"red": 0, "green": 0, "blue": 0, "alpha": 0}
                                }
                            ]
                        },
                        "AdvMultiTexCoords": None,
                        "AdvMultiSize": {
                            "List": [
                                {
                                    "Time": 0.2,
                                    "TimeBias": 0,
                                    "MidSize": {"x": 150, "y": 200},
                                    "MidSizeBias": {"x": 100, "y": 140}
                                },
                                {
                                    "Time": 0.5,
                                    "TimeBias": 0,
                                    "MidSize": {"x": 200, "y": 300},
                                    "MidSizeBias": {"x": 100, "y": 400}
                                },
                                {
                                    "Time": 0.75,
                                    "TimeBias": 0,
                                    "MidSize": {"x": 200, "y": 500},
                                    "MidSizeBias": {"x": 200, "y": 400}
                                }
                            ]
                        },
                        "AdvMultiTexCoordsStep": {
                            "List": [
                                {
                                    "Time": 0.1,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.1, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.2, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.2,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.2, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.3, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.3,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.3, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.4, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.4,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.4, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.5, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.5,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.5, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.6, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.6,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.6, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.7, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.7,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.7, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.8, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                },
                                {
                                    "Time": 0.8,
                                    "TimeBias": 0,
                                    "MidUV0": {"u": 0.8, "v": 0},
                                    "MidUV0Bias": {"u": 0, "v": 0},
                                    "MidUV1": {"u": 0.90000004, "v": 1},
                                    "MidUV1Bias": {"u": 0, "v": 0}
                                }
                            ]
                        }
                    }
                ]
            }
        },
        "fire02": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 59536,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 48,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 48,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 0.8333334,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 80,
                            "y": 130
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 9.642894e-39,
                                "y": 9.183704e-39
                            },
                            {
                                "x": 1.0102052e-38,
                                "y": 1.44e-43
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "fire02",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 2,
                            "green": 2,
                            "blue": 2,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.91999996,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.04,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 0.96,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": -20,
                        "StartRotateRandom": 0,
                        "EndRotate": -20,
                        "EndRotateRandom": 0
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": {
                        "UseDirection": False,
                        "Random": False,
                        "PointList": [
                            {
                                "x": -1.6972677e-05,
                                "y": -2.2382583e-05,
                                "z": -2.8980601e-05
                            },
                            {
                                "x": 70.45405,
                                "y": 559.3705,
                                "z": 1319.3811
                            },
                            {
                                "x": 40.193428,
                                "y": 1108.8148,
                                "z": 1283.1187
                            },
                            {
                                "x": 11.097094,
                                "y": 753.883,
                                "z": 1338.8953
                            },
                            {
                                "x": 2.5581362,
                                "y": 908.9255,
                                "z": 1328.6627
                            },
                            {
                                "x": -863.7427,
                                "y": 836.85425,
                                "z": 1902.105
                            },
                            {
                                "x": -845.54034,
                                "y": 506.3539,
                                "z": 1923.9176
                            },
                            {
                                "x": -928.0423,
                                "y": 956.68036,
                                "z": 1906.472
                            },
                            {
                                "x": -1317.328,
                                "y": 935.824,
                                "z": 1915.3145
                            },
                            {
                                "x": -881.1258,
                                "y": 810.08435,
                                "z": 2644.3967
                            },
                            {
                                "x": -872.7234,
                                "y": 657.5209,
                                "z": 2654.4656
                            },
                            {
                                "x": -1040.4478,
                                "y": 949.52386,
                                "z": 2638.0938
                            },
                            {
                                "x": -1196.6864,
                                "y": 941.15326,
                                "z": 2641.6426
                            },
                            {
                                "x": -1104.2192,
                                "y": 1735.4486,
                                "z": 2018.3694
                            },
                            {
                                "x": -787.219,
                                "y": 1752.4321,
                                "z": 2011.1688
                            },
                            {
                                "x": -786.7644,
                                "y": 1783.8152,
                                "z": 1418.2747
                            }
                        ],
                        "DirectionList": []
                    },
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.041666668,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.04,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.08,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.083333336,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.08,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.12,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.125,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.12,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.16,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.16666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.16,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.19999999,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.20833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.19999999,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.24,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.24,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.28,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.29166666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.28,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.32,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.33333334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.32,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.35999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.375,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.35999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.39999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.41666666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.39999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.44,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.45833334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.44,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.48,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.48,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.52,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5416667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.52,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.56,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.56,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.59999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.625,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.59999996,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.64,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.64,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.68,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7083333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.68,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.71999997,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.75,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.71999997,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.76,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7916667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.76,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.79999995,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8333333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.79999995,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.84,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.875,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.84,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.88,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.9166667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.88,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.91999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
                ]
            }
        },
        "woodchip": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 10304,
                    "EmitterPropsId": 19552,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 600,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 600,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": -300
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 119.2955,
                            "y": 119.2955,
                            "z": 119.2955
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 5,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 100,
                        "InitialVelocityRandom": 74.550385,
                        "ParticleLife": 0.6666667,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 10,
                            "y": 7
                        },
                        "ParticleSize_SeriMisstake": 2147483647,
                        "Color": {
                            "red": 127,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.8e-44,
                                "y": 1.5e-44
                            },
                            {
                                "x": 6.6e-44,
                                "y": 2.17e-43
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "woodchip",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": None,
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 90,
                        "EndRotate": 90,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 3.7277482,
                        "RadiusGap": 0.5,
                        "UseSphereEmission": True
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
        "PB_Weathermachine_lightning": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                        {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 60560,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 41,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 41,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 32.68158,
                            "y": 32.68158,
                            "z": 60.227192
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 13,
                        "NumParticlesPerEmissionRandom": 23,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 20,
                        "ParticleLife": 0.06666667,
                        "ParticleLifeRandom": 0.13333334,
                        "InitialDirection": {
                            "x": 2.27,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "ParticleSize": {
                            "x": 200,
                            "y": 60
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 4.65e-43,
                                "y": 6.383398e-10
                            },
                            {
                                "x": 6.82e-43,
                                "y": 4.59184e-40
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "PB_Weathermachine_lightning",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 204
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 84,
                            "green": 59.000004,
                            "blue": 211.00002,
                            "alpha": 127.5
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0,
                            "y": 0.75
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 1,
                            "y": 0.25
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 1,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 30,
                        "StartRotateRandom": 30,
                        "EndRotate": 30,
                        "EndRotateRandom": 30
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": {
                        "Radius": 76.25696,
                        "RadiusGap": 0.5,
                        "Height": 60.227192,
                        "UseCircleEmission": False,
                        "DirRotation": 0
                    },
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0,
                                    "v": 0.25
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 1,
                                    "v": 0.5
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0,
                                    "v": 0.5
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 1,
                                    "v": 0.75
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
                ]
            }
        },
        "sulfur_spray": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                {
                    "ParticlePropsId": 30816,
                    "EmitterPropsId": 31856,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 35,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 35,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 72.3574,
                            "y": 36.1787,
                            "z": 2.1707227
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 90,
                        "InitialVelocityRandom": 30,
                        "ParticleLife": 0.93333334,
                        "ParticleLifeRandom": 0.2,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 75,
                            "y": 75
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 0,
                                "y": 0
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "sulfur_spray",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 0,
                        "EndRotate": 0,
                        "EndRotateRandom": 50.000004
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.3,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.6,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
        "salimTrapIcon": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                {
                    "ParticlePropsId": 26704,
                    "EmitterPropsId": 52336,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 1,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 1,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 26.69075,
                            "y": 26.69075,
                            "z": 26.69075
                        },
                        "TimeBetweenEmissions": 2,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 1,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 169.29698,
                            "y": 169.29698
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.01e-43,
                                "y": 8.7432e-32
                            },
                            {
                                "x": 1.11e-43,
                                "y": 1.836717e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "salimTrapIcon",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": None,
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 0,
                        "RadiusGap": 0,
                        "UseSphereEmission": False
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.8,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
        "TMP_resourceGold_Sparkle": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                {
                    "ParticlePropsId": 57472,
                    "EmitterPropsId": 58512,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 5,
                    "EmitterStandard": {
                        "Seed": 1,
                        "MaxParticles": 5,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 150,
                            "y": 150,
                            "z": 5
                        },
                        "TimeBetweenEmissions": 0.06666667,
                        "TimeBetweenEmissionsRandom": 0.033333335,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 2,
                        "InitialVelocity": 1,
                        "InitialVelocityRandom": 20,
                        "ParticleLife": 0.33333334,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 1.9420925e+31,
                                "y": 1.211889e+25
                            },
                            {
                                "x": 7.7100935e+28,
                                "y": 1.8037311e+28
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "TMP_resourceGold_Sparkle",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 255,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 255,
                            "green": 127.5,
                            "blue": 0,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 1.36765,
                            "y": 1.36765
                        },
                        "StartSizeRandom": {
                            "x": 0,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 1.36765,
                            "y": 1.36765
                        },
                        "EndSizeRandom": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 360,
                        "EndRotate": 0,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.9,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 255,
                                    "blue": 0,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 13.6765,
                                    "y": 13.6765
                                },
                                "MidSizeBias": {
                                    "x": 13.6765,
                                    "y": 13.6765
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },

        "XD_StoneSparkles": {
                    "ParticleStandard": {
                        "Flags": 3,
                        "Emitters": [
                                {
                            "ParticlePropsId": 57472,
                            "EmitterPropsId": 58512,
                            "EmitterFlags": 127,
                            "MaxParticlesPerBatch": 5,
                            "EmitterStandard": {
                                "Seed": 1,
                                "MaxParticles": 5,
                                "Force": {
                                    "x": 0,
                                    "y": 0,
                                    "z": 0
                                },
                                "EmitterPosition": {
                                    "x": 0,
                                    "y": 0,
                                    "z": 0
                                },
                                "EmitterSize": {
                                    "x": 111.39,
                                    "y": 136.5,
                                    "z": 12.736
                                },
                                "TimeBetweenEmissions": 0,
                                "TimeBetweenEmissionsRandom": 0,
                                "NumParticlesPerEmission": 1,
                                "NumParticlesPerEmissionRandom": 0,
                                "InitialVelocity": 1,
                                "InitialVelocityRandom": 4,
                                "ParticleLife": 0.46666667,
                                "ParticleLifeRandom": 0.033333335,
                                "InitialDirection": {
                                    "x": 0,
                                    "y": 0,
                                    "z": -1
                                },
                                "InitialDirectionRandom": {
                                    "x": 0,
                                    "y": 0,
                                    "z": 0
                                },
                                "ParticleSize": {
                                    "x": 1,
                                    "y": 1
                                },
                                "ParticleSize_SeriMisstake": -2130706433,
                                "Color": {
                                    "red": 128,
                                    "green": 255,
                                    "blue": 255,
                                    "alpha": 255
                                },
                                "TextureCoordinates": [
                                    {
                                        "x": 0,
                                        "y": 0
                                    },
                                    {
                                        "x": 1,
                                        "y": 1
                                    },
                                    {
                                        "x": 2e-44,
                                        "y": 2e-44
                                    },
                                    {
                                        "x": 2e-44,
                                        "y": 2.1e-44
                                    }
                                ],
                                "ParticleTexture": {
                                    "texture": "XD_StoneSparkles",
                                    "textureAlpha": "",
                                    "FilterAddressing": 4358,
                                    "UnusedInt1": 0,
                                    "extension": {}
                                },
                                "ParticleRotation": 0
                            },
                            "Color": {
                                "StartColor": {
                                    "red": 255,
                                    "green": 221.00002,
                                    "blue": 191,
                                    "alpha": 255
                                },
                                "StartColorRandom": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                },
                                "EndColor": {
                                    "red": 216.00002,
                                    "green": 142,
                                    "blue": 75,
                                    "alpha": 0
                                },
                                "EndColorRandom": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            },
                            "TextureCoordinates": None,
                            "Matrix": None,
                            "ParticleSize": {
                                "StartSize": {
                                    "x": 20,
                                    "y": 20
                                },
                                "StartSizeRandom": {
                                    "x": 0,
                                    "y": 0
                                },
                                "EndSize": {
                                    "x": 1,
                                    "y": 1
                                },
                                "EndSizeRandom": {
                                    "x": 0,
                                    "y": 0
                                }
                            },
                            "Rotate": {
                                "StartRotate": 0,
                                "StartRotateRandom": 360,
                                "EndRotate": 0,
                                "EndRotateRandom": 180
                            },
                            "Tank": {
                                "UpdateFlags": -1,
                                "EmitterFlags": -1,
                                "SourceBlend": 2,
                                "DestinationBlend": 2,
                                "VertexAlphaBlending": True
                            },
                            "AdvPointList": None,
                            "AdvCircle": None,
                            "AdvSphere": None,
                            "AdvEmittingEmitter": None,
                            "AdvMultiColor": {
                                "List": [
                                    {
                                        "Time": 0.9,
                                        "TimeBias": 0,
                                        "MidColor": {
                                            "red": 216.00002,
                                            "green": 142,
                                            "blue": 75,
                                            "alpha": 51
                                        },
                                        "MidColorBias": {
                                            "red": 0,
                                            "green": 0,
                                            "blue": 0,
                                            "alpha": 0
                                        }
                                    }
                                ]
                            },
                            "AdvMultiTexCoords": None,
                            "AdvMultiSize": {
                                "List": [
                                    {
                                        "Time": 0.25,
                                        "TimeBias": 0,
                                        "MidSize": {
                                            "x": 20,
                                            "y": 20
                                        },
                                        "MidSizeBias": {
                                            "x": 10,
                                            "y": 10
                                        }
                                    }
                                ]
                            },
                            "AdvMultiTexCoordsStep": None
                        }
                        ]
                    }
                },

        "smoke11": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 57472,
                    "EmitterPropsId": 58512,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 147,
                    "EmitterStandard": {
                        "Seed": 0,
                        "MaxParticles": 147,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.33333334,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 120.38401,
                        "InitialVelocityRandom": 56.1,
                        "ParticleLife": 7.5333333,
                        "ParticleLifeRandom": 0.23333333,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 32
                        },
                        "InitialDirectionRandom": {
                            "x": 2,
                            "y": 2,
                            "z": 0.02
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 8.6324516e-17,
                                "y": 5.51153e-40
                            },
                            {
                                "x": 7.34687e-40,
                                "y": 2.8967556e-35
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "smoke11",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 221.00002,
                            "green": 136,
                            "blue": 102.00001,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 120,
                            "y": 120
                        },
                        "StartSizeRandom": {
                            "x": 0,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 198.31009,
                            "y": 705.9
                        },
                        "EndSizeRandom": {
                            "x": 22,
                            "y": 21
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 0,
                        "EndRotateRandom": 18
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.31,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 223.00002,
                                    "green": 208.00002,
                                    "blue": 188,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 2,
                                    "green": 2,
                                    "blue": 2,
                                    "alpha": 0
                                }
                            },
                            {
                                "Time": 0.39,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 119.00001,
                                    "green": 119.00001,
                                    "blue": 119.00001,
                                    "alpha": 255
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 133.2473,
                                    "y": 328.02
                                },
                                "MidSizeBias": {
                                    "x": 74,
                                    "y": 25
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
        "XF_Leaves": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 12368,
                    "EmitterPropsId": 13408,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 10,
                    "EmitterStandard": {
                        "Seed": 3,
                        "MaxParticles": 10,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 150,
                            "y": 150,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 1,
                        "TimeBetweenEmissionsRandom": 0.93333334,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 60,
                        "InitialVelocityRandom": 40,
                        "ParticleLife": 8,
                        "ParticleLifeRandom": 1.5,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -1
                        },
                        "InitialDirectionRandom": {
                            "x": 0.1,
                            "y": 0.1,
                            "z": 0.5
                        },
                        "ParticleSize": {
                            "x": 13,
                            "y": 13
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 0.5,
                                "y": 0.5
                            },
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1e-45,
                                "y": 8.5721096e-36
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "XF_Leaves",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 128,
                            "green": 128,
                            "blue": 128,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 128,
                            "green": 128,
                            "blue": 128,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 360,
                        "EndRotateRandom": 180
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
        "smoke12": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 64672,
                    "EmitterPropsId": 49328,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 30,
                    "EmitterStandard": {
                        "Seed": 30,
                        "MaxParticles": 30,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 100,
                            "y": 100,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.2,
                        "TimeBetweenEmissionsRandom": 0.1,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 1.582859,
                        "InitialVelocityRandom": 2.7197943,
                        "ParticleLife": 2,
                        "ParticleLifeRandom": 0.33333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": -396.79013
                        },
                        "InitialDirectionRandom": {
                            "x": 2,
                            "y": 2,
                            "z": 0.02
                        },
                        "ParticleSize": {
                            "x": 1,
                            "y": 1
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 8.908151e-39,
                                "y": 7.347002e-39
                            },
                            {
                                "x": 1.0285723e-38,
                                "y": 6.704133e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "smoke12",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 148,
                            "green": 114.00001,
                            "blue": 77,
                            "alpha": 0
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 157,
                            "green": 150,
                            "blue": 124.00001,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.90000004,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.1,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 1,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": {
                        "StartSize": {
                            "x": 300,
                            "y": 250
                        },
                        "StartSizeRandom": {
                            "x": 30.841,
                            "y": 0
                        },
                        "EndSize": {
                            "x": 400,
                            "y": 268
                        },
                        "EndSizeRandom": {
                            "x": 50,
                            "y": 50
                        }
                    },
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 5,
                        "EndRotate": 0,
                        "EndRotateRandom": 45
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": {
                        "List": [
                            {
                                "Time": 0.65999997,
                                "TimeBias": 0,
                                "MidColor": {
                                    "red": 255,
                                    "green": 242.00002,
                                    "blue": 191,
                                    "alpha": 127.5
                                },
                                "MidColorBias": {
                                    "red": 0,
                                    "green": 0,
                                    "blue": 0,
                                    "alpha": 0
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": {
                        "List": [
                            {
                                "Time": 0.41000023,
                                "TimeBias": 0,
                                "MidSize": {
                                    "x": 350,
                                    "y": 350
                                },
                                "MidSizeBias": {
                                    "x": 40,
                                    "y": 40
                                }
                            }
                        ]
                    },
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.1,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.1,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.2,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.2,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.2,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.3,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.3,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.3,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.4,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.4,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.4,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.5,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.5,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.6,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.6,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.7,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.7,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.8,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.8,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.90000004,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
                ]
            }
        },
        "fire01": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 19568,
                    "EmitterPropsId": 20608,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 10,
                    "EmitterStandard": {
                        "Seed": 0,
                        "MaxParticles": 10,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 0.5,
                            "y": 0.5,
                            "z": 0.5
                        },
                        "TimeBetweenEmissions": 0.033333335,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 5.45,
                        "InitialVelocityRandom": 0,
                        "ParticleLife": 0.8333334,
                        "ParticleLifeRandom": 0,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 1
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 200,
                            "y": 110
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 6.244926e-39,
                                "y": 8.724488e-39
                            },
                            {
                                "x": 4.68371e-39,
                                "y": 7.62248e-39
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "fire01",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 250.00002,
                            "green": 250.00002,
                            "blue": 250.00002,
                            "alpha": 255
                        },
                        "EndColorRandom": {
                            "red": 2,
                            "green": 2,
                            "blue": 2,
                            "alpha": 76.5
                        }
                    },
                    "TextureCoordinates": {
                        "StartUV0": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV0": {
                            "x": 0.91999996,
                            "y": 0
                        },
                        "EndUV0Random": {
                            "x": 0,
                            "y": 0
                        },
                        "StartUV1": {
                            "x": 0.04,
                            "y": 1
                        },
                        "StartUV1Random": {
                            "x": 0,
                            "y": 0
                        },
                        "EndUV1": {
                            "x": 0.96,
                            "y": 1
                        },
                        "EndUV1Random": {
                            "x": 0,
                            "y": 0
                        }
                    },
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": -60,
                        "StartRotateRandom": 20,
                        "EndRotate": -60,
                        "EndRotateRandom": 20
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": None,
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": {
                        "List": [
                            {
                                "Time": 0.041666668,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.04,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.08,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.083333336,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.08,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.12,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.125,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.12,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.16,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.16666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.16,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.19999999,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.20833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.19999999,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.24,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.25,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.24,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.28,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.29166666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.28,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.32,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.33333334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.32,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.35999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.375,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.35999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.39999998,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.41666666,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.39999998,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.44,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.45833334,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.44,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.48,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.48,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.52,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5416667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.52,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.56,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.5833333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.56,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.59999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.625,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.59999996,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.64,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.6666667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.64,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.68,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7083333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.68,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.71999997,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.75,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.71999997,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.76,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.7916667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.76,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.79999995,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.8333333,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.79999995,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.84,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.875,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.84,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.88,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            },
                            {
                                "Time": 0.9166667,
                                "TimeBias": 0,
                                "MidUV0": {
                                    "u": 0.88,
                                    "v": 0
                                },
                                "MidUV0Bias": {
                                    "u": 0,
                                    "v": 0
                                },
                                "MidUV1": {
                                    "u": 0.91999996,
                                    "v": 1
                                },
                                "MidUV1Bias": {
                                    "u": 0,
                                    "v": 0
                                }
                            }
                        ]
                    }
                }
                ]
            }
        },
        "firewheel": {
            "ParticleStandard": {
                "Flags": 3,
                "Emitters": [
                    {
                    "ParticlePropsId": 12368,
                    "EmitterPropsId": 21616,
                    "EmitterFlags": 127,
                    "MaxParticlesPerBatch": 200,
                    "EmitterStandard": {
                        "Seed": 2,
                        "MaxParticles": 200,
                        "Force": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterPosition": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "EmitterSize": {
                            "x": 4.378521,
                            "y": 4.378521,
                            "z": 1.6235573
                        },
                        "TimeBetweenEmissions": 0,
                        "TimeBetweenEmissionsRandom": 0,
                        "NumParticlesPerEmission": 1,
                        "NumParticlesPerEmissionRandom": 0,
                        "InitialVelocity": 0.67441154,
                        "InitialVelocityRandom": 1.3488231,
                        "ParticleLife": 1.3333334,
                        "ParticleLifeRandom": 1.3333334,
                        "InitialDirection": {
                            "x": 0,
                            "y": 0,
                            "z": 0.1348823
                        },
                        "InitialDirectionRandom": {
                            "x": 0,
                            "y": 0,
                            "z": 0
                        },
                        "ParticleSize": {
                            "x": 63.71852,
                            "y": 63.71853
                        },
                        "ParticleSize_SeriMisstake": -2130706433,
                        "Color": {
                            "red": 128,
                            "green": 255,
                            "blue": 255,
                            "alpha": 255
                        },
                        "TextureCoordinates": [
                            {
                                "x": 0,
                                "y": 0
                            },
                            {
                                "x": 1,
                                "y": 1
                            },
                            {
                                "x": 6.0264154e-30,
                                "y": 1.285705e-39
                            },
                            {
                                "x": 7.35047e-40,
                                "y": 6.5549e-34
                            }
                        ],
                        "ParticleTexture": {
                            "texture": "firewheel",
                            "textureAlpha": "",
                            "FilterAddressing": 4358,
                            "UnusedInt1": 0,
                            "extension": {}
                        },
                        "ParticleRotation": 0
                    },
                    "Color": {
                        "StartColor": {
                            "red": 251.00002,
                            "green": 252.00002,
                            "blue": 198.00002,
                            "alpha": 76.5
                        },
                        "StartColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        },
                        "EndColor": {
                            "red": 251.00002,
                            "green": 252.00002,
                            "blue": 198.00002,
                            "alpha": 0
                        },
                        "EndColorRandom": {
                            "red": 0,
                            "green": 0,
                            "blue": 0,
                            "alpha": 0
                        }
                    },
                    "TextureCoordinates": None,
                    "Matrix": None,
                    "ParticleSize": None,
                    "Rotate": {
                        "StartRotate": 0,
                        "StartRotateRandom": 0,
                        "EndRotate": 3600.0002,
                        "EndRotateRandom": 300
                    },
                    "Tank": {
                        "UpdateFlags": -1,
                        "EmitterFlags": -1,
                        "SourceBlend": 2,
                        "DestinationBlend": 2,
                        "VertexAlphaBlending": True
                    },
                    "AdvPointList": None,
                    "AdvCircle": None,
                    "AdvSphere": {
                        "Radius": 10.946303,
                        "RadiusGap": 0,
                        "UseSphereEmission": False
                    },
                    "AdvEmittingEmitter": None,
                    "AdvMultiColor": None,
                    "AdvMultiTexCoords": None,
                    "AdvMultiSize": None,
                    "AdvMultiTexCoordsStep": None
                }
                ]
            }
        },
    }
