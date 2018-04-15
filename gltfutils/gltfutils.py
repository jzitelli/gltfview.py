import os.path
import base64
from ctypes import c_void_p
from itertools import chain
try:
    from types import MappingProxyType
except ImportError:
    MappingProxyType = dict
import logging

import numpy as np
import OpenGL.GL as gl
import PIL.Image as Image


from gltfutils.gl_rendering import set_matrix_from_quaternion
from gltfutils.pbrmr import setup_pbrmr_programs


_here = os.path.dirname(__file__)
_logger = logging.getLogger(__name__)


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

_DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE = {
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
for k, v in list(_DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE.items()):
    _DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE[int(k)] = v

_DEFAULT_SAMPLER = {
    "magFilter": 9729,
    "minFilter": 9987,
    "wrapS": 10497,
    "wrapT": 10497
}


def setup_shaders(gltf, uri_path):
    """Loads and compiles all shaders defined or referenced in the given gltf."""
    shader_ids = {}
    for shader_name, shader in gltf['shaders'].items():
        uri = shader['uri']
        if uri.startswith('data:text/plain;base64,'):
            shader_str = base64.urlsafe_b64decode(uri.split(',')[1]).decode()
            _logger.debug('decoded shader "%s"', shader_name)
        else:
            filename = os.path.join(uri_path, shader['uri'])
            shader_str = open(filename).read()
            _logger.debug('loaded shader "%s" (from %s)', shader_name, filename)
        shader_id = gl.glCreateShader(shader['type'])
        gl.glShaderSource(shader_id, shader_str)
        gl.glCompileShader(shader_id)
        if not gl.glGetShaderiv(shader_id, gl.GL_COMPILE_STATUS):
            raise Exception('FAILED to compile shader "%s":\n%s' % (shader_name, gl.glGetShaderInfoLog(shader_id).decode()))
        _logger.debug('compiled shader "%s"', shader_name)
        shader_ids[shader_name] = shader_id
    return shader_ids


def setup_programs(gltf, shader_ids):
    """
    Creates and links OpenGL programs for the input gltf dict, given the mapping
    from GLTF shader to OpenGL handle of the compiled vertex / fragment shaders.
    """
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
        if 'uniforms' in program:
            program['uniform_locations'] = {uniform_name: gl.glGetUniformLocation(program_id, uniform_name)
                                            for uniform_name in program['uniforms']}
        else:
            program['uniform_locations'] = {}
        _logger.debug('linked program "%s"\n  attribute locations: %s\n  uniform locations: %s',
                      program_name, program['attribute_locations'], program['uniform_locations'])


def backport_pbrmr_materials(gltf):
    """
    Converts v2 materials (paramaterized by the GLTF-2.0 standard PBR-MR material model)
    into an equivalent set of v1 material and lower-level properties:
    shaders, programs, techniques, materials.
    """
    setup_pbrmr_programs(gltf)


def load_images(gltf, uri_path):
    """
    Loads all images referenced in the input gltf dict,
    returning a dict mapping GLTF image to loaded PIL.Image.
    """
    # TODO: support data URIs
    pil_images = {}
    images = gltf.get('images', {})
    if isinstance(images, list):
        images = {i: image for i, image in enumerate(images)}
    for image_name, image in images.items():
        filename = os.path.join(uri_path, image['uri'])
        pil_image = Image.open(filename)
        if pil_image.mode == 'P':
            pil_image = pil_image.convert(pil_image.palette.mode)
        pil_images[filename] = pil_image
        _logger.debug('loaded image %s from "%s"', image_name, filename)
    return pil_images


def setup_textures(gltf, uri_path):
    """
    Creates within the current GL context all textures referenced in the input gltf dict.
    """
    pil_images = load_images(gltf, uri_path)
    for i, (texture_name, texture) in enumerate(gltf.get('textures', {}).items()):
        sampler = gltf['samplers'][texture['sampler']]
        image = gltf['images'][texture['source']]
        filename = os.path.join(uri_path, image['uri'])
        pil_image = pil_images[filename]
        if 'target' not in texture:
            texture['target'] = gl.GL_TEXTURE_2D # GLTF 1.0 DEFAULT
        texture_id = gl.glGenTextures(1)
        gl.glBindTexture(texture['target'], texture_id)
        if 'id' not in sampler:
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
            _logger.warn('''you are trying to use a texture with property "type" set to %s,
            not GL_UNSIGNED_BYTE (%d), is it going to work?!?!''',
                         texture['type'], int(gl.GL_UNSIGNED_BYTE))
        gl.glTexImage2D(texture['target'], 0,
                        texture['internalFormat'],
                        pil_image.width, pil_image.height, 0,
                        gl.GL_RGB, #texture['format'],
                        texture['type'],
                        np.array(list(pil_image.getdata()),
                                 dtype=(np.ubyte if texture['type'] == gl.GL_UNSIGNED_BYTE else np.ushort)))
        gl.glGenerateMipmap(texture['target'])
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create texture "%s"' % texture_name)
        texture['id'] = texture_id
        _logger.debug('created texture "%s"', texture_name)


def setup_textures_v2(gltf, uri_path):
    from copy import copy
    pil_images = load_images(gltf, uri_path)
    textures = gltf.get('textures', [])
    for i, texture in enumerate(textures):
        if 'samplers' not in gltf:
            gltf['samplers'] = []
        if 'sampler' not in texture or texture['sampler'] not in gltf['samplers']:
            texture['sampler'] = len(gltf['samplers'])
            gltf['samplers'].append(copy(_DEFAULT_SAMPLER))
        sampler = gltf['samplers'][texture['sampler']]
        image = gltf['images'][texture['source']]
        filename = os.path.join(uri_path, image['uri'])
        pil_image = pil_images[filename]
        texture_id = gl.glGenTextures(1)
        if 'target' not in texture:
            texture['target'] = gl.GL_TEXTURE_2D # GLTF-1.0 DEFAULT
        target = texture['target']
        gl.glBindTexture(target, texture_id)
        if 'type' not in texture:
            texture['type'] = gl.GL_UNSIGNED_BYTE
        if texture['type'] != gl.GL_UNSIGNED_BYTE:
            _logger.warn('''you are trying to use a texture with property "type" set to %s,
            not GL_UNSIGNED_BYTE (%d), is it going to work?!?!''',
                         texture['type'], int(gl.GL_UNSIGNED_BYTE))
        if 'id' not in sampler:
            sampler_id = gl.glGenSamplers(1)
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MIN_FILTER, sampler.get('minFilter', 9986))
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_MAG_FILTER, sampler.get('magFilter', 9729))
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_S, sampler.get('wrapS', 10497))
            gl.glSamplerParameteri(sampler_id, gl.GL_TEXTURE_WRAP_T, sampler.get('wrapT', 10497))
            sampler['id'] = sampler_id
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        if pil_image.mode == 'RGBA':
            internal_format = gl.GL_RGBA
        elif pil_image.mode == 'L':
            internal_format = gl.GL_RED
        else:
            internal_format = gl.GL_RGB
        gl.glTexImage2D(target, 0,
                        internal_format,
                        pil_image.width, pil_image.height, 0,
                        internal_format,
                        texture['type'],
                        np.array(list(pil_image.getdata()),
                                 dtype=(np.ubyte if texture['type'] == gl.GL_UNSIGNED_BYTE else np.ushort)))
        gl.glGenerateMipmap(target)
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
        byteOffset = bufferView.get('byteOffset', 0)
        target = bufferView.get('target', gl.GL_ARRAY_BUFFER)
        gl.glBindBuffer(target, buffer_id)
        gl.glBufferData(target, bufferView['byteLength'],
                        data_buffers[bufferView['buffer']][byteOffset:], gl.GL_STATIC_DRAW)
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create bufferView %s' % i)
        bufferView['id'] = buffer_id
        gl.glBindBuffer(target, 0)
        _logger.debug('created bufferView %s', i if 'name' not in bufferView else '%d ("%s")' % (i, bufferView['name']))


