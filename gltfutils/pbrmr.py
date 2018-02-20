import os.path
from itertools import chain, groupby
import json
import logging
_logger = logging.getLogger(__name__)

import OpenGL.GL as gl


_here = os.path.dirname(__file__)

_EGA_VERT_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'ega-vert.glsl')
_EGA_FRAG_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'ega-frag.glsl')

_VERT_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'pbr-vert.glsl')
_FRAG_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'pbr-frag.glsl')

_REQUIRED_GLSL_ATTRS = ['a_Position']
_GLSL_ATTR_TO_DEFINE = {'a_Normal' : 'HAS_NORMALS',
                        'a_Tangent': 'HAS_TANGENTS',
                        'a_UV'     : 'HAS_UV'}
_GLSL_ATTR_PARAMS = {
    'a_Position': {'type': gl.GL_FLOAT_VEC4, 'semantic': 'POSITION'},
    'a_Normal'  : {'type': gl.GL_FLOAT_VEC4, 'semantic': 'NORMAL'},
    'a_UV'      : {'type': gl.GL_FLOAT_VEC2, 'semantic': 'TEXCOORD_0'},
    'a_Tangent' : {'type': gl.GL_FLOAT_VEC4, 'semantic': 'TANGENT'}
}
_REQUIRED_GLSL_VERT_UNIFS =   ['u_ModelViewMatrix',
                               'u_ProjectionMatrix',
                               'u_ModelMatrix']
                               #u_NormalMatrix
                               #u_MVPMatrix
_REQUIRED_GLSL_FRAG_UNIFS =   ['u_BaseColorFactor',
                               'u_MetallicFactor',
                               'u_RoughnessFactor'];
_GLSL_UNIF_TO_DEFINE      =   {'u_DiffuseEnvSampler'       : 'USE_IBL',
                               'u_SpecularEnvSampler'      : 'USE_IBL',
                               #'u_brdfLUT'                 : 'USE_IBL',
                               'u_BaseColorSampler'        : 'HAS_BASECOLORMAP',
                               'u_NormalSampler'           : 'HAS_NORMALMAP',
                               'u_NormalScale'             : 'HAS_NORMALMAP',
                               'u_EmissiveSampler'         : 'HAS_EMISSIVEMAP',
                               'u_EmissiveFactor'          : 'HAS_EMISSIVEMAP',
                               'u_MetallicRoughnessSampler': 'HAS_METALROUGHNESSMAP',
                               'u_OcclusionSampler'        : 'HAS_OCCLUSIONMAP',
                               'u_OcclusionStrength'       : 'HAS_OCCLUSIONMAP'}
_REQUIRED_GLSL_UNIFS = _REQUIRED_GLSL_VERT_UNIFS + _REQUIRED_GLSL_FRAG_UNIFS;

