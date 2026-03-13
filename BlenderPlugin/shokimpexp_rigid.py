import bpy

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
from collections import OrderedDict



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

def _3x3_from_matrix(q):
    mat_rot = mu.Matrix.Rotation(math.radians(45.0), 4, 'X');
    
    mat_rot[0][0] = float(q[0]["x"])
    mat_rot[0][1] = float(q[0]["y"])
    mat_rot[0][2] = float(q[0]["z"])
    
    mat_rot[1][0] = float(q[1]["x"])
    mat_rot[1][1] = float(q[1]["y"])
    mat_rot[1][2] = float(q[1]["z"])
    
    mat_rot[2][0] = float(q[2]["x"])
    mat_rot[2][1] = float(q[2]["y"])
    mat_rot[2][2] = float(q[2]["z"])
    
    
    return mat_rot
   
def mat3x3_to_js_rotation_matrix(mat_rot):
    js = []
        
    idx1 = 0
    idx2 = 1
    idx3 = 2
    
    js_vec = OrderedDict()
    js_vec["x"] = mat_rot[idx1][0]
    js_vec["y"] = mat_rot[idx1][1]
    js_vec["z"] = mat_rot[idx1][2]
    
    js.append(js_vec);
    
    js_vec = OrderedDict()
    js_vec["x"] = mat_rot[idx2][0]
    js_vec["y"] = mat_rot[idx2][1]
    js_vec["z"] = mat_rot[idx2][2]
    
    js.append(js_vec);
    
    js_vec = OrderedDict()
    js_vec["x"] = mat_rot[idx3][0]
    js_vec["y"] = mat_rot[idx3][1]
    js_vec["z"] = mat_rot[idx3][2]
    
    js.append(js_vec);
        
    return js

 
    
    

def skin_obj_to_json(skin_obj):
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bones = []
    for bone in skin_obj.data.edit_bones:
        bones.append(bone)
    bones.sort(key=lambda bone: bone.name)
    
    
    data = OrderedDict()
    data["skin"] = []
    for bone in bones:
        print(bone.name)
        
        joint = bone;
        
        roll = joint.roll;
        tail = joint.tail - joint.head
        #tail = tail / 10
        
        position = joint.head
        
        mat3x3 = vec_roll_to_mat3(tail, roll)
        mat3x3 = mul_matrix(mat3x3, mu.Quaternion((0.707, 0, 0, -0.707)).to_matrix().inverted())
        
        mat4x4 = mat3x3.to_4x4()
        mat4x4.translation = joint.head;
       # mat4x4.invert()
        
        position = mat4x4.inverted().translation
        
        bonesMat = mat3x3_to_js_rotation_matrix(mat4x4.to_3x3())
        
        pos = OrderedDict()
        pos["x"] = position.x;
        pos["y"] = position.y;
        pos["z"] = position.z;
        
        bonesMat.append(pos)
        
        data["skin"].append(bonesMat)
        
    bpy.ops.object.mode_set()
        
    return data;
        
    
    """
    quat = _3x3_from_matrix(bone).to_quaternion().to_matrix().to_4x4()
            quat.invert()
            pos = read_vector(bone[3])
            
            mat4x4 = quat
            mat4x4.translation = pos
            mat4x4.invert()
            
            name = "skin_"
            if index < 10:
                name += "0"
            name += str(index)
            
            joint = ebs.new(name)
            joint = ebs.new("skin_" + str(index))
            
            mat3x3 = mat4x4.to_3x3()
            mat3x3 = mat3x3 * mu.Quaternion((0.707, 0, 0, -0.707)).to_matrix()
            
            tail, roll = mat3_to_vec_roll(mat3x3)
            boneLength = 10
            joint.head = mat4x4.to_translation()
            joint.tail = tail*boneLength + joint.head
            joint.roll = roll

            print("joint:", joint.name)
            print(joint.matrix)
            
            parent = hanim_plg_parents[index]
            if (parent != -1):
                joint.parent = ebs[parent]
                
    """
    
    
    """
    verts_local = [v.co for v in skin_obj.data.vertices.values()]

    data = {}
    data['vertices'] = []
    for i, vert in enumerate(verts_local):
        #print(vert)
        
        vertex = {}
        vertex["x"] = vert[0]
        vertex["y"] = vert[1]
        vertex["z"] = vert[2]
        
        data['vertices'].append(vertex)

    for tri in skin_obj.data.polygons:
        print(tri.vertices[0], tri.vertices[1], tri.vertices[2])
    """

def mesh_obj_to_json(mesh_obj):
    verts_local = [v.co for v in mesh_obj.data.vertices.values()]
    
    data = OrderedDict()
    data['numMorphTargets'] = 1
    data['numVertices'] = len(verts_local)
        
    js_vertices = []
    js_normals = []
    
    for vert in verts_local:
        vertex = OrderedDict()
        vertex['x'] = vert[0]
        vertex['y'] = vert[1]
        vertex['z'] = vert[2]
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
    
    # TODO: Sphere? Probably used for clipping
    js_morphTarget['sphere'] = OrderedDict()
    js_morphTarget['sphere']['x'] = 0;
    js_morphTarget['sphere']['y'] = 0;
    js_morphTarget['sphere']['z'] = 0;
    js_morphTarget['sphere']['radius'] = 0
    
    data['morphTargets'].append(js_morphTarget)
    
    
    js_textureCoordinates = [None] * data['numVertices']
    
    for face in mesh_obj.data.polygons:
        for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
            uv_coords = mesh_obj.data.uv_layers.active.data[loop_idx].uv
            
            uv = OrderedDict()
            uv['u'] = uv_coords.x
            uv['v'] = 1 - uv_coords.y
            
            js_textureCoordinates[vert_idx] = uv
    
    data['textureCoordinates'] = []
    data['textureCoordinates'].append(js_textureCoordinates)
    
    data['format'] = 65591 # TODO, depends on texture stuff...
    
    
    
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
            texture["texture"] = mat.name
            texture["textureAlpha"] = ""
            
            material['textures'].append(texture)
            
            data['materials'].append(material)
    
    return data


def skin_obj_to_skin_plg_bones_json(skin_obj):
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bones = []
    for bone in skin_obj.data.edit_bones:
        bones.append(bone)
    bones.sort(key=lambda bone: bone.name)
    
    
    data = OrderedDict()
    data = []
    for bone in bones:        
        joint = bone;
        
        roll = joint.roll;
        tail = joint.tail - joint.head        
        position = joint.head
        
        mat3x3 = vec_roll_to_mat3(tail, roll)
        mat3x3 = mul_matrix(mat3x3, mu.Quaternion((0.707, 0, 0, -0.707)).to_matrix().inverted())
        
        mat4x4 = mat3x3.to_4x4()
        mat4x4.translation = joint.head;
        
        position = mat4x4.inverted().translation
        
        bonesMat = mat3x3_to_js_rotation_matrix(mat4x4.to_3x3())
        
        pos = OrderedDict()
        pos["x"] = position.x;
        pos["y"] = position.y;
        pos["z"] = position.z;
        
        bonesMat.append(pos)
        
        data.append(bonesMat)
        
    bpy.ops.object.mode_set()
        
    return data;

