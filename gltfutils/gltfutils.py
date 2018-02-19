import os.path
import base64
from ctypes import c_void_p
try: # python 3.3 or later
    from types import MappingProxyType
except ImportError as err:
    MappingProxyType = dict
import re
import logging

import numpy as np
import OpenGL.GL as gl
import PIL.Image as Image


_here = os.path.dirname(__file__)
_logger = logging.getLogger(__name__)
from gltfutils.gl_rendering import set_matrix_from_quaternion
import gltfutils.pbrmr as pbrmr


CHECK_GL_ERRORS = False
GLTF_BUFFERVIEW_TYPE_SIZES = MappingProxyType({
    'SCALAR': 1,
    'VEC2': 2,
    'VEC3': 3,
    'VEC4': 4,
    'MAT2': 4,
    'MAT3': 9,
    'MAT4': 16
})
DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE = {
    gl.GL_INT: 0,
    gl.GL_INT_VEC2: (0, 0),
    gl.GL_FLOAT: 1.0,
    gl.GL_FLOAT_VEC2: (0.0, 0.0),
    gl.GL_FLOAT_VEC3: (0.0, 0.0, 0.0),
    gl.GL_FLOAT_VEC4: (0.0, 0.0, 0.0, 1.0),
    gl.GL_FLOAT_MAT2: np.eye(2, dtype=np.float32),
    gl.GL_FLOAT_MAT3: np.eye(3, dtype=np.float32),
    gl.GL_FLOAT_MAT4: np.eye(4, dtype=np.float32)
}
for k, v in list(DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE.items()):
    DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE[int(k)] = v
_ATTRIBUTE_DECL_RE = re.compile(r"attribute\s+(?P<type_spec>\w+)\s+(?P<attribute_name>\w+)\s*;")
_UNIFORM_DECL_RE =   re.compile(r"uniform\s+(?P<type_spec>\w+)\s+(?P<uniform_name>\w+)\s*(=\s*(?P<initialization>.*)\s*;|;)")


