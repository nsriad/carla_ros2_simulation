#!/bin/bash
# run_all.sh — full pipeline orchestrator
# Usage: ./run_all.sh 20260713_191320 [--skip-parse] [--skip-post] [--skip-camera] [--skip-headway] [--camera-args="--skip-yolo"]

if [ -z "$1" ]; then
    echo "Usage: ./run_all.sh <DATETIME> [--skip-parse] [--skip-post] [--skip-camera] [--skip-headway]"
    exit 1
fi

DATETIME=$1
shift

SKIP_PARSE=false; SKIP_POST=false; SKIP_CAMERA=false; SKIP_HEADWAY=false
CAMERA_ARGS=""
for arg in "$@"; do
    case $arg in
        --skip-parse)   SKIP_PARSE=true ;;
        --skip-post)    SKIP_POST=true ;;
        --skip-camera)  SKIP_CAMERA=true ;;
        --skip-headway) SKIP_HEADWAY=true ;;
        --camera-args=*) CAMERA_ARGS="${arg#*=}" ;;
    esac
done

[ "$SKIP_PARSE" = false ]   && ./parse_data.sh "$DATETIME"
[ "$SKIP_POST" = false ]    && ./post_process.sh "$DATETIME"
[ "$SKIP_CAMERA" = false ]  && ./camera_process.sh "$DATETIME" $CAMERA_ARGS
[ "$SKIP_HEADWAY" = false ] && python3 headway_analysis.py "$DATETIME"

echo "Pipeline finished for $DATETIME"
