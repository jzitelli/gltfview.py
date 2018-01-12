import os.path
from copy import copy, deepcopy
from collections import defaultdict
from itertools import chain
import json
import logging

import OpenGL.GL as gl

_logger = logging.getLogger(__name__)
_here = os.path.dirname(__file__)


_PBRMR_PROGRAM_ATTRIBUTES = {
    'a_Position': {'type': gl.GL_FLOAT_VEC3,
                   'semantic': 'POSITION'},
    'a_Normal': {'type': gl.GL_FLOAT_VEC4,
                 'semantic': 'NORMAL'},
    'a_UV': {'type': gl.GL_FLOAT_VEC2,
             'semantic': 'TEXCOORD_0'},
    'a_Tangent': {'type': gl.GL_FLOAT_VEC4}
}
_PBRMR_PROGRAM_UNIFORMS = {
    'u_ModelMatrix': {'type'    : gl.GL_FLOAT_MAT4,
                      'semantic': 'MODELVIEW'},
    'u_ProjectionMatrix': {'type': gl.GL_FLOAT_MAT4,
                           'semantic': 'PROJECTION'},
    'u_MVPMatrix': {'type'    : gl.GL_FLOAT_MAT4,
                    'semantic': 'MODELVIEWPROJECTION'},
    'u_LightDirection': {'type' : gl.GL_FLOAT_VEC3,
                         'value': [0.1, 1.0, 0.5]},
    'u_LightColor': {'type' : gl.GL_FLOAT_VEC3,
                     'value': [1.0, 1.0, 0.8]},
    'u_DiffuseEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    'u_SpecularEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    'u_brdfLUT': {'type': gl.GL_SAMPLER_2D},
    'u_BaseColorSampler': {'type': gl.GL_SAMPLER_2D},
    'u_NormalSampler': {'type': gl.GL_SAMPLER_2D},
    'u_NormalScale': {'type' : gl.GL_FLOAT,
                      'value': 1.0},
    'u_EmissiveSampler': {'type': gl.GL_SAMPLER_2D},
    'u_EmissiveFactor': {'type' : gl.GL_FLOAT_VEC3,
                         'value': [0.0, 0.0, 0.0]},
    'u_MetallicRoughnessSampler': {'type': gl.GL_SAMPLER_2D},
    'u_OcclusionSampler': {'type': gl.GL_SAMPLER_2D},
    'u_OcclusionStrength': {'type' : gl.GL_FLOAT,
                            'value': 1.0},
    'u_MetallicRoughnessValues': {'type' : gl.GL_FLOAT_VEC2,
                                  'value': [0.0, 0.0]},
    'u_BaseColorFactor': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [1.0, 1.0, 0.5, 0.0]},
    'u_Camera': {'type' : gl.GL_FLOAT_VEC3,
                 'value': [0.0, 0.0, 1.0]},
    'u_ScaleDiffBaseMR': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [0.0, 0.0, 0.0, 0.0]},
    'u_ScaleFGDSpec': {'type' : gl.GL_FLOAT_VEC4,
                       'value': [0.0, 0.0, 0.0, 0.0]},
    'u_ScaleIBLAmbient': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [0.0, 0.0, 0.0, 0.0]}
}
_REQUIRED_ATTRIBUTES = ['a_Position']
_REQUIRED_UNIFORMS = [#'u_MVPMatrix',
                      'u_ModelMatrix',
                      'u_ProjectionMatrix',
                      ]
_GLSL_TO_GLTF_ATTR = {'a_Position': 'POSITION',
                      'a_Normal'  : 'NORMAL',
                      'a_UV'      : 'TEXCOORD_0'}
_GLSL_TO_GLTF_UNIF = {'u_ModelMatrix'              : 'u_ModelMatrix',
                      'u_ProjectionMatrix'         : 'u_ProjectionMatrix',
                      'u_LightDirection'           : 'lightDirection',
                      'u_LightColor'               : 'lightColor',
                      'u_Camera'                   : 'cameraPosition',
                      'u_ScaleDiffBaseMR'          : 'scaleDiffBaseMR',
                      'u_NormalSampler'            : 'normalTexture',
                      'u_NormalScale'              : 'normalScale',
                      'u_MetallicRoughnessSampler' : 'metallicRoughnessTexture',
                      'u_OcclusionSampler'         : 'occlusionTexture',
                      'u_OcclusionStrength'        : 'occlusionStrength',
                      'u_EmissiveSampler'          : 'emissiveTexture',
                      'u_EmissiveFactor'           : 'emissiveFactor',
                      'u_BaseColorSampler'         : 'baseColorTexture',
                      'u_MetallicRoughnessValues.x': 'metallicFactor',
                      'u_MetallicRoughnessValues.y': 'roughnessFactor',
                      'u_BaseColorFactor'          : 'baseColorFactor'}
_GLSL_ATTR_TO_DEFINE = {'a_Normal' : 'HAS_NORMALMAP',
                        'a_Tangent': 'HAS_TANGENTS',
                        'a_UV'     : 'HAS_UV'}
