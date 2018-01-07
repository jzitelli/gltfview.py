#!/bin/env python
from setuptools import setup
from codecs import open
from os import path, listdir

here = path.dirname(path.abspath(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='gltfview.py',
    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.1.0',
    description='utilities for rendering and viewing 3D scenes / models stored in the GL Transmission Format (glTF) file-format',
    packages=['gltfutils'],
    long_description=long_description,
    url='https://github.com/jzitelli/gltfview.py',
    author='Jeffrey Zitelli',
    author_email='jeffrey.zitelli@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    keywords='virtual reality opengl gltf python pyopengl pyopenvr openvr vr vive',
    install_requires=['numpy', 'pyopengl', 'pillow'], #'cyglfw3'
    extras_require={'gltfutils': ['openvr']},
    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={'gltfutils': [path.join('shaders', filename)
                                for filename in listdir(path.join('gltfutils', 'shaders'))
                                if filename.endswith('.glsl')]},
    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    data_files=[],
    scripts=['scripts/gltfview.py'],
    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    entry_points={}
)
