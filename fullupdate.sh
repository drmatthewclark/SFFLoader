#!/bin/bash -x
# download latest rmc dataset
echo -n "sff "
source update.sh 
update $sff_download $sff

cd ${release}
eval "$(conda shell.bash hook)"
conda activate standard
time python ../SFFLoader/readsdfiles.py

cd ..

del() {
  shift
  for d in $*; do
	echo 'removing dataset' $d
	rm -r "${d}"
  done

}

dirs=`ls -dc 2[0-9]*`
del ${dirs}