_GLSL_UNIF_PARAMS = {
    # vertex shader uniforms:
    'u_LocalMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'LOCAL'},
    'u_ModelMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODEL'},
    'u_ViewMatrix':  {'type': gl.GL_FLOAT_MAT4,  'semantic': 'VIEW'},
    'u_ModelViewMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODELVIEW'},
    'u_ProjectionMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'PROJECTION'},
    'u_MVPMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODELVIEWPROJECTION'},
    'u_ModelInverseMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODELINVERSE'},
    'u_CameraMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'VIEWINVERSE'},
    'u_ModelViewInverseMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODELVIEWINVERSE'},
    'u_ProjectionInverseMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'PROJECTIONINVERSE'},
    'u_MVPInverseMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'MODELVIEWPROJECTIONINVERSE'},
    'u_ModelInverseTranspose': {'type': gl.GL_FLOAT_MAT3, 'semantic': 'MODELINVERSETRANSPOSE'},
    'u_NormalMatrix': {'type': gl.GL_FLOAT_MAT3, 'semantic': 'MODELVIEWINVERSETRANSPOSE'},
    'u_JointMatrix': {'type': gl.GL_FLOAT_MAT4, 'semantic': 'JOINTMATRIX'},
    # fragment shader uniforms:
    'u_Viewport': {'type': gl.GL_FLOAT_VEC4, 'semantic': 'VIEWPORT'},
    'u_BaseColorFactor': {'type': gl.GL_FLOAT_VEC4},#, 'value': [1.0, 1.0, 0.5, 0.0]},
    'u_EmissiveFactor': {'type': gl.GL_FLOAT_VEC3},# 'value': [1.0, 1.0, 1.0]},
    'u_MetallicFactor': {'type': gl.GL_FLOAT},# 'value': 0.0},
    'u_RoughnessFactor': {'type': gl.GL_FLOAT},# 'value': 0.8},
    'u_BaseColorSampler': {'type': gl.GL_SAMPLER_2D},
    'u_MetallicRoughnessSampler': {'type': gl.GL_SAMPLER_2D},
    'u_EmissiveSampler': {'type': gl.GL_SAMPLER_2D},
    'u_NormalSampler': {'type': gl.GL_SAMPLER_2D},
    'u_NormalScale': {'type': gl.GL_FLOAT},# 'value': 1.0},
    'u_DiffuseEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    'u_SpecularEnvSampler': {'type': gl.GL_SAMPLER_CUBE},
    'u_OcclusionSampler': {'type': gl.GL_SAMPLER_2D},
    'u_OcclusionStrength': {'type' : gl.GL_FLOAT},# 'value': 1.0},
    'u_Camera': {'type': gl.GL_FLOAT_VEC3},# 'value': [0.0, 0.0, 1.0]},
    'u_LightDirection': {'type': gl.GL_FLOAT_VEC3},
    'u_LightColor': {'type': gl.GL_FLOAT_VEC3}
    #'u_brdfLUT': {'type': gl.GL_SAMPLER_2D},
    #'u_ScaleDiffBaseMR': {'type' : gl.GL_FLOAT_VEC4, 'value': [0.0, 0.0, 0.0, 0.0]},
    #'u_ScaleFGDSpec': {'type' : gl.GL_FLOAT_VEC4, 'value': [0.0, 0.0, 0.0, 0.0]},
    #'u_ScaleIBLAmbient': {'type' : gl.GL_FLOAT_VEC4, 'value': [0.0, 0.0, 0.0, 0.0]}
}

_GLTF_ATTR_TO_DEFINE = {'NORMAL': 'HAS_NORMALS',
                        'TANGENT': 'HAS_TANGENTS',
                        'TEXCOORD_0': 'HAS_UV'}
_DEFINE_TO_GLSL_ATTR = {define: attr for attr, define in _GLSL_ATTR_TO_DEFINE.items()}
_DEFINE_TO_GLTF_ATTR = {define: attr for attr, define in _GLTF_ATTR_TO_DEFINE.items()}
_GLSL_ATTR_TO_GLTF_ATTR = {'a_Position': 'POSITION',
                           'a_Normal'  : 'NORMAL',
                           'a_Tangent' : 'TANGENT',
                           'a_UV'      : 'TEXCOORD_0'}
_GLSL_UNIF_TO_GLTF_UNIF = {
    # metallic-roughness uniforms:
    'u_BaseColorFactor'          : 'baseColorFactor',
    'u_BaseColorSampler'         : 'baseColorTexture',
    'u_MetallicFactor'           : 'metallicFactor',
    'u_RoughnessFactor'          : 'roughnessFactor',
    'u_MetallicRoughnessSampler' : 'metallicRoughnessTexture',
    'u_NormalSampler'            : 'normalTexture',
    'u_NormalScale'              : 'normalScale',
    'u_OcclusionSampler'         : 'occlusionTexture',
    'u_OcclusionStrength'        : 'occlusionStrength',
    # specular-glossiness uniforms:
    'u_DiffuseEnvSampler'        : 'diffuseTexture',
    'u_DiffuseFactor'            : 'diffuseFactor',
    'u_SpecularEnvSampler'       : 'specularGlossinessTexture',
    'u_SpecularFactor'           : 'specularFactor',
    'u_GlossinessFactor'         : 'glossinessFactor',
    'u_EmissiveSampler'          : 'emissiveTexture',
    'u_EmissiveFactor'           : 'emissiveFactor',
    # general fragment shader uniforms:
    'u_LightDirection'           : 'lightDirection',
    'u_LightColor'               : 'lightColor',
    'u_Camera'                   : 'cameraPosition',
    #'u_ScaleDiffBaseMR'          : 'scaleDiffBaseMR',
    # vertex shader uniforms (should map to semantic):
    'u_ModelMatrix'              : 'u_ModelMatrix',
    'u_ModelViewMatrix'          : 'u_ModelViewMatrix',
    'u_ViewMatrix'               : 'u_ViewMatrix',
    'u_ProjectionMatrix'         : 'u_ProjectionMatrix',
    'u_MVPMatrix'                : 'u_MVPMatrix',
    'u_NormalMatrix'             : 'u_NormalMatrix',
    'u_CameraMatrix'             : 'u_CameraMatrix',
    'u_LocalMatrix'              : 'u_LocalMatrix'
}
_REQUIRED_GLTF_UNIFS = [_GLSL_UNIF_TO_GLTF_UNIF[unif] for unif in _REQUIRED_GLSL_UNIFS]
_GLTF_UNIF_TO_DEFINE = {gltf_unif: _GLSL_UNIF_TO_DEFINE[glsl_unif]
                        for glsl_unif, gltf_unif in _GLSL_UNIF_TO_GLTF_UNIF.items()
                        if glsl_unif in _GLSL_UNIF_TO_DEFINE}
