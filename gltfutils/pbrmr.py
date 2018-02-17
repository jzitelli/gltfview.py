import os.path
from copy import copy, deepcopy
from itertools import chain, groupby
import json
import logging
_logger = logging.getLogger(__name__)

import OpenGL.GL as gl

_here = os.path.dirname(__file__)


_REQUIRED_GLSL_ATTRS = ['a_Position']
_GLSL_ATTR_TO_DEFINE = {'a_Normal' : 'HAS_NORMALS',
                        'a_Tangent': 'HAS_TANGENTS',
                        'a_UV'     : 'HAS_UV'}
_GLSL_ATTR_PARAMS = {
    'a_Position': {'type': gl.GL_FLOAT_VEC3,
                   'semantic': 'POSITION'},
    'a_Normal'  : {'type': gl.GL_FLOAT_VEC4,
                   'semantic': 'NORMAL'},
    'a_UV'      : {'type': gl.GL_FLOAT_VEC2,
                   'semantic': 'TEXCOORD_0'},
    'a_Tangent' : {'type': gl.GL_FLOAT_VEC4,
                   'semantic': 'TANGENT'}
}


_REQUIRED_GLSL_UNIFS =   ['u_MVPMatrix',
                          'u_ModelMatrix',
                          'u_ProjectionMatrix',
                          'u_BaseColorFactor']
_GLSL_UNIF_TO_DEFINE =   {'u_DiffuseEnvSampler'       : 'USE_IBL',
                          'u_SpecularEnvSampler'      : 'USE_IBL',
                          #'u_brdfLUT'                 : 'USE_IBL',
                          'u_BaseColorSampler'        : 'HAS_COLORMAP',
                          'u_NormalSampler'           : 'HAS_NORMALMAP',
                          'u_NormalScale'             : 'HAS_NORMALMAP',
                          'u_EmissiveSampler'         : 'HAS_EMISSIVEMAP',
                          'u_EmissiveFactor'          : 'HAS_EMISSIVEMAP',
                          'u_MetallicRoughnessSampler': 'HAS_METALROUGHNESSMAP',
                          'u_OcclusionSampler'        : 'HAS_OCCLUSIONMAP',
                          'u_OcclusionStrength'       : 'HAS_OCCLUSIONMAP'}
_GLSL_UNIF_PARAMS = {
    'u_ModelMatrix': {'type'    : gl.GL_FLOAT_MAT4,
                      'semantic': 'MODELVIEW'},
    'u_ProjectionMatrix': {'type': gl.GL_FLOAT_MAT4,
                           'semantic': 'PROJECTION'},
    'u_MVPMatrix': {'type'    : gl.GL_FLOAT_MAT4,
                    'semantic': 'MODELVIEWPROJECTION'},
    'u_Camera': {'type' : gl.GL_FLOAT_VEC3,
                 'value': [0.0, 0.0, 1.0],
                 'semantic': 'CAMERA_POSITION'}, # ??
    'u_LightDirection': {'type' : gl.GL_FLOAT_VEC3,
                         'value': [0.1, 1.0, 0.5]},
    'u_LightColor': {'type' : gl.GL_FLOAT_VEC3,
                     'value': [1.0, 1.0, 0.8]},
    'u_DiffuseEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    'u_SpecularEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    #'u_brdfLUT': {'type': gl.GL_SAMPLER_2D},
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
    # 'u_MetallicRoughnessValues': {'type' : gl.GL_FLOAT_VEC2,
    #                               'value': [0.0, 0.0]},
    'u_MetallicFactor': {'type': gl.GL_FLOAT,
                         'value': 0.0},
    'u_RoughnessFactor': {'type': gl.GL_FLOAT,
                          'value': 0.0},
    'u_BaseColorFactor': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [1.0, 1.0, 0.5, 0.0]},
    'u_ScaleDiffBaseMR': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [0.0, 0.0, 0.0, 0.0]},
    'u_ScaleFGDSpec': {'type' : gl.GL_FLOAT_VEC4,
                       'value': [0.0, 0.0, 0.0, 0.0]},
    'u_ScaleIBLAmbient': {'type' : gl.GL_FLOAT_VEC4,
                          'value': [0.0, 0.0, 0.0, 0.0]}
}

