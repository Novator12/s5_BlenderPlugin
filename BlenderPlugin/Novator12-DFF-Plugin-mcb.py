
import bpy
import os
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
from bpy.props import CollectionProperty, IntProperty,StringProperty, EnumProperty

#Spherengenerator
from mathutils import Vector


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

    for frameContainer in js_frames:
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
                        new_bone.bone_name = str(nodeID)
                        new_bone.bone_type = bone_type
                        bpy.context.scene.bone_active_index = len(bpy.context.scene.bone_items) - 1

                        print("[DEBUG] AutoBoneManager: Hinzugefügt -> ID={}, Typ={}".format(nodeID, bone_type))

                
        
        

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
    
    empty_geometry = False 
    
    if len(js_geometry["morphTargets"][0])<=1: #Check auf leere Geometry, wie bei bspw. Particle Effects
        empty_geometry = True     
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='OBJECT')
        
    num_morph_targets = len(js_geometry.get("morphTargets", []))
    if num_morph_targets != 1:
        print("Skipping geometry – expected 1 morphTarget, got", num_morph_targets)
        return
    

    #Bauernhof wird hier abgefangen!
    #if js_geometry["numTris"] == None:
        #print("skipping geometry because of no tris")
        #return;
        
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

    mesh_o = bpy.data.objects.new("mesh_", mesh)

    vgs = mesh_o.vertex_groups

    vgs.new(name=boneName)#"frame_"+str(frameIndex).zfill(stringLengthOfFrames))
        
    arm_mod = mesh_o.modifiers.new(type='ARMATURE', name="skeleton")
    arm_mod.object = arm_o
    
    
    link_object_and_set_active(mesh_o)
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bpy.ops.object.mode_set()
    if not empty_geometry:
        tex_name = js_geometry["materials"][0]["textures"][0]["texture"]
        material = set_material(tex_name)
    else:
        tex_name = None
    
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

        # Zusätzliche Eigenschaften der Sphere setzen
        sphere_obj.hide_render = True  # Unsichtbar im Render
        sphere_obj.draw_type = 'WIRE'  # Drahtmodell für Übersicht

        # Sphere dem Mesh zuordnen (Parenting)
        sphere_obj.parent = mesh_o
        
    return vgs
    # MaterialDataPLG (muss vorher über rwinline erst importiert werden)
    

def read_json_rigid(js, use_connect):
    print("read_json_rigid-Func")
    js_clump = js["clump"]
    arm_o, boneNames, frames, hierarchy = make_armature_from_frames(js_clump["frames"], use_connect)    
    vertexGroups = []
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
        vgs = read_rigid_geometry(geometry, js_clump, arm_o, frameIndex, frameRestMatrix, boneNames[frameIndex], use_connect)
        vertexGroups.append(vgs)
        
    # ----------------- Particle Effect Auto-Detection -------------------
    if hasattr(bpy.context.scene, "particle_effects"):
        used_frame_indices = set()  # Verarbeitetet Bone Indices merken
        
        for atomic in js_clump["atomics"]:
            frame_index = atomic.get("frameIndex")
            if frame_index in used_frame_indices:
                continue  # Schon verarbeitet, skip
            
            extension = atomic.get("extension", {})
            particle_std = extension.get("ParticleStandard", None)
            
            if particle_std and "Emitters" in particle_std:
                for emitter in particle_std["Emitters"]:
                    particle_texture = emitter.get("EmitterStandard", {}).get("ParticleTexture", {})
                    texture_name = particle_texture.get("texture", "").lower()

                    if "smoke10" in texture_name:
                        effect_type = "SMOKE"
                        new_effect = bpy.context.scene.particle_effects.add()
                        new_effect.bone_index = str(frame_index)
                        new_effect.effect_type = effect_type
                        bpy.context.scene.particle_effects_index = len(bpy.context.scene.particle_effects) - 1

                        print("[DEBUG] Particle Effect erkannt: BoneIndex={}, Type={}".format(new_effect.bone_index, effect_type))
                        used_frame_indices.add(frame_index)  # Vermerken
                        break  # Nur ein Eintrag pro atomic






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

def generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas, bone_type_data):
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
            extension['hanimPLG'] = {}
            extension['hanimPLG']['flags'] = 0
            extension['hanimPLG']['keyFrameSize'] = 0
            extension['hanimPLG']['nodeID'] = nodeIds[frameIndex] #frameIndex + 5
            extension['hanimPLG']['numNodes'] = 0
        
        if frameIndex == 1:

            extension['hanimPLG']['numNodes'] = len(parents)
            print("Bone -{} Parents: {}".format(nodeIds[frameIndex],parents))
            extension['hanimPLG']['parents'] = parents
            extension['hanimPLG']['nodes'] = []
            extension['hanimPLG']['flags'] = 0 #28672
            extension['hanimPLG']['keyFrameSize'] = 36

            matrixflags = generateMatrixFlags(parents)

            for j, nodeID in enumerate(exportOrderAuto):
                boneIndex = nodeIdToFrameIndex[nodeID]
                node = OrderedDict()
                node['flags'] = matrixflags[j]
                node['nodeID'] = nodeID
                node['nodeIndex'] = j
                
                extension['hanimPLG']['nodes'].append(node)
                
        print("Bone-{} Extension: {}".format(nodeIds[frameIndex],extension))
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
        
def new_mesh_obj_to_json(mesh_obj, invertedRestMatrix):
    print("new_mesh_obj_to_json-Func")
    verts_local = [v.co for v in mesh_obj.data.vertices.values()]

    dimensions = mesh_obj.dimensions


    data = OrderedDict()
    data['numMorphTargets'] = 1
    data['numVertices'] = len(verts_local)
        
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
    js_morphTarget = {}
    js_morphTarget['vertices'] = js_vertices;
    js_morphTarget['has_vertices'] = 1
    js_morphTarget['has_normals'] = 1
    js_morphTarget['normals'] = js_normals;
    
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
    
    #Novator12
    data['textureCoordinates'] = []
    for uv_layer in mesh_obj.data.uv_layers:
        js_textureCoordinates = [None] * data['numVertices']
        for face in mesh_obj.data.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_coords = uv_layer.data[loop_idx].uv
                uv = OrderedDict()
                uv['u'] = uv_coords.x
                uv['v'] = 1 - uv_coords.y  # Y-Koordinate invertieren
                js_textureCoordinates[vert_idx] = uv
        # Füge UV-Koordinaten dieses Layers hinzu
        data['textureCoordinates'].append(js_textureCoordinates)
    
    
    #data['format'] = 65591 # TODO, depends on texture stuff...
    if len(mesh_obj.data.uv_layers) > 1:
        data['format'] = 131251  # Mehr als ein UV-Layer
    else:
        data['format'] = 65591  # Nur ein UV-Layer
    # 131251 bei mehr als einem UV Layer Novator
    
    
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
    
    
    data['materials'] = []
    
    ## TODO hardcoded texture stuff :(
    if mesh_obj.data.materials:
        for mat in mesh_obj.data.materials:
            material = OrderedDict()
            material["color"] = OrderedDict()
            material['color']['a'] = 255
            material['color']['r'] = 255
            material['color']['g'] = 255
            material['color']['b'] = 255
            material['textures'] = []
            texture = OrderedDict()
            texture["texture"] = re.sub(r'\.\d+$', '', mat.name)  # Vereinheitlichung der texturen Novator12
            texture["textureAlpha"] = ""
            
            material['textures'].append(texture)
            
            data['materials'].append(material)
            
    return data

def get_bone_by_name_(bones, name):
    for bone in bones:
        if bone.name == name:
            return bone
        
def append_atomic(frameIndex,geometryIndex):
    atomic = OrderedDict()
    atomic["frameIndex"] = frameIndex
    atomic["geometryIndex"] = geometryIndex

