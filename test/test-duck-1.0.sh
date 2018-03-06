#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/1.0/Duck/gltf/Duck.gltf
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} 2>&1 | tee -a test-duck-1.0.log
