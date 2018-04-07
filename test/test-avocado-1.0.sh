#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/1.0/Avocado/glTF/Avocado.gltf
logdir=logs
mkdir -p $logdir
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} \
       -s screenshots/test-avocado-1.0.png \
       --camera-position="0,3,10" 2>&1 | tee -a $logdir/test-avocado-1.0.log
