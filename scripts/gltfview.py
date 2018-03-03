#!python
from sys import exit
import os.path
import json
import argparse
import logging
_logger = logging.getLogger(__name__)
_LOGGING_FORMAT = '%(name)s.%(funcName)s[%(levelname)s]: %(message)s'
_DEBUG_LOGGING_FORMAT = '%(asctime).19s [%(levelname)s]%(name)s.%(funcName)s:%(lineno)d: %(message)s'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('filename',
                        help='path of glTF file to view')
    parser.add_argument("-v", '--verbose',
                        help="enable verbose logging",
                        action="store_true")
    parser.add_argument("--uri_prefix",
                        help='prefix for relative path URIs (defaults to the directory of the glTF file)',
                        default=None)
    parser.add_argument("-a", "--msaa",
                        help='enable multi-sample anti-aliasing (disabled by default) at the specified level (1, 2, or 4)',
                        default=0)
    parser.add_argument("--openvr",
                        help="view in VR",
                        action="store_true")
    parser.add_argument('-w', "--wireframe",
                        help="(TODO) view in wireframe mode",
                        action="store_true")
    parser.add_argument("--nframes",
                        help="exit after rendering specified number of frames",
                        default=None)
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format=_DEBUG_LOGGING_FORMAT, level=logging.DEBUG)
        opengl_logger = logging.getLogger('OpenGL')
        opengl_logger.setLevel(logging.INFO)
        pil_logger = logging.getLogger('PIL')
        pil_logger.setLevel(logging.ERROR)
    else:
        logging.basicConfig(format=_LOGGING_FORMAT, level=logging.INFO)

    if args.uri_prefix is not None:
        uri_prefix = args.uri_prefix
    else:
        uri_prefix = os.path.dirname(args.filename)

    nframes = args.nframes
    if nframes is not None:
        try:
            nframes = int(nframes)
        except TypeError:
            _logger.error('%s is an invalid value for nframes', nframes)
            exit(1)

    try:
        gltf = json.loads(open(args.filename).read())
        _logger.info('loaded "%s"', args.filename)
    except Exception as err:
        _logger.error('failed to load "%s":\n%s', args.filename, err)
        exit(1)

    from gltfutils.glfwutils import view_gltf

    view_gltf(gltf, uri_prefix, openvr=args.openvr,
              multisample=int(args.msaa),
              nframes=nframes)


if __name__ == "__main__":
    main()
