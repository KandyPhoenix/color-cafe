#!/bin/bash
# Parameter sweep. Each run writes out/<tag>.json; --save-all also writes images.
IMG=/home/user/puzzle-parlor/public/img
P=python3
cd "$(dirname "$0")"
( $P segment.py $IMG/haunted-village.jpg --n 36 --smooth bilateral --min-area 400 --min-radius 6 --save-all
  $P segment.py $IMG/haunted-village.jpg --n 24 --smooth none --min-area 400 --min-radius 6
  $P segment.py $IMG/haunted-village.jpg --n 24 --smooth bilateral --min-area 1600 --min-radius 10 --save-all ) > out/log_a.txt 2>&1 &
( $P segment.py $IMG/haunted-village.jpg --n 24 --smooth meanshift --min-area 400 --min-radius 6
  $P segment.py $IMG/haunted-village.jpg --n 36 --smooth bilateral --min-area 900 --min-radius 8 --save-all
  $P segment.py $IMG/haunted-village.jpg --n 36 --smooth bilateral --min-area 1600 --min-radius 10 ) > out/log_b.txt 2>&1 &
( $P segment.py $IMG/witch-kitchen.jpg --n 24 --smooth bilateral --min-area 400 --min-radius 6 --save-all
  $P segment.py $IMG/witch-kitchen.jpg --n 36 --smooth bilateral --min-area 900 --min-radius 8 --save-all
  $P segment.py $IMG/witch-kitchen.jpg --n 36 --smooth bilateral --min-area 400 --min-radius 6 ) > out/log_c.txt 2>&1 &
wait
echo MATRIX DONE
