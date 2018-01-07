from sys import stdout
from collections import defaultdict
import time
import logging

import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False
OpenGL.ERROR_ON_COPY = True
import OpenGL.GL as gl
import cyglfw3 as glfw
import numpy as np


_logger = logging.getLogger(__name__)
import gltfutils.gltfutils as gltfu
import gltfutils.pbrmr as pbrmr
try:
    from gltfutils.openvr_renderer import OpenVRRenderer
except ImportError:
    OpenVRRenderer = None


def setup_glfw(width=800, height=600, double_buffered=False, multisample=None):
    if not glfw.Init():
        raise Exception('failed to initialize glfw')
    if not double_buffered:
        glfw.WindowHint(glfw.DOUBLEBUFFER, False)
        glfw.SwapInterval(0)
    if multisample is not None:
        glfw.WindowHint(glfw.SAMPLES, multisample)
    window = glfw.CreateWindow(width, height, "gltfview")
    if not window:
        glfw.Terminate()
        raise Exception('failed to create glfw window')
    glfw.MakeContextCurrent(window)
    _logger.info('GL_VERSION: %s', gl.glGetString(gl.GL_VERSION))
    return window


def view_gltf(gltf, uri_path, scene_name=None, openvr=False, window_size=None, multisample=None, clear_color=(0.01, 0.01, 0.013, 0.0)):
    _t0 = time.time()
    version = '1.0'
    generator = 'no generator was specified for this file'
    if 'asset' in gltf:
        asset = gltf['asset']
        version = asset['version']
        generator = asset.get('generator', generator)
    _logger.info('''
INITIALIZING FOR GLTF VERSION %s...\nGENERATOR: %s''',
                     version, generator)
    if window_size is None:
        window_size = [800, 600]
    window = setup_glfw(width=window_size[0], height=window_size[1],
                        double_buffered=not openvr,
                        multisample=multisample)
    gl.glClearColor(*clear_color)
    if openvr and OpenVRRenderer is not None:
        vr_renderer = OpenVRRenderer(multisample=multisample, poll_tracked_device_frequency=90)
    else:
        vr_renderer = None
    projection_matrix = np.zeros((4,4), dtype=np.float32)
    camera = None
    def on_resize(window, width, height):
        window_size[:] = width, height
        gl.glViewport(0, 0, window_size[0], window_size[1])
        if camera is None:
            gltfu.calc_perspective_projection(aspectRatio=window_size[0] / max(5, window_size[1]),
                                              out=projection_matrix)
        elif 'perspective' in camera:
            camera['perspective']['aspectRatio'] = window_size[0] / max(5, window_size[1])
            gltfu.calc_projection_matrix(camera, out=projection_matrix)
    glfw.SetWindowSizeCallback(window, on_resize)

    if version.startswith('1.'):
        shader_ids = gltfu.setup_shaders(gltf, uri_path)
        gltfu.setup_programs(gltf, shader_ids)
        gltfu.setup_textures(gltf, uri_path)
        gltfu.setup_buffers(gltf, uri_path)
        if scene_name and scene_name in gltf.get('scenes', {}):
            scene = gltf['scenes'][scene_name]
        else:
            scene = list(gltf['scenes'].values())[0]

    elif version.startswith('2.'):
        gltfu.setup_textures_v2(gltf, uri_path)
        gltfu.setup_buffers_v2(gltf, uri_path)
        pbrmr.setup_techniques_v2(gltf, uri_path)
        if scene_name and scene_name < len(gltf.get('scenes', [])):
            scene = gltf['scenes'][scene_name]
        else:
            scene = gltf['scenes'][0]

    nodes = [gltf['nodes'][n] for n in scene['nodes']]
    for node in nodes:
        gltfu.update_world_matrices(node, gltf)

    camera_world_matrix = None
    for node in nodes:
        if 'camera' in node:
            camera = gltf['cameras'][node['camera']]
            gltfu.calc_projection_matrix(camera, out=projection_matrix)
            camera_world_matrix = node['world_matrix']
            break
    if not projection_matrix.any():
        gltfu.calc_perspective_projection(out=projection_matrix)
    if camera_world_matrix is None:
        camera_world_matrix = np.eye(4, dtype=np.float32)

    # sort nodes from front to back to avoid overdraw (assuming opaque objects):
    nodes = sorted(nodes, key=lambda node: np.linalg.norm(camera_world_matrix[3, :3] - node['world_matrix'][3, :3]))

    process_input = setup_controls(camera_world_matrix=camera_world_matrix, window=window)
    _t1 = time.time()
    _dt = _t1 - _t0
    _logger.info('''...INITIALIZATION COMPLETE (took %s seconds)

STARTING RENDER LOOP...

    KEYBOARD CONTROLS: W/S/A/D ----------- move Fwd/Bwd/Lft/Rgt
                       Q/Z --------------- move Up/Down
                       <-/-> (arrow keys)- turn Lft/Rgt
                       Esc --------------- exit

    MOUSE CONTROLS   : TBD

    HTC VIVE CONTROLS: TBD

''', _dt); stdout.flush()
    render_loop(vr_renderer=vr_renderer,
                process_input=process_input,
                window=window, window_size=window_size,
                gltf=gltf, nodes=nodes,
                camera_world_matrix=camera_world_matrix,
                projection_matrix=projection_matrix)