def setup_shaders(gltf, uri_path):
    """Loads and compiles all shaders defined or referenced in the given gltf"""
    shader_ids = {}
    for shader_name, shader in gltf['shaders'].items():
        uri = shader['uri']
        if uri.startswith('data:text/plain;base64,'):
            shader_str = base64.urlsafe_b64decode(uri.split(',')[1]).decode()
            _logger.debug('decoded shader "%s":\n%s', shader_name, shader_str)
        else:
            filename = os.path.join(uri_path, shader['uri'])
            shader_str = open(filename).read()
            _logger.debug('loaded shader "%s" (from %s):\n%s', shader_name, filename, shader_str)
        shader_id = gl.glCreateShader(shader['type'])
        gl.glShaderSource(shader_id, shader_str)
        gl.glCompileShader(shader_id)
        if not gl.glGetShaderiv(shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile shader "%s":\n%s' % (shader_name, gl.glGetShaderInfoLog(shader_id).decode()))
        _logger.debug('compiled shader "%s"', shader_name)
        shader_ids[shader_name] = shader_id
    return shader_ids


def setup_programs(gltf, shader_ids):
    for program_name, program in gltf['programs'].items():
        program_id = gl.glCreateProgram()
        gl.glAttachShader(program_id, shader_ids[program['vertexShader']])
        gl.glAttachShader(program_id, shader_ids[program['fragmentShader']])
        gl.glLinkProgram(program_id)
        gl.glDetachShader(program_id, shader_ids[program['vertexShader']])
        gl.glDetachShader(program_id, shader_ids[program['fragmentShader']])
        if not gl.glGetProgramiv(program_id, gl.GL_LINK_STATUS):
            raise Exception('failed to link program "%s"' % program_name)
        program['id'] = program_id
        program['attribute_locations'] = {attribute_name: gl.glGetAttribLocation(program_id, attribute_name)
                                          for attribute_name in program['attributes']}
        program['uniform_locations'] = {}
        _logger.debug('linked program "%s"\n  attribute locations: %s', program_name, program['attribute_locations'])


def setup_programs_v2(gltf):
    pbrmr.setup_pbrmr_programs(gltf)


def load_images(gltf, uri_path):
    # TODO: support data URIs
    pil_images = {}
    if 'images' in gltf and isinstance(gltf['images'], list):
        return load_images_v2(gltf, uri_path)
    for image_name, image in gltf.get('images', {}).items():
        filename = os.path.join(uri_path, image['uri'])
        pil_image = Image.open(filename)
        pil_images[filename] = pil_image
        _logger.debug('loaded image "%s" from "%s"', image_name, filename)
    return pil_images


def load_images_v2(gltf, uri_path):
    pil_images = {}
    for i, image in enumerate(gltf.get('images', [])):
        filename = os.path.join(uri_path, image['uri'])
        pil_image = Image.open(filename)
        pil_images[filename] = pil_image
        _logger.debug('loaded image %s from "%s"',
                      i if 'name' not in image else '%d ("%s")' % (i, image['name']),
                      filename)
    return pil_images


def setup_textures(gltf, uri_path):
    pil_images = load_images(gltf, uri_path)
    texture_id_0 = gl.glGenTextures(len(gltf.get('textures', {})))
    for i, (texture_name, texture) in enumerate(gltf.get('textures', {}).items()):
        sampler = gltf['samplers'][texture['sampler']]
        image = gltf['images'][texture['source']]
        filename = os.path.join(uri_path, image['uri'])
        pil_image = pil_images[filename]
        #texture_id = gl.glGenTextures(1)
        texture_id = texture_id_0 + i
        if 'target' not in texture:
            texture['target'] = gl.GL_TEXTURE_2D # GLTF 1.0 DEFAULT
        gl.glBindTexture(texture['target'], texture_id)
        sampler_id = gl.glGenSamplers(1)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, sampler.get('minFilter', 9986))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, sampler.get('magFilter', 9729))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, sampler.get('wrapS', 10497))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, sampler.get('wrapT', 10497))
        sampler['id'] = sampler_id
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        if 'type' not in texture:
            texture['type'] = gl.GL_UNSIGNED_BYTE
        if texture['type'] != gl.GL_UNSIGNED_BYTE:
            _logger.warn('you are trying to use a texture with property "type" set to %s, not GL_UNSIGNED_BYTE (%d), is it going to work?!?!', texture['type'], int(gl.GL_UNSIGNED_BYTE))
        gl.glTexImage2D(texture['target'], 0,
                        texture['internalFormat'],
                        pil_image.width, pil_image.height, 0,
                        gl.GL_RGB, #texture['format'], # TODO: INVESTIGATE
                        texture['type'],
                        np.array(list(pil_image.getdata()), dtype=(np.ubyte if texture['type'] == gl.GL_UNSIGNED_BYTE else np.ushort)))
        gl.glGenerateMipmap(texture['target'])
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create texture "%s"' % texture_name)
        texture['id'] = texture_id
        _logger.debug('created texture "%s"', texture_name)


def setup_textures_v2(gltf, uri_path):
    pil_images = load_images(gltf, uri_path)
    textures = gltf.get('textures', [])
    if textures:
        texture_id_0 = gl.glGenTextures(len(textures))
    for i, texture in enumerate(textures):
        sampler = gltf['samplers'][texture['sampler']]
        image = gltf['images'][texture['source']]
        filename = os.path.join(uri_path, image['uri'])
        pil_image = pil_images[filename]
        texture_id = texture_id_0 + i
        if 'target' not in texture:
            texture['target'] = gl.GL_TEXTURE_2D # GLTF 1.0 DEFAULT
        gl.glBindTexture(texture['target'], texture_id)
        sampler_id = gl.glGenSamplers(1)
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, sampler.get('minFilter', 9986))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, sampler.get('magFilter', 9729))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, sampler.get('wrapS', 10497))
        gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, sampler.get('wrapT', 10497))
        sampler['id'] = sampler_id
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        if 'type' not in texture:
            texture['type'] = gl.GL_UNSIGNED_BYTE
        if texture['type'] != gl.GL_UNSIGNED_BYTE:
            _logger.warn('you are trying to use a texture with property "type" set to %s, not GL_UNSIGNED_BYTE (%d), is it going to work?!?!', texture['type'], int(gl.GL_UNSIGNED_BYTE))
        gl.glTexImage2D(texture['target'], 0,
                        gl.GL_RGBA,
                        pil_image.width, pil_image.height, 0,
                        gl.GL_RGB, #texture['format'], # TODO: INVESTIGATE
                        texture['type'],
                        np.array(list(pil_image.getdata()), dtype=(np.ubyte if texture['type'] == gl.GL_UNSIGNED_BYTE else np.ushort)))
        gl.glGenerateMipmap(texture['target'])
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create texture %d' % i)
        texture['id'] = texture_id
        _logger.debug('created texture %s', i if 'name' not in texture else ('%d ("%s")' % (i, texture['name'])))


