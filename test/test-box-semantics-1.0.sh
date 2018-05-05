#!/usr/bin/bash
filename=BoxSemantics.gltf
dir=~/GitHub/glTF-Sample-Models/1.0/${filename:0:-5}/glTF
log_dir=logs
screenshots_dir=screenshots
mkdir -p $log_dir
test_name=`basename ${BASH_SOURCE[-1]}`
echo "$test_name: loading file $dir/$filename ..."
python ../gltfview/__main__.py -v $@ $dir/$filename \
       -s $screenshots_dir/${test_name:0:-3}.png 2>&1 | tee -a $log_dir/${test_name:0:-3}.log
