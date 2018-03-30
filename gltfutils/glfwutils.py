from sys import stdout, exit
from collections import defaultdict
import time
import os.path
import logging

import numpy as np
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False
OpenGL.ERROR_ON_COPY = True
import OpenGL.GL as gl
import cyglfw3 as glfw


_logger = logging.getLogger(__name__)
import gltfutils.gltfutils as gltfu
try:
    from gltfutils.openvr_renderer import OpenVRRenderer
except ImportError:
    OpenVRRenderer = None


def setup_glfw(width=800, height=600, double_buffered=False, multisample=None, window_title='gltfview'):
    if not glfw.Init():
        raise Exception('failed to initialize glfw')
    if not double_buffered:
        glfw.WindowHint(glfw.DOUBLEBUFFER, False)
        glfw.SwapInterval(0)
    if multisample is not None:
        glfw.WindowHint(glfw.SAMPLES, multisample)
    window = glfw.CreateWindow(width, height, window_title)
    if not window:
        glfw.Terminate()
        raise Exception('failed to create glfw window')
    glfw.MakeContextCurrent(window)
    _logger.info('GL_VERSION: %s', gl.glGetString(gl.GL_VERSION))
    return window


def view_gltf(gltf, uri_path, scene_name=None,
              openvr=False,
              window_size=None,
              clear_color=(0.01, 0.01, 0.013, 0.0),
              multisample=None,
              nframes=None,
              screenshot=None,
              camera_position=None, camera_rotation=None,
              zfar=None, znear=None,
              filename=None,
              **kwargs):
    _t0 = time.time()
    version = '1.0'
    generator = 'no generator was specified for this file'
    if 'asset' in gltf:
        asset = gltf['asset']
        version = asset['version']
        generator = asset.get('generator', generator)
    _logger.info('''

  INITIALIZING FOR GLTF VERSION %s...
    GENERATOR: %s

''', version, generator)
    if window_size is None:
        window_size = [800, 600]
    else:
        window_size = list(window_size)
    window_title = 'gltfview'
    if filename:
        window_title += ' - %s' % filename
    window = setup_glfw(width=window_size[0], height=window_size[1],
                        double_buffered=not openvr, multisample=multisample,
                        window_title=window_title)

    gl.glClearColor(*clear_color)

    camera = {'type': 'perspective',
              'perspective': {"aspectRatio": window_size[0]/window_size[1],
                              "yfov": 0.660593,
                              "zfar": zfar if zfar is not None else 1000.0,
                              "znear": znear if znear is not None else 0.01}}
    projection_matrix = np.zeros((4,4), dtype=np.float32)

    def on_resize(window, width, height):
        window_size[:] = width, height
        gl.glViewport(0, 0, window_size[0], window_size[1])
        gltfu.calc_projection_matrix(camera, out=projection_matrix,
                                     aspectRatio=window_size[0] / max(5, window_size[1]))
    glfw.SetWindowSizeCallback(window, on_resize)


    def init_scene_v1(gltf, uri_path):
        shader_ids = gltfu.setup_shaders(gltf, uri_path)
        gltfu.setup_programs(gltf, shader_ids)
        gltfu.setup_textures(gltf, uri_path)
        gltfu.setup_buffers(gltf, uri_path)
        if scene_name and scene_name in gltf.get('scenes', {}):
            scene = gltf['scenes'][scene_name]
        else:
            scene = list(gltf['scenes'].values())[0]
        return scene

    def init_scene_v2(gltf, uri_path):
        gltfu.backport_pbrmr_materials(gltf)
        shader_ids = gltfu.setup_shaders(gltf, uri_path)
        gltfu.setup_programs(gltf, shader_ids)
        gltfu.setup_textures_v2(gltf, uri_path)
        gltfu.setup_buffers_v2(gltf, uri_path)
        if scene_name and scene_name < len(gltf.get('scenes', [])):
            scene = gltf['scenes'][scene_name]
        else:
            scene = gltf['scenes'][0]
        return scene

    if version.startswith('1.'):
        scene = init_scene_v1(gltf, uri_path)
    else:
        if not version.startswith('2.'):
            _logger.warning('''unknown GLTF version: %s
            ...will try loading as 2.0...
            ''')
        scene = init_scene_v2(gltf, uri_path)
    if scene is None:
        _logger.error('could not load scene, now exiting...')
        exit(1)


    nodes = [gltf['nodes'][n] for n in scene['nodes']]
    for node in nodes:
        gltfu.update_world_matrices(node, gltf)

    def find_camera_node(gltf, nodes):
        for n in nodes:
            if 'camera' in gltf['nodes'][n]:
                return gltf['nodes'][n]
            if 'children' in gltf['nodes'][n]:
                node = find_camera_node(gltf, gltf['nodes'][n]['children'])
                if node is not None:
                    return node

    camera_node = find_camera_node(gltf, scene['nodes'])
    if camera_node is not None:
        camera = gltf['cameras'][camera_node['camera']]
        _logger.info('found camera: %s', camera)
        camera_world_matrix = camera_node['world_matrix']
    else:
        _logger.info('no camera specified, using default')
        camera_world_matrix = np.eye(4, dtype=np.float32)
    if camera_position is not None:
        _logger.info('setting camera position to %s', camera_position)
        camera_world_matrix[3, :3] = camera_position
    if camera_rotation is not None:
        if camera_rotation[1]:
            s, c = np.sin(camera_rotation[1]), np.cos(camera_rotation[1])
            r = np.array([[c, -s],
                          [s,  c]], dtype=np.float32)
            camera_world_matrix[:3:2,:3:2] = camera_world_matrix[:3:2,:3:2].dot(r.T)
            # camera_world_matrix[0,0] = c; camera_world_matrix[0,2] = -s
            # camera_world_matrix[2,0] = s; camera_world_matrix[2,2] = c
    on_resize(window, window_size[0], window_size[1])

    # sort nodes from front to back to avoid overdraw (assuming opaque objects):
    nodes = sorted(nodes, key=lambda node: np.linalg.norm(camera_world_matrix[3, :3] - node['world_matrix'][3, :3]))

    process_input = setup_controls(camera_world_matrix=camera_world_matrix, window=window,
                                   screen_capture_prefix=os.path.splitext(os.path.split(filename)[-1])[0] if filename else None)
    _t1 = time.time()
    _dt = _t1 - _t0
    _logger.info('''...INITIALIZATION COMPLETE (took %s seconds)''', _dt);

    # BURNER FRAME:
    gltfu.num_draw_calls = 0
    process_input(0.0)
    render(gltf, nodes, window_size,
           camera_world_matrix=camera_world_matrix,
           projection_matrix=projection_matrix)
    if screenshot:
        save_screen(window, screenshot)
    num_draw_calls_per_frame = gltfu.num_draw_calls
    _logger.info("NUM DRAW CALLS PER FRAME: %d", num_draw_calls_per_frame)

    _logger.info('''STARTING RENDER LOOP...''')
    if nframes:
        _logger.info(""" * * * WILL RENDER %s FRAMES * * * """, nframes)
    stdout.flush()

    import gc; gc.collect() # does it do anything?

    if openvr and OpenVRRenderer is not None:
        vr_renderer = OpenVRRenderer(multisample=multisample, poll_tracked_device_frequency=90)
        setup_vr_controls()
        render_stats = vr_render_loop(vr_renderer=vr_renderer, process_input=process_input,
                                      window=window, window_size=window_size,
                                      gltf=gltf, nodes=nodes)
        vr_renderer.shutdown()
    else:
        render_stats = render_loop(process_input=process_input,
                                   window=window, window_size=window_size,
                                   gltf=gltf, nodes=nodes,
                                   camera_world_matrix=camera_world_matrix,
                                   projection_matrix=projection_matrix,
                                   nframes=nframes)
    _logger.info('''QUITING...

%s
''', '\n'.join('  %21s: %s' % (k, v) for k, v in render_stats.items()))
    glfw.DestroyWindow(window)
    glfw.Terminate()