# _logger.debug('GLTF uniform to src #define:\n\n%s', '\n'.join('%s: %s' % (k, v)
#                                                               for k, v in _GLTF_UNIF_TO_DEFINE.items()))
_DEFINE_TO_GLSL_UNIFS = {define: [item[0] for item in grp]
                         for define, grp in groupby(sorted(_GLSL_UNIF_TO_DEFINE.items(),
                                                           key=lambda item: item[1]),
                                                    key=lambda item: item[1])}
_DEFINE_TO_GLTF_UNIFS = {define: [item[0] for item in grp]
                         for define, grp in groupby(sorted(_GLTF_UNIF_TO_DEFINE.items(),
                                                           key=lambda item: item[1]),
                                                    key=lambda item: item[1])}


def setup_pbrmr_programs(gltf):
    with open(_VERT_SHADER_SRC_PATH) as f:
        vert_src = f.read()
    with open(_FRAG_SHADER_SRC_PATH) as f:
        frag_src = f.read()

    # determine dependencies b/t GLTF 2.0 PBRMR material uniforms and GLSL #defines
    materials = gltf.get('materials', [])
    material_defines = []
    for i, material in enumerate(materials):
        material = material.copy()
        if 'pbrMetallicRoughness' in material:
            material.update(material.pop('pbrMetallicRoughness'))
        defines = sorted([_GLTF_UNIF_TO_DEFINE[k]
                          for k in material.keys() if k in _GLTF_UNIF_TO_DEFINE])
        material_defines.append(defines)
    # scan all primitive attributes to determine all of the unique GLTF techniques (i.e. OpenGL programs)
    # to be defined / compiled to render the scene,
    # define new GLTF 1.0 techniques and materials
    # and overwrite the existing GLTF 2.0 materials in the glsl dict with them:
    techniques = []
    technique_materials = []
    defines_to_technique = {}
    technique_and_material_to_technique_material = {}
    for i, mesh in enumerate(gltf.get('meshes', [])):
        for j, primitive in enumerate(mesh.get('primitives', [])):
            _logger.debug('mesh i, primitive j: %s', (j, primitive))
            if 'material' in primitive:
                i_material = primitive['material']
                material = gltf['materials'][i_material]
                _logger.debug('primitive["material"] = %s\nmaterial: %s', i_material, material)
                prim_defines = [] + material_defines[i_material]
                _logger.debug('material_defines[i_material] = %s', material_defines[i_material])
                attributes = primitive.get('attributes', {})
                _logger.debug('primitive["attributes"] = %s', attributes)
                for gltf_attr in attributes.keys():
                    if gltf_attr in _GLTF_ATTR_TO_DEFINE:
                        prim_defines.append(_GLTF_ATTR_TO_DEFINE[gltf_attr])
                prim_defines.sort()
                key = tuple(prim_defines)
                if key not in defines_to_technique:
                    attributes = {glsl_attr: _GLSL_ATTR_TO_GLTF_ATTR[glsl_attr]
                                  for glsl_attr in _REQUIRED_GLSL_ATTRS}
                    attributes.update({_DEFINE_TO_GLSL_ATTR[define]: _DEFINE_TO_GLTF_ATTR[define]
                                       for define in prim_defines if define in _DEFINE_TO_GLSL_ATTR})
                    uniforms = {glsl_unif: _GLSL_UNIF_TO_GLTF_UNIF[glsl_unif]
                                for glsl_unif in _REQUIRED_GLSL_UNIFS}
                    uniforms.update({glsl_unif: _GLSL_UNIF_TO_GLTF_UNIF[glsl_unif]
                                     for define in prim_defines for glsl_unif in _DEFINE_TO_GLSL_UNIFS.get(define, [])})
                    parameters = {gltf_attr: _GLSL_ATTR_PARAMS[glsl_attr]
                                  for glsl_attr, gltf_attr in attributes.items()}
                    parameters.update({gltf_unif: _GLSL_UNIF_PARAMS[glsl_unif]
                                       for glsl_unif, gltf_unif in uniforms.items()})
                    technique = {
                        "states": {"enable": [2929, 2884]},
                        "attributes": attributes,
                        "uniforms": uniforms,
                        "parameters": parameters
                    }
                    defines_to_technique[key] = len(techniques)
                    techniques.append(technique)
                    _logger.debug('''
defined GLTF 1.0 technique for PBRMR material configuration [ %s ]:

%s
''', ', '.join(prim_defines), json.dumps(technique, indent=2, sort_keys=True))
                i_technique = defines_to_technique[key]
                material_key = (i_technique, i_material)
                if material_key not in technique_and_material_to_technique_material:
                    values = material.copy()
                    if 'pbrMetallicRoughness' in values:
                        pbr = values.pop('pbrMetallicRoughness')
                        values.update(pbr)
                    for k, v in list(values.items()):
                        if k not in _REQUIRED_GLTF_UNIFS and k not in _GLTF_UNIF_TO_DEFINE:
                            values.pop(k)
                        if k.endswith('Texture'):
                            values[k] = v['index']
                    technique_material = {
                        'values': values,
                        'technique': defines_to_technique[key]
                    }
                    technique_and_material_to_technique_material[material_key] = len(technique_materials)
                    technique_materials.append(technique_material)
                    _logger.debug('''
defined GLTF 1.0 material:

%s
''', json.dumps(technique_material, indent=2, sort_keys=True))
                primitive['material'] = technique_and_material_to_technique_material[material_key]
    gltf['techniques'] = techniques
    gltf['materials'] = technique_materials
    _logger.debug('number of techniques defined: %d\nnumber of materials defined: %d',
                  len(techniques), len(technique_materials))

    gltf['programs'] = []
    for i_program, (defines, i_technique) in enumerate(defines_to_technique.items()):
        v_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [vert_src])
