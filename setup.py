#!/bin/env python
from setuptools import setup
from codecs import open
from os import path, listdir

here = path.dirname(path.abspath(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='gltfview.py',
    version='0.1.0',
    description='utilities for rendering and viewing 3D scenes / models stored in the GL Transmission Format (glTF) file-format',
    packages=['gltfutils', 'gltfview', 'gl_rendering'],
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
    install_requires=[
        'numpy',
        'pillow',
        'pyopengl',
        'pyopengl-accelerate',
        #'cyglfw3'
    ],
    extras_require={'gltfutils': ['openvr']},
    package_data={
        'gltfutils': [path.join('shaders', filename)
                      for filename in listdir(path.join('gltfutils', 'shaders'))
                      if filename.endswith('.glsl')],
        'gl_rendering': [path.join('shaders', filename)
                         for filename in listdir(path.join('gl_rendering', 'shaders'))
                         if filename.endswith('.glsl')] +
                        [path.join('fonts', 'VeraMono.ttf')]
    },
    data_files=[],
    entry_points={
        'console_scripts': [
            'gltfview = gltfview.__main__:main'
        ]
    }
)
