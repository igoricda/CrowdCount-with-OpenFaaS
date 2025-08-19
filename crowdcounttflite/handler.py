from ultralytics import YOLO
import pickle
import json
import base64
import os
from ultralytics.utils import LOGGER
import logging
import cv2
import numpy as np
import sys

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"       # Disable OneDNN probing
os.environ["TFLITE_ENABLE_XNNPACK"] = "1"       # Force-enable XNNPACK delegate
os.environ["TFLITE_USE_CUDA"] = "0"             # Prevent GPU probing if installed

# Suppress warnings and logs
os.environ['YOLO_CONFIG_DIR'] = '/tmp/Ultralytics'
os.environ['YOLO_VERBOSE'] = 'False'
LOGGER.setLevel(logging.ERROR)
#LOGGER.setLevel(logging.WARNING)  # or logging.ERROR to suppress more
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)
# Load model once (avoid reloading on every request)
#model_path = "/home/app/function/yolov8n_saved_model/yolov8n_float16.tflite"
model_path = "/home/app/function/tflitey8/yolov8n_float16.tflite"
model = YOLO(model_path, task="detect")  # Load the YOLO model

def handle(req):
    try:
        data = json.loads(req)
        img_data = base64.b64decode(data["image_data"]["image"])
        img = pickle.loads(img_data)
        if len(img.shape) == 2:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # Detect only people (class 0)
        results = model(img, classes=[0], conf=0.5, verbose=False)
        count = sum(len(result.boxes) for result in results)

        return json.dumps({
            "status": "success",
            "count": count
        })
    
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        })
