#!/bin/bash

for i in $(seq $2 $3)
do
    if [[ ! -d ../../ANALYSIS/ReconstructionTracks_from3to4/config/ped$1/ped_run$i ]]
    then
	mkdir "../../ANALYSIS/ReconstructionTracks_from3to4/config/ped$1/ped_run$i"
	source MURAVES_PedestalAnalysis.sh $1 $i $i
    else
	if [ ! -f ../../ANALYSIS/ReconstructionTracks_from3to4/config/ped$1/ped_run$i/pedestal_0.cfg ];
	then
	    mkdir "../../ANALYSIS/ReconstructionTracks_from3to4/config/ped$1/ped_run$i"
	    source MURAVES_PedestalAnalysis.sh $1 $i $i
	fi
    fi
    
    
    
    PYTHONPATH=.  ./MURAVES_reco_v2.exe $1 $i
done