# _GLTF_ATTR_TO_DEFINE = {gltf_attr: _GLSL_ATTR_TO_DEFINE[glsl_attr]
#                         for glsl_attr, gltf_attr in _GLSL_ATTR_TO_GLTF_ATTR.items()}
# _DEFINE_TO_GLTF_ATTR = {v: k for k, v in _GLTF_ATTR_TO_DEFINE.items()}
_GLTF_ATTR_TO_DEFINE = {'NORMAL': 'HAS_NORMALS',
                        'TANGENT': 'HAS_TANGENTS',
                        'TEXCOORD_0': 'HAS_UV'}
_DEFINE_TO_GLSL_ATTR = {define: attr for attr, define in _GLSL_ATTR_TO_DEFINE.items()}
_DEFINE_TO_GLTF_ATTR = {define: attr for attr, define in _GLTF_ATTR_TO_DEFINE.items()}


_GLSL_ATTR_TO_GLTF_ATTR = {'a_Position': 'POSITION',
                           'a_Normal'  : 'NORMAL',
                           'a_UV'      : 'TEXCOORD_0'}
_GLSL_UNIF_TO_GLTF_UNIF = {
    # metallic-roughness uniforms:
    'u_BaseColorFactor'          : 'baseColorFactor',
    'u_BaseColorSampler'         : 'baseColorTexture',
    'u_MetallicFactor'           : 'metallicFactor',
    'u_RoughnessFactor'          : 'roughnessFactor',
    'u_MetallicRoughnessSampler' : 'metallicRoughnessTexture',
    # specular-glossiness uniforms:
    'u_NormalSampler'            : 'normalTexture',
    'u_NormalScale'              : 'normalTexture',
    'u_OcclusionSampler'         : 'occlusionTexture',
    'u_OcclusionStrength'        : 'occlusionTexture',
    'u_EmissiveSampler'          : 'emissiveTexture',
    'u_EmissiveFactor'           : 'emissiveTexture',
    # general material uniforms:
    'u_DiffuseEnvSampler'        : 'diffuseTexture',
    'u_DiffuseFactor'            : 'diffuseFactor',
    'u_SpecularEnvSampler'       : 'specularGlossinessTexture',
    'u_SpecularFactor'           : 'specularFactor',
    'u_GlossinessFactor'         : 'glossinessFactor',
    # other uniforms:
    'u_LightDirection'           : 'lightDirection',
    'u_LightColor'               : 'lightColor',
    'u_Camera'                   : 'cameraPosition',
    #'u_ScaleDiffBaseMR'          : 'scaleDiffBaseMR',
    # vertex shader uniforms:
    #'u_ModelMatrix'              : 'u_ModelMatrix',
    #'u_ProjectionMatrix'         : 'u_ProjectionMatrix',
}


_GLTF_UNIF_TO_DEFINE = {gltf_unif: _GLSL_UNIF_TO_DEFINE[glsl_unif]
                        for glsl_unif, gltf_unif in _GLSL_UNIF_TO_GLTF_UNIF.items()
                        if glsl_unif in _GLSL_UNIF_TO_DEFINE}
_DEFINE_TO_GLSL_UNIFS = {define: [item[0] for item in grp]
                         for define, grp in groupby(sorted(_GLSL_UNIF_TO_DEFINE.items(),
                                                           key=lambda item: item[1]),
                                                    key=lambda item: item[1])}
_DEFINE_TO_GLTF_UNIFS = {define: [item[0] for item in grp]
                         for define, grp in groupby(sorted(_GLTF_UNIF_TO_DEFINE.items(),
                                                           key=lambda item: item[1]),
                                                    key=lambda item: item[1])}