def render_loop(process_input=None, window=None, window_size=None,
                gltf=None, nodes=None,
                camera_world_matrix=None, projection_matrix=None,
                nframes=None):
    _nframes = 0
    dt_max = 0.0
    lt = st = glfw.GetTime()
    while not glfw.WindowShouldClose(window) and _nframes != nframes:
        t = glfw.GetTime()
        dt = t - lt
        lt = t
        dt_max = max(dt, dt_max)
        process_input(dt)
        render(gltf, nodes, window_size,
               camera_world_matrix=camera_world_matrix,
               projection_matrix=projection_matrix)
        _nframes += 1
        glfw.SwapBuffers(window)
    return {'NUM FRAMES RENDERED': _nframes,
            'AVERAGE FPS': _nframes / (t - st),
            'MAX FRAME RENDER TIME': dt_max}


def render(gltf, nodes, window_size,
           projection_matrix=None,
           camera_world_matrix=None,
           **frame_data):
    gl.glViewport(0, 0, window_size[0], window_size[1])
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    gltfu.set_material_state.current_material = None
    gltfu.set_technique_state.current_technique = None
    for node in nodes:
        gltfu.draw_node(node, gltf,
                        projection_matrix=projection_matrix,
                        camera_matrix=camera_world_matrix,
                        **frame_data)