def render_loop(vr_renderer=None, process_input=None, window=None, gltf=None, nodes=None, window_size=None,
                camera_world_matrix=None, projection_matrix=None):
    import gc; gc.collect()
    gltfu.num_draw_calls = 0
    nframes = 0
    dt_max = 0.0
    lt = glfw.GetTime()
    while not glfw.WindowShouldClose(window):
        t = glfw.GetTime()
        dt = t - lt
        lt = t
        process_input(dt)
        if vr_renderer is not None:
            vr_renderer.process_input()
            vr_renderer.render(gltf, nodes, window_size)
        else:
            gl.glViewport(0, 0, window_size[0], window_size[1])
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            view_matrix = np.linalg.inv(camera_world_matrix)
            gltfu.set_material_state.current_material = None
            gltfu.set_technique_state.current_technique = None
            for node in nodes:
                gltfu.draw_node(node, gltf,
                                projection_matrix=projection_matrix,
                                view_matrix=view_matrix)
        if nframes == 0:
            _logger.info("NUM DRAW CALLS PER FRAME: %d", gltfu.num_draw_calls)
            stdout.flush()
            st = glfw.GetTime()
        else:
            dt_max = max(dt, dt_max)
        nframes += 1
        glfw.SwapBuffers(window)
    _logger.info('''EXITING...

  NUM FRAMES RENDERED: %d
  AVERAGE FPS: %f
  MAX FRAME RENDER TIME: %f seconds

''', nframes - 1, ((nframes - 1) / (t - st)), dt_max)
    if vr_renderer is not None:
        vr_renderer.shutdown()
    glfw.DestroyWindow(window)
    glfw.Terminate()


def setup_controls(camera_world_matrix=None, window=None):
    camera_position = camera_world_matrix[3, :3]
    camera_rotation = camera_world_matrix[:3, :3]
    dposition = np.zeros(3, dtype=np.float32)
    rotation = np.eye(3, dtype=np.float32)
    move_speed = 2.0
    turn_speed = 0.5
    key_state = defaultdict(bool)
    def on_keydown(window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.SetWindowShouldClose(window, gl.GL_TRUE)
        elif action == glfw.PRESS:
            key_state[key] = True
        elif action == glfw.RELEASE:
            key_state[key] = False
    glfw.SetKeyCallback(window, on_keydown)
    def on_mousedown(window, button, action, mods):
        pass
    glfw.SetMouseButtonCallback(window, on_mousedown)
    def process_input(dt):
        glfw.PollEvents()
        dposition[:] = 0.0
        if key_state[glfw.KEY_W]:
            dposition[2] -= dt * move_speed
        if key_state[glfw.KEY_S]:
            dposition[2] += dt * move_speed
        if key_state[glfw.KEY_A]:
            dposition[0] -= dt * move_speed
        if key_state[glfw.KEY_D]:
            dposition[0] += dt * move_speed
        if key_state[glfw.KEY_Q]:
            dposition[1] += dt * move_speed
        if key_state[glfw.KEY_Z]:
            dposition[1] -= dt * move_speed
        theta = 0.0
        if key_state[glfw.KEY_LEFT]:
            theta -= dt * turn_speed
        if key_state[glfw.KEY_RIGHT]:
            theta += dt * turn_speed
        rotation[0,0] = np.cos(theta)
        rotation[2,2] = rotation[0,0]
        rotation[0,2] = np.sin(theta)
        rotation[2,0] = -rotation[0,2]
        camera_rotation[...] = rotation.dot(camera_world_matrix[:3,:3])
        camera_position[:] += camera_rotation.T.dot(dposition)
    return process_input