def _setup_vertex_array_objects_for_primitive(primitive, gltf):
    if 'vao' in primitive:
        return
    enabled_locations = []
    buffer_id = None
    vao = gl.glGenVertexArrays(1)
    gl.glBindVertexArray(vao)
    material = gltf['materials'][primitive['material']]
    technique = gltf['techniques'][material['technique']]
    program = gltf['programs'][technique['program']]
    accessor_names = primitive['attributes']
    for attribute_name, parameter_name in technique['attributes'].items():
        location = program['attribute_locations'][attribute_name]
        parameter = technique['parameters'][parameter_name]
        if 'semantic' in parameter:
            semantic = parameter['semantic']
            if semantic in accessor_names:
                accessor = gltf['accessors'][accessor_names[semantic]]
                bufferView = gltf['bufferViews'][accessor['bufferView']]
                if buffer_id != bufferView['id']:
                    buffer_id = bufferView['id']
                    target = bufferView.get('target', gl.GL_ARRAY_BUFFER)
                    buffer_id = bufferView['id']
                    gl.glBindBuffer(target, buffer_id)
                gl.glEnableVertexAttribArray(location)
                enabled_locations.append(location)
                gl.glVertexAttribPointer(location,
                                         GLTF_BUFFERVIEW_TYPE_SIZES[accessor['type']],
                                         accessor['componentType'], False,
                                         accessor.get('byteStride', # GLTF 1.0
                                                      bufferView.get('byteStride', 0)), # GLTF 2.0
                                         c_void_p(accessor.get('byteOffset', 0)))
            else:
                raise Exception('expected a semantic property for attribute "%s", parameter "%s"' %
                                (attribute_name, parameter_name))
    gl.glBindVertexArray(0)
    for location in enabled_locations:
        gl.glDisableVertexAttribArray(location)
    primitive['vao'] = vao