def skin_obj_to_parents(skin_obj):
    bpy.ops.object.mode_set(mode='EDIT')
    
    bones = []
    for bone in skin_obj.data.edit_bones:
        bones.append(bone)
    bones.sort(key=lambda bone: bone.name)
    
    parents = []
    
    for bone in bones:
        if bone.parent == None:
            parents.append(-1)
        else:
            for idx, bone2 in enumerate(bones):
                if bone2 == bone.parent:
                    parents.append(idx)
    
    bpy.ops.object.mode_set()
    
    return parents;

def generateMatrixFlags(parents):
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
    
def genDefaultFrame():
	
    frame = OrderedDict()
    frame['position'] = OrderedDict()
    frame['position']['x'] = 0
    frame['position']['y'] = 0
    frame['position']['z'] = 0
    
    #frame['matrixCreationFlags'] = 0
    
    frame['parentFrameIndex'] = -1
    
    frame['rotationMatrix'] = []
    
    r0 = OrderedDict()
    r0['x'] = 1
    r0['y'] = 0
    r0['z'] = 0
    
    r1 = OrderedDict()
    r1['x'] = 0
    r1['y'] = 1
    r1['z'] = 0
    
    r2 = OrderedDict()
    r2['x'] = 0
    r2['y'] = 0
    r2['z'] = 1
    
    frame['rotationMatrix'].append(r0)
    frame['rotationMatrix'].append(r1)
    frame['rotationMatrix'].append(r2)
    
    return frame;
    
def generateFrameListFromParents(parents):
    
    framelist = []
    
    matrixflags = generateMatrixFlags(parents)
    
    frame = OrderedDict()
    frame['extension'] = None
    frame['frame'] = genDefaultFrame();
    
    framelist.append(frame)
    
    
    
    for i, parent in enumerate(parents):
        
        frame = genDefaultFrame()
        frame['parentFrameIndex'] = i
        
        extension = OrderedDict()
        extension['hanimPLG'] = {}
        extension['hanimPLG']['flags'] = 0
        extension['hanimPLG']['keyFrameSize'] = 0
        extension['hanimPLG']['nodeID'] = i + 5
        extension['hanimPLG']['numNodes'] = 0
        
        if i == 0:
            extension['hanimPLG']['numNodes'] = len(parents)
            extension['hanimPLG']['parents'] = parents
            extension['hanimPLG']['nodes'] = []
            extension['hanimPLG']['flags'] = 28672
            extension['hanimPLG']['keyFrameSize'] = 36

            for j, parent2 in enumerate(parents):
                node = OrderedDict()
                node['flags'] = matrixflags[j]
                node['nodeID'] = j + 5
                node['nodeIndex'] = j
                
                extension['hanimPLG']['nodes'].append(node)
        
        f = OrderedDict()
        f['frame'] = frame;
        f['extension'] = extension
        
        framelist.append(f)
    
    return framelist
    
def skin_obj_to_sorted_bone_array(skin_obj):
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bones = []
    for bone in skin_obj.data.edit_bones:
        bones.append(bone)
    bones.sort(key=lambda bone: bone.name)
    
    bpy.ops.object.mode_set()
    
    return bones
    
def find_index_by_bone_name(bones, bone_name):
    for idx, bone in enumerate(bones):
        print(bone.name, bone_name)
        if bone.name == bone_name:
            return idx;
    return None;
    
def write_skinned_model(path):
    
    selection = bpy.context.selected_objects
    
    skin_obj = None;
    mesh_obj = None;
    
    for obj in selection:
        if obj.type == "ARMATURE":
            skin_obj = obj
        else:
            mesh_obj = obj
            
    js = mesh_obj_to_json(mesh_obj)
    ## Everything but extension filled by now
    
    js['extension'] = OrderedDict()
    js['extension']['skinPLG'] = OrderedDict()
    js['extension']['skinPLG']['affectedBones'] = []
    js['extension']['skinPLG']['usedBones'] = 0
    js['extension']['skinPLG']['bones'] = skin_obj_to_skin_plg_bones_json(skin_obj)
    js['extension']['skinPLG']['numBones'] = len(js['extension']['skinPLG']['bones'])
    js['extension']['skinPLG']['maxVertexWeight'] = 4
    
    js['extension']['skinPLG']['weights'] = [None] * len(mesh_obj.data.vertices)
    js['extension']['skinPLG']['bonePairs'] = [None] *  len(mesh_obj.data.vertices)
    
    max = 0
    
    numBones = len(js['extension']['skinPLG']['bones'])
    
    bones = skin_obj_to_sorted_bone_array(skin_obj)

    
    for i, v in enumerate(mesh_obj.data.vertices):
        js['extension']['skinPLG']['weights'][i] = []
        js['extension']['skinPLG']['bonePairs'][i] = []
        
        
        for j, g in enumerate(v.groups):            
            if len(mesh_obj.vertex_groups) > g.group:
                print(type(mesh_obj.vertex_groups[g.group].name))
                bone_idx = find_index_by_bone_name(bones, mesh_obj.vertex_groups[g.group].name)
                if bone_idx:
                    js['extension']['skinPLG']['weights'][i].append(g.weight)
                    js['extension']['skinPLG']['bonePairs'][i].append(bone_idx)
            
            
        while len(js['extension']['skinPLG']['weights'][i]) < 4:
            js['extension']['skinPLG']['weights'][i].append(0)
            js['extension']['skinPLG']['bonePairs'][i].append(0)
            
        # Normalize to 1
        totalWeight = 0;
        for j in range(0, 4):
            if js['extension']['skinPLG']['weights'][i][j] != 0:
                totalWeight += js['extension']['skinPLG']['weights'][i][j];
        if totalWeight > 0:
            for j in range(0, 4):
                if js['extension']['skinPLG']['weights'][i][j] != 0:
                    js['extension']['skinPLG']['weights'][i][j] = js['extension']['skinPLG']['weights'][i][j] / totalWeight;
                    
        for j in range(0, 4):
            if js['extension']['skinPLG']['weights'][i][j] != 0:
                if max < j + 1:
                    max = j +1;
            
    js['extension']['skinPLG']['maxVertexWeight'] = max

    ## Parents:
    js['parents'] = skin_obj_to_parents(skin_obj)
    
    real_js = {}
    real_js['clump'] = OrderedDict()
    real_js['clump']['frames'] = generateFrameListFromParents(skin_obj_to_parents(skin_obj))
    real_js['clump']['geometries'] = []
    real_js['clump']['geometries'].append(js)
    real_js['clump']['atomics'] = []
    
    atomic = OrderedDict()
    atomic['frameIndex'] = 0
    atomic['geometryIndex'] = 0
    
    real_js['clump']['atomics'].append(atomic)
    
    js = real_js
    
    with open(path, "w") as outfile:
       #json.dump(data, outfile, indent=4)
       json.dump(js, outfile, indent=4)