def get_json_rigid(bone_type_data):
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
    clump["frames"] = generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas,bone_type_data)
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

        clump["geometries"].append(new_mesh_obj_to_json(mesh, frameRestMatrix.inverted()))
        # print("Geometrie-Data {}: {}".format(mesh, clump["geometries"])) # --Debug
        # add geometry to atomics
        atomic = append_atomic(frameIndex,geometryIndex)

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
        # Daten exportieren
        bone_type_data = [
            {"name": bone.bone_name, "type": bone.bone_type}
            for bone in context.scene.bone_items
        ]
        if bone_type_data == []:
            bone_type_data = None;
        
        #print("[DEBUG] Exporting with bone data: {}".format(bone_type_data))
        write_model(self.filepath, bone_type_data)  # Deine Exportfunktion
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
            {"name": bone.bone_name, "type": bone.bone_type}
            for bone in context.scene.bone_items
        ]
        if bone_type_data == []:
            bone_type_data = None;
        
        write_model(self.filepath, bone_type_data)
        return {'FINISHED'}
    
#----------------------------------------------------------------------------------------------------------------------------------------------------------
#----------------------------------------------------------------Novator Bone Structur-Handler-------------------------------------------------------------

class DynamicBoneItem(PropertyGroup):
    """Repräsentiert einen Bone-Eintrag"""
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
        layout.label(text="Bones:")
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


class AddBoneItem(Operator):
    bl_idname = "export_model.add_bone_item"
    bl_label = "Add Bone Item"

    def execute(self, context):
        new_bone = context.scene.bone_items.add()
        new_bone.bone_name = "New Bone"
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
        name="Effekt",
        items=[
            ('SMOKE', "SMOKE", "Erzeugt eine Rauchwolke am Bone mit passendem Index")
        ],
        default='SMOKE'
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

        layout.label(text="Effekte:")
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


# Add Operator
class PARTICLE_OT_add_effect(Operator):
    bl_idname = "export_model.add_particle_effect"
    bl_label = "Add Particle Effect"

    def execute(self, context):
        new_effect = context.scene.particle_effects.add()
        new_effect.bone_index = 0
        new_effect.effect_type = 'SMOKE'
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
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect
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
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect
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
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect
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
        
        custom_classes = (
            DynamicBoneItem,
            DynamicBoneListUIList,
            BoneManagerPanel,
            ModelExporterDFF,
            AddBoneItem,
            RemoveBoneItem,
            CreateSphereOperator,
            SpherePanel,
            ParticleEffectItem,
            PARTICLE_UL_effects,
            PARTICLE_PT_tools,
            PARTICLE_OT_add_effect,
            PARTICLE_OT_remove_effect
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

def write_model(path,bone_type_data):
    print("write_model-Func")
    js = get_json_rigid(bone_type_data)
    
    if path.endswith(".json"):
        with open(path, "w") as outfile:
            json.dump(js, outfile, indent=4)
    else:
        p = subprocess.Popen([get_converter_exe_location(),"--export"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        js_str = json.dumps(js)
        bytes = js_str.encode('utf-8')
        x = p.stdin.write(bytes)
        
        #print(x, len(bytes))
        p.stdin.flush()
        p.stdin.close()

        outs, errs = p.communicate()
        
        #DEBUG: Eingabe in Datei schreiben
        with open("C:\\Program Files (x86)\\Ubisoft\\Blue Byte\\DIE SIEDLER - Das Erbe der Könige - Gold Edition\\GitRepo\\s5_BlenderPlugin\\TestEnv\\debug_export.json", "w", encoding="utf-8") as debugfile:
            debugfile.write(js_str)
            
        #Export
        with open(path, "wb") as outfile:
            outfile.write(outs)

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
    

    #write_model("C:\\Users\\olive\Desktop\\Blender Dev Test\\Blender_Output\\Test_Res.json",[{'name': '415', 'type': 'BUILDING'}, {'name': '416', 'type': 'DECAL'}])
    #write_model("C:\\Users\\olive\Desktop\\Blender Dev Test\\Blender_Output\\Test_Res.dff",[{'name': '415', 'type': 'BUILDING'}, {'name': '416', 'type': 'DECAL'}])
    
    