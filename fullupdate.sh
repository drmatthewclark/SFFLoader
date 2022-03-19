#!/bin/bash
# download latest  dataset

loader="SFFLoader"

source update.sh 
source ./${loader}/credentials.py
echo ${message} 
update ${download} ${dataset}

if [ "${success}" =  "no" ]; then
	echo "end load"
	exit 1;
fi

cd ${release}
eval "$(conda shell.bash hook)"
conda activate standard
time python ../${loader}/readsdfiles.py

cd ..

del() {
  shift
  for d in $*; do
	if [ ! "${d}" == "${release}" ]; then
	  echo 'removing dataset' $d
 	  rm -r "${d}"
	fi
  done

}

dirs=`ls -dc 2[0-9]*`
del ${dirs}