def write_skinned_model_wrapper(context, filepath, obj):
    
    sce = bpy.context.scene
    ob = bpy.context.object
    
    write_skinned_model(filepath);

    return {'FINISHED'}


  
    
def read_vector(js):
    return mu.Vector((js["x"],js["y"],js["z"]))

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

def read_skinned_geometry(js_geometry, js_clump, use_connect):
    # Assume Skin is always present    
    hanim_plg_parents = js_clump["frames"][1]["extension"]["hanimPLG"]["parents"]
    #for frame in js_clump["frames"]:
    #    if 'extension' in frame and frame['extension'] != None:
    #        if 'hanimPLG' in frame["extension"]:
    #            if 'numNodes' in frame["extension"]["hanimPLG"] and frame["extension"]["hanimPLG"]["numNodes"] > 0:
    #                hanim_plg_parents = frame["extension"]["hanimPLG"]["parents"];
    
    arm = bpy.data.armatures.new("Armature_Skin")
    arm_o = bpy.data.objects.new("Armature_Skin", arm)
    link_object_and_set_active(arm_o)
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = arm.edit_bones
    
    for index, bone in enumerate(js_geometry["extension"]["skinPLG"]["bones"]):
        quat = _3x3_from_matrix(bone).to_quaternion().to_matrix().to_4x4()
        quat.invert()
        pos = read_vector(bone[3])
        
        mat4x4 = quat
        mat4x4.translation = pos
        mat4x4.invert()
        
        name = "skin_"
        if index < 10:
            name += "0"
        name += str(index)
        
        joint = ebs.new(name)
        
        mat3x3 = mat4x4.to_3x3()
        mat3x3 = mul_matrix(mat3x3, mu.Quaternion((0.707, 0, 0, -0.707)).to_matrix())
        
        tail, roll = mat3_to_vec_roll(mat3x3)
        boneLength = 10
        joint.head = mat4x4.to_translation()
        joint.tail = tail*boneLength + joint.head
        joint.roll = roll

        #print("joint:", joint.name)
        #print(joint.matrix)
        
        parent = hanim_plg_parents[index]
        if (parent != -1):
            joint.parent = ebs[parent]
            if use_connect:
                joint.use_connect = True
            
    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='OBJECT')
    
    
    if js_geometry["numMorphTargets"] != 1:
        print("skipping geometry, because of num morph targets != 1")
        return;
    
    if js_geometry["numTris"] == 0:
        print("skipping geometry because of no tris")
        return;
        
    bm = bmesh.new()
    wd = bm.verts.layers.deform.verify()
    uvs = bm.loops.layers.uv.verify()
    
    mesh = bpy.data.meshes.new("mesh")
    
    uv_coordinates = []
    for textureCoords in js_geometry["textureCoordinates"][0]: # assume one set of texture coordinates...
        uv_coordinates.append((textureCoords["u"], textureCoords["v"]))
    
    vertex_index = 0;
    for json_vertex in js_geometry["morphTargets"][0]["vertices"]:
        x = json_vertex["x"]
        y = json_vertex["y"]
        z = json_vertex["z"]
        
        xyz = mu.Vector((x,y,z))
        
        

        vertex = bm.verts.new(xyz)
        
        
        
        normal = mu.Vector((
            js_geometry["morphTargets"][0]["normals"][vertex_index]["x"],
            js_geometry["morphTargets"][0]["normals"][vertex_index]["y"],
            js_geometry["morphTargets"][0]["normals"][vertex_index]["z"]
        ))
        
        ## TODO does this work?
        vertex.normal = normal
        
        bm.verts.index_update()
        
        bone_index = 0
        for weight in js_geometry["extension"]["skinPLG"]["weights"][vertex_index]:
            bone = js_geometry["extension"]["skinPLG"]["bonePairs"][vertex_index][bone_index]
            bone_index = bone_index + 1;
            vertex[wd][bone] = weight
                
        vertex_index = vertex_index + 1;
        
    bm.verts.ensure_lookup_table()

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
                ln = [l for l in face.loops if l.vert == vn][0]
                u0, v0 = [uv_coordinates[vn.index][0], uv_coordinates[vn.index][1]]
                ln[uvs].uv = (u0, 1.0 - v0)
            
            
        except ValueError:
            print("caught")
    


    bm.to_mesh(mesh)
    bm.free()

    mesh_o = bpy.data.objects.new("mesh_", mesh)
    
        
    vgs = mesh_o.vertex_groups
    
    for bone in range(0, index + 1):
        if (bone < 10):
            vgs.new(name="skin_0"+str(bone))
        else:
            vgs.new(name="skin_"+str(bone))
        
    arm_mod = mesh_o.modifiers.new(type='ARMATURE', name="skeleton")
    arm_mod.object = arm_o
    
    
    link_object_and_set_active(mesh_o)
    
    bpy.ops.object.mode_set(mode='EDIT')
    
    bpy.ops.object.mode_set()
    
    tex_name = js_geometry["materials"][0]["textures"][0]["texture"]
    set_material(tex_name)
    set_texture(tex_name)
    
    
    arm.show_names = True
    
    if (2, 80, 0) <= bpy.app.version:
        arm_o.show_in_front = True;
    else:
        arm_o.show_x_ray = True
    
    
def read_json_skinned(js_clump, use_connect):
    # ignore atomics and assume geometry == frame == 0
    
    # read frames
    #armature_frames = read_frames(js_clump["frames"])
    # read geometries
    ## only support one geo
    read_skinned_geometry(js_clump["geometries"][0], js_clump, use_connect)
    
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

        if extension != None and "userDataPLG" in extension:
            userDataPLG = extension["userDataPLG"]
            userData = userDataPLG

            #for property in userDataPLG:
                #print(property)
                #for value in userDataPLG[property]:
                #    print(value)
        
        userDatas.append(userData)
                
        
        

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

    bpy.ops.object.mode_set()
    bpy.ops.object.mode_set(mode='OBJECT')
        
    if js_geometry["numMorphTargets"] != 1:
        print("skipping geometry, because of num morph targets != 1")
        return;
    
    if js_geometry["numTris"] == 0:
        print("skipping geometry because of no tris")
        return;
        
    bm = bmesh.new()
    wd = bm.verts.layers.deform.verify()
    uvs = bm.loops.layers.uv.verify()
    
    mesh = bpy.data.meshes.new("mesh")
    
    uv_coordinates = []
    for textureCoords in js_geometry["textureCoordinates"][0]: # assume one set of texture coordinates...
        uv_coordinates.append((textureCoords["u"], textureCoords["v"]))
    
    vertex_index = 0;
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
                ln = [l for l in face.loops if l.vert == vn][0]
                u0, v0 = [uv_coordinates[vn.index][0], uv_coordinates[vn.index][1]]
                ln[uvs].uv = (u0, 1.0 - v0)
            
            
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
    
    tex_name = js_geometry["materials"][0]["textures"][0]["texture"]
    material = set_material(tex_name)
    # TODO
    #set_texture(material,tex_name)
    """
        def set_texture(material, name):

        for slot in material.texture_slots:
            print(slot)
            if slot:
                if slot.name == name:
                    return
                
        tex = bpy.data.textures.new(name, 'IMAGE')
        slot = material.texture_slots.add()
        slot.texture = tex

    """
    