def setup_buffers(gltf, uri_path):
    buffers = gltf['buffers']
    data_buffers = {}
    for buffer_name, buffer in buffers.items():
        uri = buffer['uri']
        if uri.startswith('data:application/octet-stream;base64,'):
            data_buffers[buffer_name] = base64.b64decode(uri.split(',')[1])
        else:
            filename = os.path.join(uri_path, buffer['uri'])
            if buffer['type'] == 'arraybuffer':
                data_buffers[buffer_name] = open(filename, 'rb').read()
            elif buffer['type'] == 'text':
                raise Exception('TODO')
                #data_buffers[buffer_name] = open(filename, 'r').read()
            _logger.debug('loaded buffer "%s" (from %s)', buffer_name, filename)
    for bufferView_name, bufferView in gltf['bufferViews'].items():
        buffer_id = gl.glGenBuffers(1)
        byteOffset = bufferView['byteOffset']
        gl.glBindBuffer(bufferView['target'], buffer_id)
        gl.glBufferData(bufferView['target'], bufferView['byteLength'],
                        data_buffers[bufferView['buffer']][byteOffset:], gl.GL_STATIC_DRAW)
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create buffer "%s"' % bufferView_name)
        bufferView['id'] = buffer_id
        gl.glBindBuffer(bufferView['target'], 0)
        _logger.debug('created buffer "%s"' % bufferView_name)


def setup_buffers_v2(gltf, uri_path):
    buffers = gltf.get('buffers', [])
    data_buffers = []
    for i, buffer in enumerate(buffers):
        uri = buffer['uri']
        if uri.startswith('data:application/octet-stream;base64,'):
            data_buffers.append(base64.b64decode(uri.split(',')[1]))
        else:
            filename = os.path.join(uri_path, buffer['uri'])
            data_buffers.append(open(filename, 'rb').read())
            _logger.debug('loaded buffer %s from "%s"',
                          i if 'name' not in buffer else '%d ("%s")' % (i, buffer['name']),
                          filename)
    for i, bufferView in enumerate(gltf.get('bufferViews', [])):
        buffer_id = gl.glGenBuffers(1)
        byteOffset = bufferView['byteOffset']
        gl.glBindBuffer(bufferView['target'], buffer_id)
        gl.glBufferData(bufferView['target'], bufferView['byteLength'],
                        data_buffers[bufferView['buffer']][byteOffset:], gl.GL_STATIC_DRAW)
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create bufferView %s' % i)
        bufferView['id'] = buffer_id
        gl.glBindBuffer(bufferView['target'], 0)
        _logger.debug('created bufferView %s', i if 'name' not in bufferView else '%d ("%s")' % (i, bufferView['name']))


def set_technique_state(technique_name, gltf):
    if set_technique_state.current_technique is not None and set_technique_state.current_technique == technique_name:
        return
    set_technique_state.current_technique = technique_name
    technique = gltf['techniques'][technique_name]
    program = gltf['programs'][technique['program']]
    gl.glUseProgram(program['id'])
    enabled_states = technique.get('states', {}).get('enable', [])
    for state, is_enabled in list(set_technique_state.states.items()):
        if state in enabled_states:
            if not is_enabled:
                gl.glEnable(state)
                set_technique_state.states[state] = True
        elif is_enabled:
            gl.glDisable(state)
            set_technique_state.states[state] = False
    for state in [state for state in enabled_states
                  if state not in set_technique_state.states]:
        gl.glEnable(state)
        set_technique_state.states[state] = True
set_technique_state.current_technique = None
set_technique_state.states = {}


