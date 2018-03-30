#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/1.0/Avocado/glTF/Avocado.gltf
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} -s screenshots/test-avocado-1.0.png 2>&1 | tee -a test-avocado-1.0.log