def frameIndexToName(frameIndex, length):
    return str(frameIndex).zfill(length)


def read_json_rigid(js, use_connect):

    js_clump = js["clump"]
    arm_o, boneNames, frames, hierarchy = make_armature_from_frames(js_clump["frames"], use_connect)    

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



def getMatrixByEditBone2(bone):

    mat = mu.Matrix()

    parents = []

    bone2 = bone.parent
    while bone2 != None:
        parents.append(bone2)
        bone2 = bone2.parent

    mat = editBoneToMatrix(bone)
    
    for index in reversed(len(parents)):
        mat = editBoneToMatrix(parents[index]).inverted() * mat

   # mat = mat * editBoneToMatrix(bone).inverted()
    return mat


def getMatrixByEditBone(bone):

    mat = mu.Matrix()
    while bone != None:
        mat = mat * editBoneToMatrix(bone)
        bone = bone.parent
    return mat


def editBoneToMatrix(bone):
    translation = bone.head
    tail = bone.tail - translation
    tail = tail / 100
    roll = bone.roll
    mat3x3 = vec_roll_to_mat3(tail, roll)

    mat4x4 = mat3x3.to_4x4()
    mat4x4.translation = translation

    return mat4x4


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
    
    return nodeToBoneId

def calculateBoneIdsByLength(hierarchy, numKeyframes):
    firstBone = len(hierarchy) - numKeyframes
    return calculateBoneIds(hierarchy, firstBone)





def determine_hierarchy_and_rest_matrices(ob):
    
    numBones = len(ob.pose.bones)
    # Rest Matrices ermitteln
    bpy.ops.object.mode_set(mode='EDIT')


    hierarchy = []
    restMatrices = []

    for frameIndex in range(numBones):
        bone = ob.data.edit_bones[frameIndex]
        parentIndex = -1
        if bone.parent:
            for b in range(numBones):
                if ob.data.edit_bones[b] == bone.parent:
                    parentIndex = b
        hierarchy.append(parentIndex)

        mat4x4 = editBoneToMatrix(bone)
        if bone.parent:
            mat4x4 = editBoneToMatrix(bone.parent).inverted() * mat4x4
        restMatrices.append(mat4x4)

    bpy.ops.object.mode_set()
    # Rest Matrices & Hierarchy ermittelt

    return hierarchy, restMatrices


def read_rigid_animation(js):
    
    print("read_rigid_animation")

    nodes = js["nodes"]

    sce = bpy.context.scene
    ob = bpy.context.object

    numBones = len(ob.pose.bones)

    # Rest Matrices ermitteln
    bpy.ops.object.mode_set(mode='EDIT')

    hierarchy = []
    restMatrices = []

    for frameIndex in range(numBones):
        bone = ob.data.edit_bones[frameIndex]
        parentIndex = -1
        if bone.parent:
            for b in range(numBones):
                if ob.data.edit_bones[b] == bone.parent:
                    parentIndex = b
        hierarchy.append(parentIndex)

        mat4x4 = editBoneToMatrix(bone)
        if bone.parent:
            mat4x4 = editBoneToMatrix(bone.parent).inverted() * mat4x4
        restMatrices.append(mat4x4)

    bpy.ops.object.mode_set()
    # Rest Matrices & Hierarchy ermittelt

    sce.frame_set(0)

    # animationBoneIndexToBoneIndex entspricht dem nodeIndex

    animationBoneIndexToBoneIndex = calculateBoneIdsByLength(hierarchy, len(nodes))

    print("animationBoneIndexToBoneIndex", animationBoneIndexToBoneIndex)
    
    for nodeIndex, node in enumerate(nodes):

        boneIndex = animationBoneIndexToBoneIndex[nodeIndex]
        print(nodeIndex, boneIndex, "->", len(node))

        for frameIndex, frame in enumerate(node):
            
            time = int(frame["time"] * 24)
            
            sce.frame_set(time)

            pose_bone = ob.pose.bones[boneIndex]
            
            js_translation = frame["position"]
            quat = mu.Quaternion((frame["quaternion"]["w"], frame["quaternion"]["x"], frame["quaternion"]["y"], frame["quaternion"]["z"]))
            translation = mu.Vector((js_translation["x"], js_translation["y"], js_translation["z"]))
            mat = quat.to_matrix().to_4x4()
            mat.translation = translation

            from_js_matrix = mat
            # this is it!
            pose_bone.matrix_basis = restMatrices[boneIndex].inverted()  * from_js_matrix

            pose_bone.keyframe_insert(data_path="rotation_quaternion",frame=time)
            pose_bone.keyframe_insert(data_path="location",frame=time)
            
    sce.frame_set(0)
    
    return {'FINISHED'}
    

