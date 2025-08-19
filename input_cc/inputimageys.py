import pickle
import cv2
import requests
import json
import subprocess
import base64
import os
import numpy as np
from requests.exceptions import Timeout, RequestException, ConnectionError
from dotenv import load_dotenv
load_dotenv()

# 1. Setup OpenFaaS connection
def setup_openfaas():
    try:
        with open("/dev/null", "w") as nullfile:
            login_script = os.getenv("LOGIN_SCRIPT_SERVER")
            subprocess.run(["sudo", "/bin/bash", login_script],
                         check=True, stdout=nullfile, stderr=nullfile)
        print("OpenFaaS connection established successfully.")
        return True
    except subprocess.CalledProcessError:
        print("Error: Unable to connect to OpenFaaS server.")
        return False

# 2. Load and prepare image
def prepare_image(img_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not load image at {img_path}")
        return None
    
    try:
        return pickle.dumps(img)
    except Exception as e:
        print(f"Image processing error: {e}")
        return None

# 3. Process and display results
def process_results(original_img, result):
    if 'status' in result and result['status'] == 'error':
        print(f"Server error: {result.get('message', 'Unknown error')}")
        return False
    
    if 'detections' in result:
        # Draw bounding boxes
        for detection in result['detections']:
            x1, y1, x2, y2 = map(int, detection['bbox'])
            cv2.rectangle(original_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(original_img, f"Person {detection['confidence']:.2f}",
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        
        print(f"Processing time: {response.elapsed.total_seconds():.2f}s")
        print(f"Persons detected: {len(result['detections'])}")
        return original_img
    
    elif 'processed_image' in result:
        img_data = base64.b64decode(result['processed_image'])
        img_array = np.frombuffer(img_data, dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    return None

# Main execution
if __name__ == "__main__":
    if not setup_openfaas():
        exit(1)

    url = os.getenv("OPENFAAS_URL_SERVER")
    openfaas_url = url + "/function/crowdcountyolox"
    img_path = os.getenv("BUS_IMAGE_PATH")

    # Prepare image data
    imdata = prepare_image(img_path)
    if imdata is None:
        exit(1)

    # Create request payload
    json_data = json.dumps({
        "image_data": {
            "image": base64.b64encode(imdata).decode('ascii')
        }
    })

    # Send request and handle response
    # 4. Send request and process response
    try:
        response = requests.post(openfaas_url, 
                            data=json_data, 
                            timeout=30,
                            headers={'Content-Type': 'application/json'})
        
        # Debug raw response
        #print(f"Raw response: {response.text}")  # Add this for troubleshooting
        
        response.raise_for_status()
        #print(f"Count of persons: {response['count']}")
        try:
            result = response.json()
            print(f"Count: {result['count']}")
            print(f"Response time: {response.elapsed.total_seconds()} seconds")
        except json.JSONDecodeError:
            print("Error: Server returned invalid JSON")
            print(f"Response content: {response.content}")
            exit(1)
        """
        output_img = process_results(original_img, result)
        if output_img is not None:
            cv2.imshow('Detection Results', output_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            cv2.imwrite('detection_output.jpg', output_img)
        """
    except Timeout:
        print("Error: Request timed out after 30 seconds")
    except ConnectionError as e:
        print(f"Connection error: {e}")
    except RequestException as e:
        print(f"Request failed: {e}")
    except json.JSONDecodeError:
        print("Error: Invalid server response")
    except Exception as e:
        print(f"Unexpected error: {e}")