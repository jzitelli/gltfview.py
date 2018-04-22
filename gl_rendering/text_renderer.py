import os.path
import logging

import numpy as np
from freetype import Face, FT_LOAD_RENDER, FT_LOAD_FORCE_AUTOHINT


_logger = logging.getLogger(__name__)
_here = os.path.dirname(__file__)


from gltfutils.glslutils import _ATTRIBUTE_DECL_RE, _UNIFORM_DECL_RE


class TextRenderer(object):
    _VERT_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'text_renderer_vert.glsl')
    _FRAG_SHADER_SRC_PATH = os.path.join(_here, 'shaders', 'text_renderer_frag.glsl')
    _VERT_SHADER_SRC = None
    _FRAG_SHADER_SRC = None

    def __init__(self,
                 font_file=os.path.join(_here, 'fonts', 'VeraMono.ttf'),
                 size=72*16):
        _logger.debug('loading %s...', font_file)
        self._font_file = font_file
        self._face = Face(font_file)
        self._face.set_char_size(size)
        width, max_asc, max_desc = 0, 0, 0
        widths = []
        for c in range(32, 128):
            self._face.load_char(chr(c), FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
            bitmap = self._face.glyph.bitmap
            width = max(width, bitmap.width)
            max_asc = max(max_asc, self._face.glyph.bitmap_top)
            max_desc = max(max_desc, bitmap.rows-self._face.glyph.bitmap_top)
            widths.append(bitmap.width)
        self._max_asc = max_asc
        self._widths = np.array(widths)
        self._width = width
        self._height = max_asc + max_desc
        self._read_shader_src()
        self._screen_size = (800.0, 600.0)
        self._texcoords = np.zeros((32, 2), dtype=np.float32)
        self._gl_initialized = False

    def set_screen_size(self, screen_size):
        self._screen_size = screen_size

    def init_gl(self):
        if self._gl_initialized:
            return
        import OpenGL.GL as gl
        self._texture_unit = 4
        vs_id = gl.glCreateShader(gl.GL_VERTEX_SHADER)
        gl.glShaderSource(vs_id, self._VERT_SHADER_SRC)
        gl.glCompileShader(vs_id)
        if not gl.glGetShaderiv(vs_id, gl.GL_COMPILE_STATUS):
            raise Exception('failed to compile %s vertex shader:\n%s' %
                            (self.__class__.__name__, gl.glGetShaderInfoLog(vs_id).decode()))
        fs_id = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
        gl.glShaderSource(fs_id, self._FRAG_SHADER_SRC)
        gl.glCompileShader(fs_id)
        if not gl.glGetShaderiv(fs_id, gl.GL_COMPILE_STATUS):
            raise Exception('failed to compile %s fragment shader:\n%s' %
                            (self.__class__.__name__, gl.glGetShaderInfoLog(fs_id).decode()))
        self._program_id = gl.glCreateProgram()
        gl.glAttachShader(self._program_id, vs_id)
        gl.glAttachShader(self._program_id, fs_id)
        gl.glLinkProgram(self._program_id)
        gl.glDetachShader(self._program_id, vs_id)
        gl.glDetachShader(self._program_id, fs_id)
        if not gl.glGetProgramiv(self._program_id, gl.GL_LINK_STATUS):
            raise Exception('failed to link program for %s' % self.__class__.__name__)
        self._attribute_locations = {attribute: gl.glGetAttribLocation(self._program_id, attribute)
                                     for attribute in self._ATTRIBUTES}
        self._uniform_locations = {uniform: gl.glGetUniformLocation(self._program_id, uniform)
                                   for uniform in self._UNIFORMS}
        width, height = self._width, self._height
        self._image_width, self._image_height = image_width, image_height = width * 16, height * 6
        bitmap_buffer = np.zeros((image_height, image_width), dtype=np.ubyte)
        self._char_to_texcoords = {}
        for j in range(6):
            for i in range(16):
                i_char = j * 16 + i
                char = chr(32 + i_char)
                self._char_to_texcoords[char] = (i / 16.0, j / 6.0)
                self._face.load_char(char, FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
                glyph = self._face.glyph
                bitmap = glyph.bitmap
                x = i*width + glyph.bitmap_left
                y = j*height + self._max_asc - glyph.bitmap_top
                bitmap_buffer[y:y+bitmap.rows,x:x+bitmap.width].flat = bitmap.buffer
        self._texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        self._sampler_id = gl.glGenSamplers(1)
        gl.glSamplerParameteri(self._sampler_id, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glSamplerParameteri(self._sampler_id, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glSamplerParameteri(self._sampler_id, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glSamplerParameteri(self._sampler_id, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glBindSampler(self._texture_unit, self._sampler_id)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0,
                        gl.GL_RED,
                        image_width, image_height, 0,
                        gl.GL_RED, gl.GL_UNSIGNED_BYTE,
                        bitmap_buffer)
        gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        if gl.glGetError() != gl.GL_NO_ERROR:
            raise Exception('failed to create font texture')
        self._gl_initialized = True
        _logger.debug('%s.init_gl: OK', self.__class__.__name__)

    def draw_text(self, text,
                  color=(1.0, 1.0, 0.0, 0.0),
                  screen_position=(0.0, 0.0)):
        import OpenGL.GL as gl
        gl.glUseProgram(self._program_id)
        gl.glActiveTexture(gl.GL_TEXTURE0+self._texture_unit)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture_id)
        #gl.glBindSampler(tex_unit, self._sampler_id)
        gl.glUniform1i(self._uniform_locations['u_fonttex'], self._texture_unit)
        gl.glUniform4f(self._uniform_locations['u_color'], *color)
        gl.glUniform2f(self._uniform_locations['u_screen_size'], *self._screen_size)
        gl.glUniform2f(self._uniform_locations['u_char_size'], self._width, self._height)
        gl.glUniform2f(self._uniform_locations['u_screen_position'], *screen_position)
        gl.glUniform2f(self._uniform_locations['u_fonttex_size'], self._image_width, self._image_height)
        nchars = len(text)
        gl.glUniform1ui(self._uniform_locations['u_nchars'], nchars)
        self._texcoords[:nchars] = [self._char_to_texcoords[c] for c in text]
        gl.glUniform2fv(self._uniform_locations['u_texcoords'], nchars, self._texcoords)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        gl.glDisable(gl.GL_BLEND)

    def save_image(self, filename=None):
        from PIL import Image
        if filename is None:
            filename = os.path.split_ext(os.path.basename(self._font_file))[0] + '.png'
        _logger.debug('filename = %s', filename)
        width, height = self._width, self._height
        image_width, image_height = width * 16, height * 6
        bitmap_buffer = np.zeros((image_height, image_width), dtype=np.ubyte)
        for j in range(6):
            for i in range(16):
                i_char = j * 16 + i
                char = chr(32 + i_char)
                self._face.load_char(char, FT_LOAD_RENDER | FT_LOAD_FORCE_AUTOHINT)
                glyph = self._face.glyph
                bitmap = glyph.bitmap
                x = i*width + glyph.bitmap_left
                y = j*height + self._max_asc - glyph.bitmap_top
                bitmap_buffer[y:y+bitmap.rows,x:x+bitmap.width].flat = bitmap.buffer
        image = Image.new('L', (bitmap_buffer.shape[1], bitmap_buffer.shape[0]))
        image.putdata(list(bitmap_buffer.ravel()))
        image.save(filename)
        _logger.info('...saved to %s', filename)

    @classmethod
    def _read_shader_src(cls):
        if cls._VERT_SHADER_SRC is None:
            with open(cls._VERT_SHADER_SRC_PATH) as f:
                cls._VERT_SHADER_SRC = f.read()
            attr_matches = _ATTRIBUTE_DECL_RE.finditer(cls._VERT_SHADER_SRC)
            attributes = []
            for m in attr_matches:
                attributes.append(m['attribute_name'])
            cls._ATTRIBUTES = attributes
        if cls._FRAG_SHADER_SRC is None:
            with open(cls._FRAG_SHADER_SRC_PATH) as f:
                cls._FRAG_SHADER_SRC = f.read()
            unif_matches = _UNIFORM_DECL_RE.finditer(cls._FRAG_SHADER_SRC)
            uniforms = []
            for m in unif_matches:
                uniforms.append(m['uniform_name'])
            cls._UNIFORMS = uniforms



if __name__ == "__main__":
    import cyglfw3 as glfw
    _DEBUG_LOGGING_FORMAT = '%(asctime).19s [%(levelname)s]%(name)s.%(funcName)s:%(lineno)d: %(message)s'
    logging.basicConfig(format=_DEBUG_LOGGING_FORMAT, level=logging.DEBUG)
    opengl_logger = logging.getLogger('OpenGL')
    opengl_logger.setLevel(logging.INFO)
    pil_logger = logging.getLogger('PIL')
    pil_logger.setLevel(logging.WARNING)
    text_drawer = TextRenderer()
    glfw.Init()
    w, h = 800, 600
    window = glfw.CreateWindow(w, h, os.path.basename(__file__))
    glfw.MakeContextCurrent(window)
    gl.glClearColor(0.1, 0.1, 0.2, 0.0)
    text_drawer.init_gl()
    def on_keydown(window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.SetWindowShouldClose(window, gl.GL_TRUE)
    glfw.SetKeyCallback(window, on_keydown)
    def on_resize(window, width, height):
        gl.glViewport(0, 0, width, height)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        text_drawer.set_screen_size((width, height))
    glfw.SetWindowSizeCallback(window, on_resize)
    on_resize(window, w, h)
    _logger.debug('starting render loop...')
    nframes = 0
    dt = float('inf')
    avg_fps = 0.0
    t = lt = st = glfw.GetTime();
    while not glfw.WindowShouldClose(window):
        glfw.PollEvents()
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        text_drawer.draw_text('TESTING123', screen_position=(0.5, 0.5))
        text_drawer.draw_text('fps: %f' % (1.0 / dt),
                              screen_position=(abs(np.sin(0.01 * (t - st))),
                                               abs(np.sin(0.1 * (t - st)))))
        text_drawer.draw_text('avg fps: %f' % avg_fps,
                              screen_position=(abs(np.sin(0.07 * (t - st))),
                                               abs(np.cos(0.3 * (t - st)))),
                              color=(1.0, 0.0, 0.0, 0.0))
        glfw.SwapBuffers(window)
        t = glfw.GetTime(); dt = t - lt; lt = t
        nframes += 1
        avg_fps = nframes / (t - st)
    _logger.debug('avg fps: %f', avg_fps)
    glfw.DestroyWindow(window)
    glfw.Terminate()