def get_rigid_animation():

    print("get_rigid_animation")

    sce = bpy.context.scene
    ob = bpy.context.object
    
    anim_data = ob.animation_data
    action = anim_data.action
    
    print(len(action.fcurves))
        
    #blender_rot = mu.Quaternion((0.707, 0, 0, -0.707))
    #blender_rot_inv = blender_rot.inverted()
    
    duration = 0
    
    nodes = []
    
    bones_sorted = []
    for bone in ob.pose.bones:
        bones_sorted.append(bone)
    
    #bones_sorted.sort(key=lambda bone: bone.name)


    numExportedBones = 0
    
    boneIdToKeyframes = []

    hierarchy, restMatrices = determine_hierarchy_and_rest_matrices(ob)

    for boneIndex in range(len(bones_sorted)):
        keyframes = []
        
        bone = bones_sorted[boneIndex]
        #print(bone.name)
        
        times = {}
        
        for fcurve in action.fcurves:
            #print(fcurve.data_path)
            if (fcurve.data_path == ('pose.bones["%s"].location' % bone.name)) or (fcurve.data_path == ('pose.bones["%s"].rotation_quaternion' % bone.name)):
                for key in fcurve.keyframe_points:
                    times[key.co[0]] = True
        
        times_array = []
        for time, val in enumerate(times):
            times_array.append(val)
            
        times_array.sort()   
        #print("times_array", times_array)

        
        for index, time in enumerate(times_array):
            #times_array[index] = float(time / 24)
            
            sce.frame_set(time)
            
            t = time / 24
            duration = max(duration, t)


            pose_bone = ob.pose.bones[boneIndex]
            # to get the pose this was used:
            #pose_bone.matrix_basis = restMatrices[boneIndex].inverted()  * from_js_matrix

            # reverse it...
            matrix_basis = pose_bone.matrix_basis
            from_js_matrix = restMatrices[boneIndex] * matrix_basis

            
            matrix = from_js_matrix
            pos = matrix.translation
            rot = matrix.to_quaternion()
            
            keyframe = OrderedDict()
            keyframe["time"] = t;
            keyframe["position"] = OrderedDict()
            keyframe["position"]["x"] = pos.x
            keyframe["position"]["y"] = pos.y
            keyframe["position"]["z"] = pos.z
            
            keyframe["quaternion"] = OrderedDict()
            keyframe["quaternion"]["w"] = rot.w
            keyframe["quaternion"]["x"] = rot.x
            keyframe["quaternion"]["y"] = rot.y
            keyframe["quaternion"]["z"] = rot.z
            
            keyframes.append(keyframe)

           # if bone.name == "frame_053":
                #print("bone", bone)
            
            #print(rot, pos)
        
        boneIdToKeyframes.append(keyframes)

        # skip all bones with no keyframes
        if len(keyframes) == 0:
            continue
        
        numExportedBones = numExportedBones + 1
        #nodes.append(keyframes)

    animationBoneIndexToBoneIndex = calculateBoneIdsByLength(hierarchy, numExportedBones)

    print("animationBoneIndexToBoneIndex", animationBoneIndexToBoneIndex )

    for i in range(len(animationBoneIndexToBoneIndex )):
        boneId = animationBoneIndexToBoneIndex [i]
        print(i, boneId, "->", len(boneIdToKeyframes[boneId]))
        nodes.append(boneIdToKeyframes[boneId])

#    print(animToAnim)
            
    js = {}
    js["duration"] = duration
    js["nodes"] = nodes    
    return js



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

def generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas):

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

            #print(nodeID, nodeIdToFrameIndex[nodeID], index, parents[j] == index)




    #return

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
        if userData != None:
            extension['userDataPLG'] = userData

        if frameIndex != 0:
            extension['hanimPLG'] = {}
            extension['hanimPLG']['flags'] = 0
            extension['hanimPLG']['keyFrameSize'] = 0
            extension['hanimPLG']['nodeID'] = nodeIds[frameIndex] #frameIndex + 5
            extension['hanimPLG']['numNodes'] = 0
        
        if frameIndex == 1:

            extension['hanimPLG']['numNodes'] = len(parents)
            extension['hanimPLG']['parents'] = parents
            extension['hanimPLG']['nodes'] = []
            extension['hanimPLG']['flags'] = 0 #28672
            extension['hanimPLG']['keyFrameSize'] = 36

            #parents = []

            
            #for j, nodeID in enumerate(exportOrder):
            #    boneIndex = nodeIdToFrameIndex[nodeID]
            #    print(nodeID, boneIndex, len(exportOrder))
            #    if j == 0:
            #        parents.append(-1)
            #    else:
            #        parents.append(hierarchy[boneIndex] - 1)

            matrixflags = generateMatrixFlags(parents)

            for j, nodeID in enumerate(exportOrderAuto):
                boneIndex = nodeIdToFrameIndex[nodeID]
                node = OrderedDict()
                node['flags'] = matrixflags[j]
                node['nodeID'] = nodeID
                node['nodeIndex'] = j
                
                extension['hanimPLG']['nodes'].append(node)

            
            if False:
                parents = []
                for i in range(1, len(hierarchy)):
                    parent = hierarchy[i]
                #  parent = parent - 1
                    parents.append(parent)
                    

                matrixflags = generateMatrixFlags(parents)



                extension['hanimPLG']['numNodes'] = len(parents)
                extension['hanimPLG']['parents'] = parents
                extension['hanimPLG']['nodes'] = []
                extension['hanimPLG']['flags'] = 0 #28672
                extension['hanimPLG']['keyFrameSize'] = 36

                for j, parent2 in enumerate(parents):
                    node = OrderedDict()
                    node['flags'] = matrixflags[j]
                    node['nodeID'] = nodeIds[j + 1]
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
        
def get_bone_by_name(ob, name):
    for bone in ob.pose.bones:
        if bone.name == name:
            return bone
    

def new_mesh_obj_to_json(mesh_obj, invertedRestMatrix):
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
    
    # TODO: Sphere? Probably used for clipping
    js_morphTarget['sphere'] = OrderedDict()
    js_morphTarget['sphere']['x'] = 0
    js_morphTarget['sphere']['y'] = 0
    js_morphTarget['sphere']['z'] = 0
    js_morphTarget['sphere']['radius'] = max(dimensions[0], dimensions[1], dimensions[2])
    
    data['morphTargets'].append(js_morphTarget)
    
    
    js_textureCoordinates = [None] * data['numVertices']
    
    for face in mesh_obj.data.polygons:
        for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
            uv_coords = mesh_obj.data.uv_layers.active.data[loop_idx].uv
            
            uv = OrderedDict()
            uv['u'] = uv_coords.x
            uv['v'] = 1 - uv_coords.y
            
            js_textureCoordinates[vert_idx] = uv
    
    data['textureCoordinates'] = []
    data['textureCoordinates'].append(js_textureCoordinates)
    
    data['format'] = 65591 # TODO, depends on texture stuff...
    
    
    
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
            texture["texture"] = mat.name
            texture["textureAlpha"] = ""
            
            material['textures'].append(texture)
            
            data['materials'].append(material)
    
    return data

def get_bone_by_name_(bones, name):
    for bone in bones:
        if bone.name == name:
            return bone

def get_json_rigid():
    # armature must be selected!

    sce = bpy.context.scene
    ob = bpy.context.object

        
    #os.system("cls")

 #   print(ob)

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
    clump["frames"] = generate_frame_list(boneNamesSorted, hierarchy, restMatrices, userDatas)
    clump["atomics"] = []
    clump["geometries"] = []

    #return

    
    geometryIndex = 0
    for mesh in meshesToExport:
        frameIndex = get_bone_index_by_bone_name(boneNamesSorted, mesh.vertex_groups[0].name)


        #print("FrameIndex", frameIndex, mesh.vertex_groups[0].name)

       # print(get_bone_by_name(ob, mesh.vertex_groups[0].name))
