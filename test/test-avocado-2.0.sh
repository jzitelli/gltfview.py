#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/2.0/Avocado/glTF/Avocado.gltf
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} \
       -s screenshots/test-avocado-2.0.png \
       --camera-position="-0.0996, -0.025, 0.082" \
       --camera-rotation="0, 0.64, 0" 2>&1 | tee -a logs/test-avocado-2.0.log