def setup_vertex_array_objects(gltf, mesh):
    for primitive in mesh['primitives']:
        _setup_vertex_array_objects_for_primitive(primitive, gltf)


def init_scene(gltf, uri_path, scene_name=None):
    version = gltf.get('asset', {'version': '1.0'})['version']
    generator = gltf.get('asset', {'generator': 'no generator was specified for this file'})\
                    .get('generator', 'no generator was specified for this file')
    _logger.info('''

  INITIALIZING FOR GLTF VERSION %s...
    GENERATOR: %s

''', version, generator)

    def _init_scene_v1(gltf, uri_path, scene_name=None):
        shader_ids = setup_shaders(gltf, uri_path)
        setup_programs(gltf, shader_ids)
        setup_textures(gltf, uri_path)
        setup_buffers(gltf, uri_path)
        scenes = gltf.get('scenes', {})
        if scene_name and scene_name in scenes:
            return scenes[scene_name]
        else:
            # return a constructed scene containing all root nodes:
            nodes_dict = dict(gltf.get('nodes', {}))
            for node_name, node in gltf.get('nodes', {}).items():
                for child_name in node.get('children', []):
                    if child_name in nodes_dict:
                        nodes_dict.pop(child_name)
            return next((scene for scene in scenes.values()), {'nodes': list(nodes_dict.keys())})

    def _init_scene_v2(gltf, uri_path, scene_name=None):
        backport_pbrmr_materials(gltf)
        shader_ids = setup_shaders(gltf, uri_path)
        setup_programs(gltf, shader_ids)
        setup_textures_v2(gltf, uri_path)
        setup_buffers_v2(gltf, uri_path)
        scenes = gltf.get('scenes', [])
        if scene_name and scene_name < len(scenes):
            return scenes[scene_name]
        else:
            root_nodes = set(range(len(gltf.get('nodes', []))))
            for i_node, node in enumerate(gltf.get('nodes', [])):
                for i_child in node.get('children', []):
                    if i_child in root_nodes:
                        root_nodes.remove(i_child)
            return next((scene for scene in scenes), {'nodes': list(root_nodes)})

    if version.startswith('1.'):
        scene = _init_scene_v1(gltf, uri_path, scene_name=scene_name)
        all_meshes = gltf.get('meshes', {})
    else:
        if not version.startswith('2.'):
            _logger.warning('''unknown GLTF version: %s
            ...will try loading as 2.0...
            ''', version)
        scene = _init_scene_v2(gltf, uri_path, scene_name=scene_name)
        all_meshes = gltf.get('meshes', [])

    nodes = [gltf['nodes'][n] for n in scene.get('nodes', [])]
    flattened_nodes = flatten_nodes(nodes, gltf)
    flattened_meshes = list(chain.from_iterable([[all_meshes[m] for m in node.get('meshes', [])] +
                                                 ([] if 'mesh' not in node else
                                                  [all_meshes[node['mesh']]])
                                                 for node in flattened_nodes]))
    _logger.debug('''
    number of root nodes in scene: %d
    number of nodes in scene: %d
    number of meshes in scene: %d''', len(nodes), len(flattened_nodes), len(flattened_meshes))
    for mesh in flattened_meshes:
        setup_vertex_array_objects(gltf, mesh)
    for node in nodes:
        update_world_matrices(node, gltf)
    return scene