#         xyz = (frameRestMatrix * mu.Vector((x,y,z, 1))).to_3d()


        # rest matrix für aktuelles geometry ermitteln
        mat = restMatrices[frameIndex]
        index = hierarchy[frameIndex]
        while hierarchy[index] != -1:
            mat = restMatrices[index] * mat
            #print("parent", index)

            index = hierarchy[index]


        frameRestMatrix = mat

        clump["geometries"].append(new_mesh_obj_to_json(mesh, frameRestMatrix.inverted()))
        """
        geometryVertex = new_mesh_obj_to_json(mesh, frameRestMatrix.inverted())
        originalVertex = mu.Vector((4.038628578186035, 0.000012976015568710864, -144.71014404296875))
        
        print("orig", originalVertex)
        print("mesh", geometryVertex)

        mat53 = restMatrices[53]
        mat52 = restMatrices[52]
        mat51 = restMatrices[51]
        mat50 = restMatrices[50]
        mat49 = restMatrices[49]
        mat1 = restMatrices[1]
        mat0 = restMatrices[0]

        print((mat0 * mat1 * mat49 * mat50 * mat51 * mat52 * mat53) * originalVertex)
        xyz = (frameRestMatrix * originalVertex) #mu.Vector((4.038628578186035, 0.000012976015568710864, -144.71014404296875, 1))).to_3d()
        print(xyz)

        print(frameRestMatrix)
        print(mat0 * mat1 * mat49 * mat50 * mat51 * mat52 * mat53)

        print(frameRestMatrix.inverted() * geometryVertex)

        #print(frameRestMatrix)
        #print(geometryVertex * frameRestMatrix.inverted())

        return
        """

        #originalVertex = mu.Vector((-0.0677613914012909, 84.50083923339844, -84.85282135009766))
        #geometryVertex = mu.Vector((-85.2049, -366.4429, 35.1105))
        """
        vert = new_mesh_obj_to_json(mesh, frameRestMatrix)
        print("ORIGINAL", originalVertex)
        print("VERT:",vert)
        print("->", originalVertex * frameRestMatrix)

        print(originalVertex * frameRestMatrix)
        print(originalVertex * frameRestMatrix)
        print(originalVertex * frameRestMatrix * frameRestMatrix.inverted())

        print(vert - frameRestMatrix.to_translation())

        print(frameRestMatrix)
        print(restMatrices[frameIndex])
        """

        
        # add geometry to atomics
        atomic = OrderedDict()
        atomic["frameIndex"] = frameIndex
        atomic["geometryIndex"] = geometryIndex
        clump["atomics"].append(atomic)
        geometryIndex = geometryIndex + 1
    

    js = {}
    js["clump"] = clump

    return js



def read_json_model(context, filepath, use_connect):
    read_json_rigid(filepath, use_connect);
    return {'FINISHED'}

def write_animaton(path):
    sce = bpy.context.scene
    ob = bpy.context.object
    
    anim_data = ob.animation_data
    action = anim_data.action
    
    os.system('cls')
    
    print(len(action.fcurves))
        
    blender_rot = mu.Quaternion((0.707, 0, 0, -0.707))
    blender_rot_inv = blender_rot.inverted()
    
    duration = 0
    
    nodes = []
    
    bones_sorted = []
    for bone in ob.pose.bones:
        bones_sorted.append(bone)
    bones_sorted.sort(key=lambda bone: bone.name)
    
    for bone in bones_sorted:
        keyframes = []
        
        
        print(bone.name)
        
        times = {}
        
        for fcurve in action.fcurves:
            print(fcurve.data_path)
            if (fcurve.data_path == ('pose.bones["%s"].location' % bone.name)) or (fcurve.data_path == ('pose.bones["%s"].rotation_quaternion' % bone.name)):
                for key in fcurve.keyframe_points:
                    times[key.co[0]] = True
        
        times_array = []
        for time, val in enumerate(times):
            times_array.append(val)
            
        times_array.sort()   
        print("times_array", times_array)

        
        for index, time in enumerate(times_array):
            #times_array[index] = float(time / 24)
            
            sce.frame_set(time)
            
            t = time / 24
            duration = max(duration, t)
            
            matrix = bone.matrix
            pos = matrix.translation
            rot = matrix.to_quaternion()
            
            rot = mul_matrix(rot, blender_rot_inv)
            parent_rot = mu.Quaternion((1,0,0,0)) if bone.parent == None else mul_matrix(bone.parent.matrix.to_quaternion(), blender_rot_inv)
            parent_pos = mu.Vector((0,0,0)) if bone.parent == None else bone.parent.matrix.translation 
            
            rot = mul_matrix(parent_rot.inverted(), rot)
            
            pos = pos - parent_pos
            pos = mul_matrix(parent_rot.inverted().to_matrix(), pos)
            
            keyframe = {}
            keyframe["time"] = t;
            keyframe["position"] = {}
            keyframe["position"]["x"] = pos.x
            keyframe["position"]["y"] = pos.y
            keyframe["position"]["z"] = pos.z
            
            keyframe["quaternion"] = {}
            keyframe["quaternion"]["w"] = rot.w
            keyframe["quaternion"]["x"] = rot.x
            keyframe["quaternion"]["y"] = rot.y
            keyframe["quaternion"]["z"] = rot.z
            
            keyframes.append(keyframe)
            
            #print(rot, pos)
        
        # Skip root bone if frame based animation
        if len(nodes) == 0 and len(keyframes) == 0:
            continue
        
        nodes.append(keyframes)
            
    js = {}
    js["duration"] = duration
    js["nodes"] = nodes    
    
    with open(path, "w") as outfile:
       #json.dump(data, outfile, indent=4)
       json.dump(js, outfile, indent=4)
   


    









def write_animaton_wrapper(context, filepath, obj):    
    sce = bpy.context.scene
    ob = bpy.context.object
    
    if ob.type != 'ARMATURE':
        obj.report({"WARNING"}, "Selected object must be of type Armature!")
        return {'CANCELLED'}
    
    write_animaton(filepath)

    return {'FINISHED'}



