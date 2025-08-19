from ultralytics import YOLO
import pickle
import json
import base64
import os
from ultralytics.utils import LOGGER
import logging

# Suppress warnings and logs
os.environ['YOLO_CONFIG_DIR'] = '/tmp/Ultralytics'
os.environ['YOLO_VERBOSE'] = 'False'
LOGGER.setLevel(logging.ERROR)

# Load model once (avoid reloading on every request)
model = YOLO("./yolo11n.pt")

def handle(req):
    try:
        data = json.loads(req)
        img_data = base64.b64decode(data["image_data"]["image"])
        img = pickle.loads(img_data)

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
