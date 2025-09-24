#!/bin/bash
for i in $(seq $2 $3)
do
    PYTHONPATH=. ./OnePhe_evaluator.exe $1 $i
done