# _DEFINE_TO_GLTF_UNIFS = {define: [_GLSL_UNIF_TO_GLTF_UNIF[glsl_unif] for glsl_unif in glsl_unifs]
#                          for define, glsl_unifs in _DEFINE_TO_GLSL_UNIFS.items()}


def setup_pbrmr_programs(gltf):
    with open(os.path.join(_here, 'shaders', 'pbr-vert.glsl')) as f:
        vert_src = f.read()
    with open(os.path.join(_here, 'shaders', 'pbr-frag.glsl')) as f:
        frag_src = f.read()

    # determine dependencies b/t GLTF 2.0 PBRMR material uniforms and GLSL #defines
    materials = gltf.get('materials', [])
    material_defines = []
    for i, material in enumerate(materials):
        defines = sorted([_GLSL_UNIF_TO_DEFINE[k]
                          for k in chain(material.keys(), material.get('pbrMetallicRoughness', {}).keys())
                          if k in _GLSL_UNIF_TO_DEFINE])
        material_defines.append(defines)
    _logger.debug('material_defines = %s', material_defines)

    # scan all primitive attributes to determine all of the unique GLTF techniques (i.e. OpenGL programs)
    # to be defined / compiled to render the scene,
    # define new GLTF 1.0 techniques and materials
    # and overwrite the existing GLTF 2.0 materials in the glsl dict with them:
    techniques = []
    technique_materials = []
    defines_to_technique = {}
    technique_and_material_to_technique_material = {}
    primitive_to_technique = {}
    for i, mesh in enumerate(gltf.get('meshes', [])):
        for j, primitive in enumerate(mesh.get('primitives', [])):
            _logger.debug('mesh i, primitive j: %s', (j, primitive))
            if 'material' in primitive:
                i_material = primitive['material']
                material = gltf['materials'][i_material]
                _logger.debug('primitive["material"] = %s\nmaterial: %s', i_material, material)
                prim_defines = [] + material_defines[i_material]
                attributes = primitive.get('attributes', {})
                _logger.debug('primitive["attributes"] = %s', attributes)
                if 'NORMAL' in attributes:
                    prim_defines.append('HAS_NORMALS')
                if 'TANGENT' in attributes:
                    prim_defines.append('HAS_TANGENTS')
                if 'TEXCOORD_0' in attributes:
                    prim_defines.append('HAS_UV')
                prim_defines.sort()
                key = tuple(prim_defines)
                if key not in defines_to_technique:
                    technique = {
                        "states": {"enable": [2929, 2884]},
                        "attributes": {_DEFINE_TO_GLSL_ATTR[define]: _DEFINE_TO_GLTF_ATTR[define]
                                       for define in prim_defines},
                        "uniforms": {glsl_unif: _GLSL_UNIF_TO_GLTF_UNIF[glsl_unif]
                                     for glsl_unif in chain(_DEFINE_TO_GLSL_UNIFS[define]
                                                            for define in prim_defines
                                                            if define in _DEFINE_TO_GLSL_UNIFS)}
                    }
                    technique['parameters'] = {gltf_attr: _GLSL_ATTR_PARAMS[glsl_attr]
                                               for glsl_attr, gltf_attr in technique['attributes'].items()}
                    technique['parameters'].update({gltf_unif: _GLSL_UNIF_PARAMS[glsl_unif]
                                                    for glsl_unif, gltf_unif in technique['uniforms'].items()})
                    defines_to_technique[key] = len(techniques)
                    techniques.append(technique)
                    _logger.debug('defined new GLTF 1.0 technique for defines %s: %s', prim_defines, json.dumps(technique, indent=1, sort_keys=True))
                i_technique = defines_to_technique[key]
                material_key = (i_technique, i_material)
                if material_key not in technique_and_material_to_technique_material:
                    values = material.get('pbrMetallicRoughness', {}).copy()
                    values.update(material)
                    for k, v in list(values.items()):
                        if k not in _GLTF_UNIF_TO_DEFINE:
                            values.pop(k)
                        if k.endswith('Texture'):
                            values[k] = v['index']
                    technique_material = {
                        'values': values,
                        'technique': defines_to_technique[key]
                    }
                    technique_and_material_to_technique_material[material_key] = len(technique_materials)
                    technique_materials.append(technique_material)
                    _logger.debug('defined GLTF 1.0 material for GLTF 2.0 material configuration (#defines: %s):\n%s',
                                  ', '.join(prim_defines), json.dumps(technique_material, indent=1, sort_keys=True))
                primitive['material'] = technique_and_material_to_technique_material[material_key]
    gltf['techniques'] = techniques
    gltf['materials'] = technique_materials
    _logger.debug('number of techniques defined: %d\nnumber of materials defined: %d',
                  len(techniques), len(technique_materials))

    raise Exception('asdf')

    for i_program, (defines, i_technique) in enumerate(defines_to_technique.items()):
        _logger.debug('defines = %s', defines)
        v_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [vert_src])
        #_logger.debug('compiling vertex shader...:\n%s\n', v_src)
        vert_shader_id = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vert_shader_id, v_src)
        gl.glCompileShader(vert_shader_id)
        if not gl.glGetShaderiv(vert_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile vertex shader %s:\n%s' % (i, gl.glGetShaderInfoLog(vert_shader_id).decode()))
        #_logger.debug('..successfully compiled vertex shader %s', vert_shader_id)
        f_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [frag_src])
        _logger.debug('''...successfully compiled vertex shader.

compiling fragment shader...:

================================================================================

%s

================================================================================

''', '\n'.join(ln for ln in
               (ln.strip() for ln in f_src.split('\n'))
               if ln))
        frag_shader_id = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(frag_shader_id, f_src)
        gl.glCompileShader(frag_shader_id)
        if not gl.glGetShaderiv(frag_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile fragment shader %s:\n%s' % (i, gl.glGetShaderInfoLog(frag_shader_id).decode()))
        program_id = gl.glCreateProgram()
        attributes = _REQUIRED_GLSL_ATTRS + [_DEFINE_TO_GLSL_ATTR[define]
                                             for define in defines
                                             if define in _DEFINE_TO_GLSL_ATTR]
        uniforms = _REQUIRED_GLSL_UNIFS + list(chain.from_iterable(_DEFINE_TO_GLSL_UNIFS[define]
                                                                   for define in defines
                                                                   if define in _DEFINE_TO_GLSL_UNIFS))
        program = {
            'id': program_id,
            'attributes': attributes,
            'uniforms': uniforms,
            'uniform_locations': {}
        }
        _logger.debug('''...successfully compiled fragment shader %s

now linking program %d...:
  attributes: %s
  uniforms: %s

''', frag_shader_id, i_program, attributes, uniforms)
        gl.glAttachShader(program_id, vert_shader_id)
        gl.glAttachShader(program_id, frag_shader_id)
        gl.glLinkProgram(program_id)
        gl.glDetachShader(program_id, vert_shader_id)
        gl.glDetachShader(program_id, frag_shader_id)
        if not gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS):
            raise Exception('FAILED to link program %s:\n%s' % (i_program,
                                                                gl.glGetProgramInfoLog(program_id).decode()))
        _logger.debug('...successfully linked program %s', i_program)
        program['attribute_locations'] = {attribute_name: gl.glGetAttribLocation(program_id,
                                                                                 attribute_name)
                                          for attribute_name in program['attributes']}
        _logger.debug('attribute locations: %s', program['attribute_locations'])
        gltf['programs'].append(program)


def _define_techniques_for_meshes(meshes, materials):
    pass
