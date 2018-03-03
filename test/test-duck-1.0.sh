#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/1.0/Duck/gltf/Duck.gltf
echo 'loading file' ${filename} '...'
gltfview.py -v $@ ${filename} 2>&1 | tee -a test-duck-1.0.log