def set_material_state(material_name, gltf):
    if set_material_state.current_material == material_name:
        return
    set_material_state.current_material = material_name
    material = gltf['materials'][material_name]
    set_technique_state(material['technique'], gltf)
    technique = gltf['techniques'][material['technique']]
    program = gltf['programs'][technique['program']]
    textures = gltf.get('textures', {})
    samplers = gltf.get('samplers', {})
    material_values = material.get('values', {})
    for uniform_name, parameter_name in technique['uniforms'].items():
        parameter = technique['parameters'][parameter_name]
        if 'semantic' in parameter:
            continue
        value = material_values.get(parameter_name, parameter.get('value', DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE.get(parameter['type'])))
        if value is None:
            raise Exception('could not determine a value to use for material "%s" parameter "%s" (type %s) uniform "%s"' % (
                material_name, parameter_name, parameter['type'], uniform_name))
        if isinstance(value, (tuple, list)):
            value = np.array(value, dtype=np.float32)
        if uniform_name in program['uniform_locations']:
            location = program['uniform_locations'][uniform_name]
        else:
            location = gl.glGetUniformLocation(program['id'], uniform_name)
            program['uniform_locations'][uniform_name] = location
        if parameter['type'] == gl.GL_SAMPLER_2D:
            texture = textures[value]
            gl.glActiveTexture(gl.GL_TEXTURE0+set_material_state.n_tex)
            gl.glBindTexture(texture['target'], texture['id'])
            gl.glBindSampler(gl.GL_TEXTURE0+set_material_state.n_tex,
                             samplers[texture['sampler']]['id'])
            gl.glUniform1i(location, set_material_state.n_tex)
            set_material_state.n_tex += 1
        elif parameter['type'] == gl.GL_INT:
            gl.glUniform1i(location, value)
        elif parameter['type'] == gl.GL_FLOAT:
            gl.glUniform1f(location, value)
        elif parameter['type'] == gl.GL_FLOAT_VEC2:
            gl.glUniform2f(location, *value)
        elif parameter['type'] == gl.GL_FLOAT_VEC3:
            gl.glUniform3f(location, *value)
        elif parameter['type'] == gl.GL_FLOAT_VEC4:
            gl.glUniform4f(location, *value)
        elif parameter['type'] == gl.GL_FLOAT_MAT2:
            gl.glUniformMatrix2fv(location, 1, False, value)
        elif parameter['type'] == gl.GL_FLOAT_MAT3:
            gl.glUniformMatrix3fv(location, 1, False, value)
        elif parameter['type'] == gl.GL_FLOAT_MAT4:
            gl.glUniformMatrix4fv(location, 1, False, value)
        else:
            raise Exception('unhandled parameter type: %s' % parameter['type'])
    if CHECK_GL_ERRORS:
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('error setting material state')
set_material_state.current_material = None
set_material_state.n_tex = 0


def set_draw_state(primitive, gltf,
                   projection_matrix=None,
                   view_matrix=None,
                   camera_matrix=None,
                   model_matrix=None,
                   modelview_matrix=None,
                   normal_matrix=None,
                   mvp_matrix=None,
                   local_matrix=None):
    set_material_state(primitive['material'], gltf)
    material = gltf['materials'][primitive['material']]
    technique = gltf['techniques'][material['technique']]
    program = gltf['programs'][technique['program']]
    accessors = gltf['accessors']
    bufferViews = gltf['bufferViews']
    accessor_names = primitive['attributes']
    for uniform_name, parameter_name in technique['uniforms'].items():
        parameter = technique['parameters'][parameter_name]
        if 'semantic' in parameter:
            semantic = parameter['semantic']
            location = gl.glGetUniformLocation(program['id'], uniform_name)
            if semantic == 'MODELVIEW':
                if 'node' in parameter and view_matrix is not None:
                    world_matrix = gltf['nodes'][parameter['node']]['world_matrix']
                    world_matrix.dot(view_matrix, out=set_draw_state.modelview_matrix)
                    gl.glUniformMatrix4fv(location, 1, False, set_draw_state.modelview_matrix)
                elif modelview_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, modelview_matrix)
            elif semantic == 'PROJECTION':
                if projection_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, projection_matrix)
            elif semantic == 'MODELVIEWPROJECTION':
                if mvp_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, True, mvp_matrix)
            elif semantic == 'MODEL':
                if model_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, model_matrix)
            elif semantic == 'LOCAL':
                if local_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, local_matrix)
            elif semantic == 'VIEW':
                if view_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, view_matrix)
            elif semantic == 'VIEWINVERSE':
                if camera_matrix is None and view_matrix is not None:
                    camera_matrix = np.linalg.inv(view_matrix)
                if camera_matrix is not None:
                    gl.glUniformMatrix4fv(location, 1, False, camera_matrix)
            elif semantic == 'MODELVIEWINVERSETRANSPOSE':
                if normal_matrix is not None:
                    gl.glUniformMatrix3fv(location, 1, True, normal_matrix)
            else:
                raise Exception('unhandled semantic for uniform "%s": %s' % (uniform_name, parameter['semantic']))
    if 'vao' not in primitive:
        enabled_locations = []
        buffer_id = None
        vao = gl.glGenVertexArrays(1)
        gl.glBindVertexArray(vao)
        for attribute_name, parameter_name in technique['attributes'].items():
            parameter = technique['parameters'][parameter_name]
            if 'semantic' in parameter:
                semantic = parameter['semantic']
                if semantic in accessor_names:
                    accessor = accessors[accessor_names[semantic]]
                    bufferView = bufferViews[accessor['bufferView']]
                    location = program['attribute_locations'][attribute_name]
                    gl.glEnableVertexAttribArray(location)
                    enabled_locations.append(location)
                    if buffer_id != bufferView['id']:
                        buffer_id = bufferView['id']
                        gl.glBindBuffer(bufferView['target'], buffer_id)
                    gl.glVertexAttribPointer(location, GLTF_BUFFERVIEW_TYPE_SIZES[accessor['type']],
                                             accessor['componentType'], False,
                                             accessor.get('byteStride', # GLTF 1.0
                                                          bufferView.get('byteStride')), # GLTF 2.0
                                             c_void_p(accessor.get('byteOffset', 0)))
                else:
                    raise Exception('expected a semantic property for attribute "%s", parameter "%s"' % (attribute_name, parameter_name))
        primitive['vao'] = vao
        gl.glBindVertexArray(0)
        for location in enabled_locations:
            gl.glDisableVertexAttribArray(location)
    gl.glBindVertexArray(primitive['vao'])
    if CHECK_GL_ERRORS:
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('error setting draw state')
set_draw_state.modelview_matrix = np.empty((4,4), dtype=np.float32)
set_draw_state.mvp_matrix = np.empty((4,4), dtype=np.float32)
set_draw_state.vaos = {}


