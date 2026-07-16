#!/bin/bash
# camera_process.sh — runs YOLO detection through camera calibration
# Usage: ./camera_process.sh 20260713_191320 [--skip-yolo] [--skip-missing] [--skip-multi] [--skip-depth] [--skip-calib]

if [ -z "$1" ]; then
    echo "Usage: ./camera_process.sh <DATETIME> [--skip-yolo] [--skip-missing] [--skip-multi] [--skip-depth] [--skip-calib]"
    exit 1
fi

DATETIME=$1
shift  # remaining args are flags

RUN_DIR=$(ls -d ../data/*${DATETIME} 2>/dev/null | head -n 1)
if [ -z "$RUN_DIR" ]; then
    echo "ERROR: no dataset folder found matching *${DATETIME}"
    exit 1
fi

GT_CSV="../data/headway_csv/headway_log_${DATETIME}.csv"
IMAGES_DIR="${RUN_DIR}/processed_camera/images"
CAM_DIR="${RUN_DIR}/processed_camera"

REPORT_DIR="${RUN_DIR}/processed_camera/reports"
mkdir -p "$REPORT_DIR"
REPORT_FILE="${REPORT_DIR}/report_${DATETIME}.txt"

# flags default to "run everything" unless explicitly skipped
SKIP_YOLO=false; SKIP_MISSING=false; SKIP_MULTI=false; SKIP_DEPTH=false; SKIP_CALIB=false
for arg in "$@"; do
    case $arg in
        --skip-yolo)    SKIP_YOLO=true ;;
        --skip-missing) SKIP_MISSING=true ;;
        --skip-multi)   SKIP_MULTI=true ;;
        --skip-depth)   SKIP_DEPTH=true ;;
        --skip-calib)   SKIP_CALIB=true ;;
    esac
done

echo "=====================================================" | tee -a "$REPORT_FILE"
echo " Camera pipeline for: $RUN_DIR  ($(date))" | tee -a "$REPORT_FILE"
echo "=====================================================" | tee -a "$REPORT_FILE"

if [ "$SKIP_YOLO" = false ]; then
    echo "[1/5] YOLOv8 detection..." | tee -a "$REPORT_FILE"
    python3 camera/yolo_detection.py --frames_dir "$IMAGES_DIR" --conf_thresh 0.3 --exclude_bottom_px 40 2>&1 | tee -a "$REPORT_FILE"
else
    echo "[1/5] SKIPPED (yolo)" | tee -a "$REPORT_FILE"
fi

if [ "$SKIP_MISSING" = false ]; then
    echo "[2/5] Missing leader frame check..." | tee -a "$REPORT_FILE"
    python3 camera/missing_leader_frame.py --camera_dir "$CAM_DIR" 2>&1 | tee -a "$REPORT_FILE"
else
    echo "[2/5] SKIPPED (missing frame check)" | tee -a "$REPORT_FILE"
fi

if [ "$SKIP_MULTI" = false ]; then
    echo "[3/5] Multi-vehicle frame check..." | tee -a "$REPORT_FILE"
    python3 camera/find_multi_car_frame.py --camera_dir "$CAM_DIR" 2>&1 | tee -a "$REPORT_FILE"
else
    echo "[3/5] SKIPPED (multi-car check)" | tee -a "$REPORT_FILE"
fi

if [ "$SKIP_DEPTH" = false ]; then
    echo "[4/5] ZoeDepth headway estimation..." | tee -a "$REPORT_FILE"
    python3 camera/camera_headway_estimation.py --camera_dir "$CAM_DIR" 2>&1 | tee -a "$REPORT_FILE"
else
    echo "[4/5] SKIPPED (depth estimation)" | tee -a "$REPORT_FILE"
fi

if [ "$SKIP_CALIB" = false ]; then
    echo "[5/5] Camera calibration..." | tee -a "$REPORT_FILE"
    python3 camera/camera_calibrate.py \
        --gt_csv "$GT_CSV" --cam_dir "$CAM_DIR" \
        --gt_time_col timestamp --gt_dist_col gt_headway_m 2>&1 | tee -a "$REPORT_FILE"
else
    echo "[5/5] SKIPPED (calibration)" | tee -a "$REPORT_FILE"
fi

echo "=====================================================" | tee -a "$REPORT_FILE"
echo " Camera pipeline done. Report: $REPORT_FILE" | tee -a "$REPORT_FILE"
echo "=====================================================" | tee -a "$REPORT_FILE"
