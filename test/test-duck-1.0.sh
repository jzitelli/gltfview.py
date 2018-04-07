#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/1.0/Duck/gltf/Duck.gltf
logdir=logs
mkdir -p $logdir
echo 'loading file' $filename '...'
python ../gltfview/__main__.py -v $@ $filename \
       -s screenshots/test-duck-1.0.png 2>&1 | tee -a $logdir/test-duck-1.0.log