def draw_primitive(primitive, gltf,
                   projection_matrix=None,
                   view_matrix=None,
                   camera_matrix=None,
                   model_matrix=None,
                   modelview_matrix=None,
                   normal_matrix=None,
                   mvp_matrix=None,
                   local_matrix=None):
    set_draw_state(primitive, gltf,
                   projection_matrix=projection_matrix,
                   view_matrix=view_matrix,
                   camera_matrix=camera_matrix,
                   model_matrix=model_matrix,
                   modelview_matrix=modelview_matrix,
                   normal_matrix=normal_matrix,
                   mvp_matrix=mvp_matrix,
                   local_matrix=local_matrix)
    index_accessor = gltf['accessors'][primitive['indices']]
    index_bufferView = gltf['bufferViews'][index_accessor['bufferView']]
    gl.glBindBuffer(index_bufferView['target'], index_bufferView['id'])
    gl.glDrawElements(primitive['mode'], index_accessor['count'], index_accessor['componentType'],
                      c_void_p(index_accessor.get('byteOffset', 0)))
    global num_draw_calls
    num_draw_calls += 1
    if CHECK_GL_ERRORS:
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('error drawing elements')
num_draw_calls = 0


def draw_mesh(mesh, gltf,
              projection_matrix=None,
              view_matrix=None,
              camera_matrix=None,
              model_matrix=None,
              modelview_matrix=None,
              normal_matrix=None,
              #mvp_matrix=None,
              local_matrix=None):
    # set_vert_draw_state(projection_matrix=projection_matrix,
    #                     view_matrix=view_matrix,
    #                     camera_matrix=camera_matrix,
    #                     model_matrix=model_matrix,
    #                     modelview_matrix=modelview_matrix,
    #                     normal_matrix=normal_matrix,
    #                     mvp_matrix=mvp_matrix,
    #                     local_matrix=local_matrix)
    for i, primitive in enumerate(mesh['primitives']):
        draw_primitive(primitive, gltf,
                       projection_matrix=(projection_matrix if i == 0 else None),
                       view_matrix=(view_matrix if i == 0 else None),
                       camera_matrix=(camera_matrix if i == 0 else None),
                       model_matrix=(model_matrix if i == 0 else None),
                       modelview_matrix=(modelview_matrix if i == 0 else None),
                       normal_matrix=(normal_matrix if i == 0 else None),
                       #mvp_matrix=(mvp_matrix if i == 0 else None),
                       local_matrix=(local_matrix if i == 0 else None))


