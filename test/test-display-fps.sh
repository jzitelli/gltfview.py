#!/usr/bin/bash
filename=~/GitHub/glTF-Sample-Models/2.0/Duck/gltf/Duck.gltf
logdir=logs
test_name=`basename ${BASH_SOURCE[-1]}`
mkdir -p $logdir
echo 'loading file' ${filename} '...'
python ../gltfview/__main__.py -v $@ ${filename} \
       -s screenshots/${test_name:0:-3}.png --display-fps 2>&1 | tee -a $logdir/${test_name:0:-3}.log