def vr_render_loop(vr_renderer=None, process_input=None,
                   window=None, window_size=None,
                   gltf=None, nodes=None):
    gltfu.num_draw_calls = 0
    nframes = 0
    dt_max = 0.0
    st = lt = glfw.GetTime()
    while not glfw.WindowShouldClose(window):
        t = glfw.GetTime()
        dt = t - lt
        lt = t
        process_input(dt)
        vr_renderer.process_input()
        vr_renderer.render(gltf, nodes, window_size)
        dt_max = max(dt, dt_max)
        nframes += 1
        glfw.SwapBuffers(window)
    return {'NUM FRAMES RENDERER': nframes,
            'AVERAGE FPS': nframes / (t - st),
            'MAX FRAME RENDER TIME': dt_max}


def setup_controls(window=None, camera_world_matrix=None,
                   move_speed=None, turn_speed=0.5,
                   screen_capture_prefix='screen-capture'):
    if move_speed is None:
        move_speed = 1.5 * abs(camera_world_matrix[3,3] / camera_world_matrix[2,2])
    _logger.debug('move_speed = %s', move_speed)
    _logger.info('''

  KEYBOARD CONTROLS: W/S/A/D ----------- move Fwd/Bwd/Lft/Rgt
                     Q/Z --------------- move Up/Down
                     <-/-> (arrow keys)- turn Lft/Rgt

                     C ----------------- capture screenshot

                     Esc --------------- quit
''')
    camera_position = camera_world_matrix[3, :3]
    camera_rotation = camera_world_matrix[:3, :3]
    dposition = np.zeros(3, dtype=np.float32)
    rotation = np.eye(3, dtype=np.float32)
    key_state = defaultdict(bool)
    key_state_chg = defaultdict(bool)
    def on_keydown(window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.SetWindowShouldClose(window, gl.GL_TRUE)
        elif action == glfw.PRESS:
            if not key_state[key]:
                key_state_chg[key] = True
            else:
                key_state_chg[key] = False
            key_state[key] = True
        elif action == glfw.RELEASE:
            if key_state[key]:
                key_state_chg[key] = True
            else:
                key_state_chg[key] = False
            key_state[key] = False
    glfw.SetKeyCallback(window, on_keydown)
    def on_mousedown(window, button, action, mods):
        pass
    glfw.SetMouseButtonCallback(window, on_mousedown)

    _capture_wait = 0.0
    _num_captures = 0
    def process_input(dt):
        nonlocal _capture_wait, _num_captures
        glfw.PollEvents()
        if _capture_wait > 0:
            _capture_wait -= dt
        elif key_state[glfw.KEY_C]:
            _logger.info('''capturing screen...
            camera position: %s''', camera_position)
            save_screen(window, '.'.join([screen_capture_prefix, '%03d' % _num_captures, 'png']))
            _num_captures += 1
            _capture_wait = 0.25
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
        if theta:
            rotation[0,0] = np.cos(theta)
            rotation[2,2] = rotation[0,0]
            rotation[0,2] = np.sin(theta)
            rotation[2,0] = -rotation[0,2]
            camera_rotation[...] = rotation.dot(camera_world_matrix[:3,:3])
        if dposition.any():
            camera_position[:] += camera_rotation.T.dot(dposition)
    return process_input


def setup_vr_controls():
    _logger.info('''

      HTC VIVE CONTROLS: TBD

''')


def save_screen(window, filepath='screenshot.png'):
    from PIL import Image
    w, h = glfw.GetWindowSize(window)
    pixels = gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE)
    pil_image = Image.frombytes('RGB', (w, h), pixels).transpose(Image.FLIP_TOP_BOTTOM)
    pil_image.save(filepath)
    _logger.info('...saved %s', filepath)
