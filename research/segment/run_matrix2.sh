#!/bin/bash
# Second sweep: adaptive split of over-sized palette colours (--max-share) + stronger smoothing.
IMG=/home/user/puzzle-parlor/public/img
P=python3
cd "$(dirname "$0")"
( $P segment.py $IMG/haunted-village.jpg --n 24 --smooth bilateral --min-area 900 --min-radius 8 --max-share 0.12 --save-all
  $P segment.py $IMG/haunted-village.jpg --n 24 --smooth strong --min-area 900 --min-radius 8 --max-share 0.12 --save-all ) > out/log_d.txt 2>&1 &
( $P segment.py $IMG/haunted-village.jpg --n 36 --smooth bilateral --min-area 900 --min-radius 8 --max-share 0.12 --save-all
  $P segment.py $IMG/witch-kitchen.jpg --n 36 --smooth bilateral --min-area 900 --min-radius 8 --max-share 0.12 --save-all ) > out/log_e.txt 2>&1 &
( $P segment.py $IMG/witch-kitchen.jpg --n 24 --smooth bilateral --min-area 900 --min-radius 8 --max-share 0.12 --save-all
  $P segment.py $IMG/witch-kitchen.jpg --n 24 --smooth strong --min-area 900 --min-radius 8 --max-share 0.12 --save-all ) > out/log_f.txt 2>&1 &
wait; echo MATRIX2 DONE