def find_mesh_bounds(mesh, gltf):
    bounds = {}
    for primitive in mesh['primitives']:
        material = gltf['materials'][primitive['material']]
        technique = gltf['techniques'][material['technique']]
        accessor_names = primitive['attributes']
        for attribute_name, parameter_name in technique['attributes'].items():
            parameter = technique['parameters'][parameter_name]
            if 'semantic' in parameter:
                semantic = parameter['semantic']
                if semantic in accessor_names:
                    accessor = gltf['accessors'][accessor_names[semantic]]
                    if ('min' in accessor or 'max' in accessor) and semantic not in bounds:
                        ndim = GLTF_BUFFERVIEW_TYPE_SIZES[accessor['type']]
                        bounds[semantic] = np.array([ndim*[float('inf')], ndim*[float('-inf')]],
                                                    dtype=np.float32)
                    if 'min' in accessor:
                        bounds[semantic][0] = np.minimum(bounds[semantic][0], accessor['min'])
                    if 'max' in accessor:
                        bounds[semantic][1] = np.maximum(bounds[semantic][1], accessor['max'])
    return bounds


def find_scene_bounds(scene, gltf):
    root_nodes = [gltf['nodes'][n] for n in scene.get('nodes', [])]
    all_nodes = flatten_nodes(root_nodes, gltf)
    scene_bounds = {}
    all_mesh_bounds = []
    world_matrices = []
    for node in all_nodes:
        if 'mesh' in node:
            mesh_bounds = find_mesh_bounds(gltf['meshes'][node['mesh']], gltf)
            all_mesh_bounds.append(mesh_bounds)
            world_matrices.append(node['world_matrix'])
        if 'meshes' in node:
            for m in node['meshes']:
                mesh_bounds = find_mesh_bounds(gltf['meshes'][m], gltf)
                all_mesh_bounds.append(mesh_bounds)
                world_matrices.append(node['world_matrix'])
    for mesh_bounds, world_matrix in zip(all_mesh_bounds, world_matrices):
        for semantic, bounds in mesh_bounds.items():
            ndim = bounds.shape[1]
            if semantic not in scene_bounds:
                scene_bounds[semantic] = np.array([ndim*[float( 'inf')],
                                                   ndim*[float('-inf')]], dtype=np.float32)
            mesh_world_bounds = bounds.dot(world_matrix[:ndim,:ndim])
            scene_bounds[semantic][0] = np.minimum(scene_bounds[semantic][0], mesh_world_bounds[0])
            scene_bounds[semantic][1] = np.maximum(scene_bounds[semantic][1], mesh_world_bounds[1])
    return scene_bounds


