#!/usr/bin/bash

filename=~/GitHub/glTF-Sample-Models/2.0/Duck/gltf/Duck_working.gltf

echo 'loading file' ${filename} '...'
gltfview.py -v ${filename} 2>&1 | tee -a test-duck-2.0.log
