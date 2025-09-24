#!/bin/bash

for i in `seq $2 $3`; do
    echo $i
root -l <<EOF  
.L AnalysisOfCluster_and_tracks4planes.C
AnalysisOfCluster_and_tracks4planes F("$1",$i)
F.Loop("$1",$i)
EOF
python3 CheckFile.py $1 $i
done    