def set_technique_state(technique_name, gltf):
    if set_technique_state.current_technique == technique_name:
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
    set_material_state.n_tex = 0
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
        value = material_values.get(parameter_name,
                                    parameter.get('value',
                                                  _DEFAULT_MATERIAL_VALUES_BY_PARAM_TYPE.get(parameter['type'])))
        if value is None:
            raise Exception('''could not determine a value to use for material "%s", parameter "%s":
            %s %s''' % (material_name, parameter_name,
                        parameter['type'], uniform_name))
        if isinstance(value, (tuple, list)):
            value = np.array(value, dtype=np.float32)
        if uniform_name in program['uniform_locations']:
            location = program['uniform_locations'][uniform_name]
        else:
            location = gl.glGetUniformLocation(program['id'], uniform_name)
            program['uniform_locations'][uniform_name] = location
        if parameter['type'] == gl.GL_SAMPLER_2D:
            texture = textures[value]
            gl.glActiveTexture(gl.GL_TEXTURE0 + set_material_state.n_tex)
            gl.glBindTexture(texture['target'], texture['id'])
            gl.glBindSampler(gl.GL_TEXTURE0 + set_material_state.n_tex,
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
                raise Exception('unhandled semantic for uniform "%s": %s' %
                                (uniform_name, parameter['semantic']))
    gl.glBindVertexArray(primitive['vao'])
    if CHECK_GL_ERRORS:
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('error setting draw state')
set_draw_state.modelview_matrix = np.empty((4,4), dtype=np.float32)
set_draw_state.mvp_matrix = np.empty((4,4), dtype=np.float32)


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
    if 'target' not in index_bufferView:
        index_bufferView['target'] = gl.GL_ELEMENT_ARRAY_BUFFER
    gl.glBindBuffer(index_bufferView['target'], index_bufferView['id'])
    gl.glDrawElements(primitive.get('mode', gl.GL_TRIANGLES), index_accessor['count'],
                      index_accessor['componentType'], c_void_p(index_accessor.get('byteOffset', 0)))
    global num_draw_calls
    num_draw_calls += 1
    if CHECK_GL_ERRORS:
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('error drawing elements')
num_draw_calls = 0


def set_vert_draw_state(projection_matrix=None,
                        view_matrix=None,
                        camera_matrix=None,
                        model_matrix=None,
                        modelview_matrix=None,
                        normal_matrix=None,
                        mvp_matrix=None,
                        local_matrix=None):
    pass


def draw_mesh(mesh, gltf,
              projection_matrix=None,
              view_matrix=None,
              camera_matrix=None,
              model_matrix=None,
              modelview_matrix=None,
              normal_matrix=None,
              mvp_matrix=None,
              local_matrix=None):
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
    if 'meshes' in node: # GLTF v1.0
        meshes = node['meshes']
    elif 'mesh' in node: # GLTF v2.0
        meshes = [node['mesh']]
    else:
        meshes = []
    if meshes:
        model_matrix = node['world_matrix']
        if view_matrix is None:
            view_matrix = np.linalg.inv(camera_matrix)
        model_matrix.dot(view_matrix, out=draw_node.modelview_matrix)
        draw_node.normal_matrix[...] = np.linalg.inv(draw_node.modelview_matrix[:3,:3])
        #if projection_matrix is not None:
        #    projection_matrix.dot(draw_node.modelview_matrix, out=draw_node.mvp_matrix)
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
draw_node.modelview_matrix = np.eye(4, dtype=np.float32)
draw_node.normal_matrix    = np.eye(3, dtype=np.float32)
draw_node.mvp_matrix       = np.eye(4, dtype=np.float32)


def update_world_matrices(node, gltf, world_matrix=None):
    if 'matrix' not in node:
        matrix = np.eye(4, dtype=np.float32)
        if 'rotation' in node:
            matrix[:3,:3] = set_matrix_from_quaternion(node['rotation']).T
        if 'scale' in node:
            scale = node['scale']
            matrix[:3, 0] *= scale[0]
            matrix[:3, 1] *= scale[1]
            matrix[:3, 2] *= scale[2]
        if 'translation' in node:
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


def flatten_nodes(nodes, gltf, flat=None):
    all_nodes = gltf.get('nodes', {})
    def find_all_descendents(node):
        children = [all_nodes[c] for c in node.get('children', [])]
        return children + list(chain.from_iterable(find_all_descendents(child) for child in children))
    return list(chain(nodes, chain.from_iterable(find_all_descendents(node) for node in nodes)))


def calc_projection_matrix(camera, out=None, **kwargs):
    if 'perspective' in camera:
        _kwargs = dict(camera['perspective'])
        _kwargs.update(kwargs)
        return calc_perspective_projection(**_kwargs, out=out)
    elif 'orthographic' in camera:
        _kwargs = dict(camera['orthographic'])
        _kwargs.update(kwargs)
        return calc_orthographic_projection(**_kwargs, out=out)
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