def read_skinned_animation(path):
    fh = open(path, "r")
    j = json.load(fh)
    fh.close()
    
    duration = j["duration"]
    nodes = j["nodes"]
    
    sce = bpy.context.scene
    ob = bpy.context.object
    
    
    # save 'rest' position at frame 0
    sce.frame_set(0)
    
    #bpy.ops.anim.keyframe_clear_v3d()

    #for pbone in ob.pose.bones:
    #    pbone.keyframe_insert(data_path="location",frame=0)
    #    pbone.keyframe_insert(data_path="rotation_quaternion",frame=0)
    
    blender_rot = mu.Quaternion((0.707, 0, 0, -0.707))
    blender_rot_inv = blender_rot.inverted()
    
    for nodeIndex, node in enumerate(nodes):
        for frameIndex, frame in enumerate(node):
            
            time = (frame["time"] * 24)# + 5
            
            sce.frame_set(time)
            
            #pose_bone = ob.pose.bones["skin_" + str(nodeIndex)]
            pose_bone = ob.pose.bones[nodeIndex]
            
            js_translation = frame["position"]
            quat = mu.Quaternion((frame["quaternion"]["w"], frame["quaternion"]["x"], frame["quaternion"]["y"], frame["quaternion"]["z"]))
            translation = mu.Vector((js_translation["x"], js_translation["y"], js_translation["z"]))
            
            rot = mu.Quaternion((1,0,0,0)) if pose_bone.parent == None else mul_matrix(pose_bone.parent.matrix.to_quaternion(), blender_rot_inv)
            pos = mu.Vector((0,0,0)) if pose_bone.parent == None else pose_bone.parent.matrix.translation 
            
            pos = mul_matrix(rot.to_matrix(), translation) + pos
            rot = mul_matrix(mul_matrix(rot, quat), blender_rot)
            
            #print(nodeIndex, rot * blender_rot_inv, pos)
            
            matrix = rot.to_matrix().to_4x4()
            matrix.translation = pos
            
            pose_bone.matrix = matrix
            
            pose_bone.keyframe_insert(data_path="rotation_quaternion",frame=time)
            pose_bone.keyframe_insert(data_path="location",frame=time)
            
    sce.frame_set(0)



def set_bone_matrix(bone, frame, idx):
    
    current_mtx = mu.Quaternion((frame["quaternion"]["w"], frame["quaternion"]["x"], frame["quaternion"]["y"], frame["quaternion"]["z"]))
    
    js_quat = frame["quaternion"]
    x = js_quat["x"]
    y = js_quat["y"]
    z = js_quat["z"]
    w = js_quat["w"]
    
    current_mtx = mu.Quaternion((frame["quaternion"]["w"], frame["quaternion"]["x"], frame["quaternion"]["y"], frame["quaternion"]["z"]))
    current_mtx = current_mtx.to_matrix().to_4x4()
    
    current_mtx = mu.Quaternion(( w,  x, y, z)).to_matrix().to_4x4()
    
    js_translation = frame["position"]
    translation = mu.Vector((js_translation["x"], js_translation["y"], js_translation["z"]))
    
    offset = bone.bone.head
    
    parents = mu.Vector((0, 0, 0))
    parent = bone.bone.parent
    
    while parent != None:
        parents = parents + bone.bone.parent.head
        parent = None#parent.parent
    current_mtx.translation = translation - bone.bone.head #- parents
    
    
    bone.matrix_basis = current_mtx
    
    bone.keyframe_insert(data_path="rotation_quaternion",frame=idx)#frameIndex+10)
    bone.keyframe_insert(data_path="location",frame=idx)#frameIndex+10)


def read_animation_wrapper(context, filepath):#, skinned):
    fh = open(filepath, "r")
    j = json.load(fh)
    fh.close()
    
    duration = j["duration"]
    numNodes = len(j["nodes"])
    
    read_skinned_animation(filepath)
    
    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

import subprocess

bl_info = {
    "name": "DFF-JSON & ANM-JSON Rigid Model/Animation Imp-/Exporter",
    "location": "File > Import-Export",
    "blender": (2, 80, 0), # meh...
    "category": "Import-Export",
}

class AnimationImporterANM(Operator, ImportHelper):
    bl_idname = "import_animation.rigid_anm"
    bl_label = "ANM-Animation (.anm)"
    filename_ext = "*.anm"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        read_animation(self.filepath)
        return {'FINISHED'}
class AnimationImporterJSON(Operator, ImportHelper):
    bl_idname = "import_animation.rigid_json"
    bl_label = "JSON-Animation (.json)"
    filename_ext = "*.json"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        read_animation(self.filepath)
        return {'FINISHED'}

class AnimationExporterANM(Operator, ExportHelper):
    bl_idname = "export_animation.rigid_anm"
    bl_label = "ANM-Animation (.anm)"
    filename_ext = ".anm"
    filter_glob = StringProperty(
            default="*" + filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        write_animation(self.filepath)
        return {'FINISHED'}
class AnimationExporterJSON(Operator, ExportHelper):
    bl_idname = "export_animation.rigid_json"
    bl_label = "JSON-Animation (.json)"
    filename_ext = ".json"
    filter_glob = StringProperty(
            default="*" + filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        write_animation(self.filepath)
        return {'FINISHED'}

class ModelImporterDFF(Operator, ImportHelper):
    bl_idname = "import_model.rigid_dff"
    bl_label = "Rigid-DFF-Model (.dff)"
    filename_ext = "*.dff"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )   
    def execute(self, context):
        read_model(self.filepath)
        return {'FINISHED'}
class ModelImporterJSON(Operator, ImportHelper):
    bl_idname = "import_model.rigid_json"
    bl_label = "Rigid-JSON-Model (.json)"
    filename_ext = "*.json"
    filter_glob = StringProperty(
            default=filename_ext,
            options={'HIDDEN'},
            )   
    def execute(self, context):
        read_model(self.filepath)
        return {'FINISHED'}

class ModelExporterDFF(Operator, ExportHelper):
    bl_idname = "export_model.rigid_dff"
    bl_label = "Rigid-DFF-Model (.dff)"
    filename_ext = ".dff"
    filter_glob = StringProperty(
            default="*" + filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        write_model(self.filepath)
        return {'FINISHED'} 
class ModelExporterJSON(Operator, ExportHelper):
    bl_idname = "export_model.rigid_json"
    bl_label = "Rigid-JSON-Model (.json)"
    filename_ext = ".json"
    filter_glob = StringProperty(
            default="*" + filename_ext,
            options={'HIDDEN'},
            )
    def execute(self, context):
        write_model(self.filepath)
        return {'FINISHED'}



def menu_func_import_animationANM(self, context):
    self.layout.operator(AnimationImporterANM.bl_idname, AnimationImporterANM.bl_label)
def menu_func_import_animationJSON(self, context):
    self.layout.operator(AnimationImporterJSON.bl_idname, AnimationImporterJSON.bl_label)

def menu_func_export_animationANM(self, context):
    self.layout.operator(AnimationExporterANM.bl_idname, AnimationExporterANM.bl_label)
def menu_func_export_animationJSON(self, context):
    self.layout.operator(AnimationExporterJSON.bl_idname, AnimationExporterJSON.bl_label)

def menu_func_import_ModelDFF(self, context):
    self.layout.operator(ModelImporterDFF.bl_idname, ModelImporterDFF.bl_label)
def menu_func_import_ModelJSON(self, context):
    self.layout.operator(ModelImporterJSON.bl_idname, ModelImporterJSON.bl_label)

def menu_func_export_ModelDFF(self, context):
    self.layout.operator(ModelExporterDFF.bl_idname, ModelExporterDFF.bl_label)
def menu_func_export_ModelJSON(self, context):
    self.layout.operator(ModelExporterJSON.bl_idname, ModelExporterJSON.bl_label)


def register():
    if (2, 80, 0) <= bpy.app.version:
        from bpy.utils import register_class
        classes = (AnimationImporter, ExportAnimation, ImportModel, ExportModel)
        for cls in classes:
            register_class(cls)
            
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import_animation)
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import_model)
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export_model)
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export_animation)
        
    else:
        bpy.utils.register_module(__name__)
        bpy.types.INFO_MT_file_import.append(menu_func_import_animationANM)
        bpy.types.INFO_MT_file_import.append(menu_func_import_animationJSON)

        bpy.types.INFO_MT_file_export.append(menu_func_export_animationANM)
        bpy.types.INFO_MT_file_export.append(menu_func_export_animationJSON)

        bpy.types.INFO_MT_file_import.append(menu_func_import_ModelDFF)
        bpy.types.INFO_MT_file_import.append(menu_func_import_ModelJSON)

        bpy.types.INFO_MT_file_export.append(menu_func_export_ModelDFF)
        bpy.types.INFO_MT_file_export.append(menu_func_export_ModelJSON)


