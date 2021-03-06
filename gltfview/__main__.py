from sys import exit
import os.path
import json
import argparse
import logging
_logger = logging.getLogger(__name__)
_LOGGING_FORMAT = '%(name)s.%(funcName)s[%(levelname)s]: %(message)s'
_DEBUG_LOGGING_FORMAT = '%(asctime).19s [%(levelname)s]%(name)s.%(funcName)s:%(lineno)d: %(message)s'


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename',
                        help='path of glTF file to view')
    parser.add_argument("-v", '--verbose',
                        help="enable verbose logging",
                        action="store_true")
    parser.add_argument("--uri_prefix",
                        help='prefix for relative path URIs (defaults to the directory of the glTF file)',
                        default=None)
    parser.add_argument("-a", "--msaa", metavar='A',
                        help='enable multi-sampled anti-aliasing (disabled by default) at level A (1, 2, or 4)',
                        default=0)
    parser.add_argument("--openvr",
                        help="view in VR",
                        action="store_true")
    parser.add_argument('-w', "--wireframe",
                        help="(TODO) view in wireframe mode",
                        action="store_true")
    parser.add_argument('-n', '--nframes', metavar='N',
                        help="exit after rendering N number of frames",
                        default=None)
    parser.add_argument('-s', '--screenshot',
                        help='save a screenshot',
                        default=None)
    parser.add_argument('--camera-position',
                        help='position of the camera in world space',
                        default=None)
    parser.add_argument('--camera-rotation',
                        help='rotation of the camera (specified in Euler angles) in world space',
                        default=None)
    parser.add_argument('--display-fps',
                        help='display realtime FPS',
                        action='store_true')
    args = parser.parse_args()
    if args.uri_prefix is None:
        args.uri_prefix = os.path.dirname(args.filename)
    if args.nframes is not None:
        try:
            args.nframes = int(args.nframes)
        except TypeError:
            _logger.error('%s is an invalid value for nframes', args.nframes)
            exit(1)
    if args.camera_position is not None:
        try:
            args.camera_position = tuple(float(x.strip()) for x in args.camera_position.split(','))
        except Exception as err:
            _logger.error('%s is an invalid value for camera-position', args.camera_position)
            exit(1)
    if args.camera_rotation is not None:
        try:
            args.camera_rotation = tuple(float(x.strip()) for x in args.camera_rotation.split(','))
        except Exception as err:
            _logger.error('%s is an invalid value for camera-rotation', args.camera_rotation)
            exit(1)
    return args


def main():
    args = parse_args()
    if args.verbose:
        logging.basicConfig(format=_DEBUG_LOGGING_FORMAT, level=logging.DEBUG)
        opengl_logger = logging.getLogger('OpenGL')
        opengl_logger.setLevel(logging.INFO)
        pil_logger = logging.getLogger('PIL')
        pil_logger.setLevel(logging.WARNING)
    else:
        logging.basicConfig(format=_LOGGING_FORMAT, level=logging.INFO)
    if args.openvr:
        _logger.info('will try viewing using OpenVR...')
    try:
        gltf = json.loads(open(args.filename).read())
        _logger.info('loaded "%s"', args.filename)
    except Exception as err:
        _logger.error('failed to load "%s":\n%s', args.filename, err)
        exit(1)
    from gltfutils.glfwutils import view_gltf
    view_gltf(gltf, args.uri_prefix,
              openvr=args.openvr,
              multisample=int(args.msaa),
              nframes=args.nframes,
              screenshot=args.screenshot,
              camera_position=args.camera_position,
              camera_rotation=args.camera_rotation,
              window_title='gltfview - %s' % os.path.split(args.filename)[-1],
              screen_capture_prefix=os.path.splitext(os.path.split(args.filename)[-1])[0],
              display_fps=args.display_fps)


if __name__ == "__main__":
    main()