#         _logger.debug('''compiling vertex shader...:

# ================================================================================

# %s

# ================================================================================

# ''', '\n'.join(ln for ln in
#                (ln.strip() for ln in v_src.split('\n'))
#                if ln))
        vert_shader_id = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vert_shader_id, v_src)
        gl.glCompileShader(vert_shader_id)
        if not gl.glGetShaderiv(vert_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile vertex shader %s:\n%s' % (i, gl.glGetShaderInfoLog(vert_shader_id).decode()))
        #_logger.debug('..successfully compiled vertex shader %s', vert_shader_id)
        f_src = '\n'.join(['#version 130'] + ['#define %s 1' % define for define in defines] + [frag_src])
#         _logger.debug('''...successfully compiled vertex shader.

# compiling fragment shader...:

# ================================================================================

# %s

# ================================================================================

# ''', '\n'.join(ln for ln in
#                (ln.strip() for ln in f_src.split('\n'))
#                if ln))
        frag_shader_id = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(frag_shader_id, f_src)
        gl.glCompileShader(frag_shader_id)
        if not gl.glGetShaderiv(frag_shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile fragment shader %s:\n%s' % (i, gl.glGetShaderInfoLog(frag_shader_id).decode()))
#         _logger.debug('''...successfully compiled fragment shader %s

# linking program %d...:
#   attributes: %s
#   uniforms: %s

# ''', frag_shader_id, i_program, attributes, uniforms)
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
        #program['uniform_locations'] = {uniform_name: gl.glGetUniformLocation(program['id'], uniform_name)
        #                                for uniform_name in program['uniforms']}
        _logger.debug('attribute locations: %s\nuniform locations: %s', program['attribute_locations'], program['uniform_locations'])
        gltf['techniques'][i_technique]['program'] = i_program
        gltf['programs'].append(program)