def unregister():
    if (2, 80, 0) <= bpy.app.version:
        classes = (AnimationImporter, ExportAnimation, ImportModel, ExportModel)

        from bpy.utils import unregister_class
        for cls in reversed(classes):
            unregister_class(cls)
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_animation)
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_model)
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_model)
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_animation)
    else:
        bpy.utils.unregister_module(__name__)
        bpy.types.INFO_MT_file_import.remove(menu_func_import_animationANM)
        bpy.types.INFO_MT_file_import.remove(menu_func_import_animationJSON)

        bpy.types.INFO_MT_file_export.remove(menu_func_export_animationANM)
        bpy.types.INFO_MT_file_export.remove(menu_func_export_animationJSON)

        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelDFF)
        bpy.types.INFO_MT_file_import.remove(menu_func_import_ModelJSON)

        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelDFF)
        bpy.types.INFO_MT_file_export.remove(menu_func_export_ModelJSON)


def get_converter_exe_location():
    offset = __file__.rfind("\\")
    exe_loc = __file__[:offset] + "\\RW_inline.exe"
   # exe_loc = "C:\\Users\\Simon\\AppData\\Roaming\\Blender Foundation\\Blender\\2.79\\scripts\\addons" + "\\RW_inline.exe"
   # exe_loc = "G:\\Test\\DFF-ANM-Converter\\RW\\RW\\Debug\\RW.exe"
    return exe_loc


def convert_to_js_external(binary_data):
    p = subprocess.Popen(get_converter_exe_location(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    outs, errs = p.communicate(input=binary_data)

    return outs.decode('utf-8')

def read_animation(path):
    js = None
    if path.endswith(".anm"):
        with open(path, 'rb') as file:
            data = convert_to_js_external(file.read())
            js = json.loads(data)
    else:
        fh = open(path, "r")
        js = json.load(fh)
        fh.close()

    read_rigid_animation(js)
    
def read_model(path):
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

def write_animation(path):
    js = get_rigid_animation()
    
    if path.endswith(".json"):
        with open(path, "w") as outfile:
            json.dump(js, outfile, indent=4)
    else:
        p = subprocess.Popen(get_converter_exe_location(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        js_str = json.dumps(js)
        bytes = js_str.encode('utf-8')
        x = p.stdin.write(bytes)

        print(x, len(bytes))
        p.stdin.flush()
        p.stdin.close()

        outs, errs = p.communicate()

        with open(path, "wb") as outfile:
            outfile.write(outs)

def write_model(path):
    js = get_json_rigid()
    
    if path.endswith(".json"):
        with open(path, "w") as outfile:
            json.dump(js, outfile, indent=4)
    else:
        p = subprocess.Popen(get_converter_exe_location(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        js_str = json.dumps(js)
        bytes = js_str.encode('utf-8')
        x = p.stdin.write(bytes)

        print(x, len(bytes))
        p.stdin.flush()
        p.stdin.close()

        outs, errs = p.communicate()

        with open(path, "wb") as outfile:
            outfile.write(outs)

#write_model("G:\\Test\\test.json")
#write_model("G:\\Test\\test.dff")
#read_model("G:\\Test\\test.dff")
#read_model("G:\\Test\\orig\\pb_foundry2.dff")
#write_animation("G:\\Test\\pb_foundry2_cannon4_603_export.anm")
#read_animation("G:\\Test\\pb_foundry2_cannon4_603_export.json")

#os.system("cls")

#read_model("G:\\Test\\orig\\pv_cannon4.dff")
#read_animation("G:\\Test\\orig\\pv_cannon4_destroyed.anm")
#read_animation("G:\\Test\\orig\\pb_foundry2_cannon4_603.anm")
#write_animation("G:\\Test\\pv_cannon4_destroyed_export.anm")
#read_animation("G:\\Test\\pv_cannon4_destroyed_export.anm")

#write_animation("G:\\Test\\pb_foundry2_cannon4_603_export.anm")
#read_model("G:\\Test\\pb_monastery1.dff")

if __name__ == "__main__":
    register()

    # test call
    #bpy.ops.import_model.json_dff('INVOKE_DEFAULT')

    #read_json_rigid("G:\\Test\\pb_university2.json", False)
    #read_rigid_animation("G:\\Test\\pb_university2_astrodome_601.json")
    #write_rigid_animation("G:\\Test\\pb_university2_astrodome_601_output_edited.json")
    #read_rigid_animation("G:\\Test\\pb_university2_astrodome_601_output.json")

    
    #write_json_rigid("G:\\Test\\pb_foundry2_output.json")
    #read_json_rigid("G:\\Test\\pb_foundry2_output.json", False)

    #read_model("G:\\Test\\cb_abbey01.dff")
    #read_model("G:\\Test\\cb_abbey01.json")

    #read_json_rigid("G:\\Test\\cb_abbey01_output.json", False)
    #write_json_rigid("G:\\Test\\cb_abbey01_output.json")
    #write_rigid_animation("G:\\Test\\cb_abbey01_output_anim.json")
    #read_rigid_animation("G:\\Test\\cb_abbey01_output_anim.json")

    #read_json_rigid("G:\\Test\\pb_foundry2.json", False)
    #read_rigid_animation("G:\\Test\\pb_foundry2_cannon4_603.json")

    #write_rigid_animation("G:\\Test\\pb_foundry2_cannon4_603_output.json")
    #read_rigid_animation("G:\\Test\\pb_foundry2_cannon4_603_output.json")


   # bpy.ops.import_animation.json_anm('INVOKE_DEFAULT')

    