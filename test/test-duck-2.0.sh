#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/2.0/Duck/gltf/Duck.gltf
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} -s screenshots/test-duck-2.0.png 2>&1 | tee -a test-duck-2.0.log
