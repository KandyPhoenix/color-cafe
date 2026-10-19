#!/bin/bash
# Third sweep: strong smoothing + post-merge split of regions over 3% of the image.
IMG=/home/user/puzzle-parlor/public/img
P=python3
cd "$(dirname "$0")"
( $P segment.py $IMG/haunted-village.jpg --n 24 --smooth strong --min-area 900 --min-radius 8 --max-share-region 0.03 --save-all
  $P segment.py $IMG/haunted-village.jpg --n 36 --smooth strong --min-area 900 --min-radius 8 --max-share-region 0.03 --save-all ) > out/log_g.txt 2>&1 &
( $P segment.py $IMG/witch-kitchen.jpg --n 24 --smooth strong --min-area 900 --min-radius 8 --max-share-region 0.03 --save-all
  $P segment.py $IMG/witch-kitchen.jpg --n 36 --smooth strong --min-area 900 --min-radius 8 --max-share-region 0.03 --save-all ) > out/log_h.txt 2>&1 &
wait; echo MATRIX3 DONE
