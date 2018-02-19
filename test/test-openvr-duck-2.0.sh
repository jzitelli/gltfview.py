#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/2.0/Duck/gltf/Duck.gltf
echo 'loading file' ${filename} '...'
gltfview.py -v --openvr ${filename} 2>&1 | tee -a test-openvr-duck-2.0.log