def draw_node(node, gltf,
              projection_matrix=None,
              view_matrix=None,
              camera_matrix=None):
    model_matrix = node['world_matrix']
    if view_matrix is None:
        view_matrix = np.linalg.inv(camera_matrix)
    model_matrix.dot(view_matrix, out=draw_node.modelview_matrix)
    draw_node.normal_matrix[...] = np.linalg.inv(draw_node.modelview_matrix[:3,:3])
    #if projection_matrix is not None:
    #    projection_matrix.dot(draw_node.modelview_matrix, out=draw_node.mvp_matrix)
    if 'meshes' in node: # GLTF v1.0
        meshes = node['meshes']
    elif 'mesh' in node: # GLTF v2.0
        meshes = [node['mesh']]
    else:
        meshes = []
    for mesh_name in meshes:
        draw_mesh(gltf['meshes'][mesh_name], gltf,
                  projection_matrix=projection_matrix,
                  view_matrix=view_matrix,
                  camera_matrix=camera_matrix,
                  model_matrix=model_matrix,
                  modelview_matrix=draw_node.modelview_matrix,
                  normal_matrix=draw_node.normal_matrix)
                  #mvp_matrix=draw_node.mvp_matrix)
    if 'children' in node:
        for child in node['children']:
            draw_node(gltf['nodes'][child], gltf,
                      projection_matrix=projection_matrix,
                      view_matrix=view_matrix,
                      camera_matrix=camera_matrix)
draw_node.modelview_matrix = np.empty((4,4), dtype=np.float32)
draw_node.normal_matrix = np.eye(3, dtype=np.float32)
#draw_node.mvp_matrix = np.empty((4,4), dtype=np.float32)


def calc_projection_matrix(camera, out=None):
    if 'perspective' in camera:
        return calc_perspective_projection(**camera['perspective'], out=out)
    elif 'orthographic' in camera:
        return calc_orthographic_projection(**camera['orthographic'], out=out)
    else:
        raise Exception('camera does not have "perspective" or "orthographic" property')


def calc_perspective_projection(yfov=40*np.pi/180, aspectRatio=4/3, znear=0.01, zfar=100.0,
                                out=None):
    a, zn, zf = aspectRatio, znear, zfar
    f = 1 / np.tan(0.5 * yfov)
    if out is None:
        out = np.empty((4,4), dtype=np.float32)
    out[:] = list(zip(*[[f/a, 0,               0,               0],
                        [  0, f,               0,               0],
                        [  0, 0, (zf+zn)/(zn-zf), 2*zf*zn/(zn-zf)],
                        [  0, 0,              -1,              0]]))
    return out


def calc_orthographic_projection(xmag=1, ymag=1, znear=0.01, zfar=100.0,
                                 out=None):
    r, t, f, n = xmag, ymag, zfar, znear
    if out is None:
        out = np.empty((4,4), dtype=np.float32)
    out[:] = list(zip(*[[1/r,   0,       0,           0],
                        [  0, 1/t,       0,           0],
                        [  0,   0, 2/(n-f), (f+n)/(n-f)],
                        [  0,   0,       0,           1]]))
    return out


def update_world_matrices(node, gltf, world_matrix=None):
    if 'matrix' not in node:
        matrix = np.eye(4, dtype=np.float32)
        if 'rotation' in node:
            matrix[:3,:3] = set_matrix_from_quaternion(node['rotation']).T
            matrix[:3, 0] *= node['scale'][0]
            matrix[:3, 1] *= node['scale'][1]
            matrix[:3, 2] *= node['scale'][2]
            matrix[:3, 3] = node['translation']
    else:
        matrix = np.array(node['matrix'], dtype=np.float32).reshape((4, 4)).T
        node['matrix'] = np.ascontiguousarray(matrix)
    if world_matrix is None:
        world_matrix = matrix
    else:
        world_matrix = world_matrix.dot(matrix)
    node['world_matrix'] = np.ascontiguousarray(world_matrix.T)
    if 'children' in node:
        for child in [gltf['nodes'][n] for n in node['children']]:
            update_world_matrices(child, gltf, world_matrix=world_matrix)


def find_camera_in_nodes(gltf, nodes):
    camera = None
    for node in nodes:
        if 'camera' in node:
            return gltf['cameras'][node['camera']], node
        elif node.get('children', []):
            camera, camera_node = find_camera_in_nodes(gltf, [gltf['nodes'][n]
                                                              for n in node.get('children', [])])
            if camera is not None:
                return camera, camera_node
    return camera, None