_GLSL_UNIF_TO_DEFINE = {'u_DiffuseEnvSampler'       : 'USE_IBL',
                        'u_SpecularEnvSampler'      : 'USE_IBL',
                        'u_brdfLUT'                 : 'USE_IBL',
                        'u_BaseColorSampler'        : 'HAS_COLORMAP',
                        'u_NormalSampler'           : 'HAS_NORMALMAP',
                        'u_NormalScale'             : 'HAS_NORMALMAP',
                        'u_EmissiveSampler'         : 'HAS_EMISSIVEMAP',
                        'u_EmissiveFactor'          : 'HAS_EMISSIVEMAP',
                        'u_MetallicRoughnessSampler': 'HAS_METALROUGHNESSMAP',
                        'u_OcclusionSampler'        : 'HAS_OCCLUSIONMAP',
                        'u_OcclusionStrength'       : 'HAS_OCCLUSIONMAP'}
_DEFINE_TO_GLTF_PBRMR_ATTRS = defaultdict(list)
for attr, define in _GLSL_ATTR_TO_DEFINE.items():
    _DEFINE_TO_GLTF_PBRMR_ATTRS[define].append(attr)
_DEFINE_TO_GLTF_PBRMR_UNIFS = defaultdict(list)
for unif, define in _GLSL_UNIF_TO_DEFINE.items():
    _DEFINE_TO_GLTF_PBRMR_UNIFS[define].append(unif)


def setup_pbrmr_programs(gltf):
    with open(os.path.join(_here, 'shaders', 'pbr-vert.glsl')) as f:
        vert_src = f.read()
    with open(os.path.join(_here, 'shaders', 'pbr-frag.glsl')) as f:
        frag_src = f.read()
    materials = gltf.get('materials', [])
    defines_to_materials = defaultdict(list)
    for i, material in enumerate(materials):
        material_defines = sorted([_GLSL_ATTR_TO_DEFINE[k]
                                   for k in chain(material.keys(), material.get('pbrMetallicRoughness', {}))
                                   if k in _GLSL_ATTR_TO_DEFINE or k in _GLSL_UNIF_TO_DEFINE])
        defines_to_materials[tuple(material_defines)].append(material)
    programs = []
    techniques = {}
    for i, (defines, materials) in enumerate(defines_to_materials.items()):
        v_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [vert_src])
        _logger.debug('compiling vertex shader...:\n%s\n', v_src)
        vert_shader_id = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vert_shader_id, v_src)
        gl.glCompileShader(vert_shader_id)
        if not gl.glGetShaderiv(vert_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile vertex shader %s:\n%s' % (i, gl.glGetShaderInfoLog(vert_shader_id).decode()))
        _logger.debug('..successfully compiled vertex shader %s', vert_shader_id)
        f_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [frag_src])
        _logger.debug('compiling fragment shader...:\n%s', f_src)
        frag_shader_id = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(frag_shader_id, f_src)
        gl.glCompileShader(frag_shader_id)
        if not gl.glGetShaderiv(frag_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile fragment shader %s:\n%s' % (i, gl.glGetShaderInfoLog(frag_shader_id).decode()))
        _logger.debug('...successfully compiled fragment shader %s', frag_shader_id)
        program_id = gl.glCreateProgram()
        gl.glAttachShader(program_id, vert_shader_id)
        gl.glAttachShader(program_id, frag_shader_id)
        gl.glLinkProgram(program_id)
        gl.glDetachShader(program_id, vert_shader_id)
        gl.glDetachShader(program_id, frag_shader_id)
        if not gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS):
            raise Exception('FAILED to link program %s' % i)
        attributes = copy(_REQUIRED_ATTRIBUTES)
        attributes += list(chain(_DEFINE_TO_GLTF_PBRMR_ATTRS[define]
                                 for define in defines))
        uniforms = copy(_REQUIRED_UNIFORMS)
        uniforms += list(chain(_DEFINE_TO_GLTF_PBRMR_UNIFS[define]
                               for define in defines))
        program = {
            'id': program_id,
            'attributes': attributes,
            'uniforms': uniforms,
            'attribute_locations': {attribute_name: gl.glGetAttribLocation(program_id, attribute_name)
                                    for attribute_name in attributes},
            'uniform_locations': {}
        }
        _logger.debug('linked program %s\n  attribute locations: %s\n  uniforms: %s', i, program['attribute_locations'], program['uniforms'])
        programs.append(program)
        parameters = {_GLSL_TO_GLTF_ATTR[k]: deepcopy(v)
                      for k, v in _PBRMR_PROGRAM_ATTRIBUTES.items() if k in attributes}
        parameters.update({_GLSL_TO_GLTF_UNIF[k]: deepcopy(v)
                           for k, v in _PBRMR_PROGRAM_UNIFORMS.items() if k in uniforms})
        technique = {
            'program': i,
            'attributes': {k: v for k, v in _GLSL_TO_GLTF_ATTR.items() if k in attributes},
            'parameters': parameters,
            'uniforms': {k: v for k, v in _GLSL_TO_GLTF_UNIF.items() if k in uniforms},
            #'states': {'enable': [2929, 2884]}
        }
        technique_name = 'pbrmr_technique%d' % i
        _logger.debug('created technique %s:\n%s',
                      technique_name, json.dumps(technique, indent=2, sort_keys=True))
        techniques[technique_name] = technique
        for material in materials:
            material['technique'] = technique_name
    gltf['programs'] = programs
    gltf['techniques'] = techniques
