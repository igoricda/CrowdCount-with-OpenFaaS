import pickle
import cv2
import requests
import json
import subprocess
import base64
import numpy as np
import os
import re
from requests.exceptions import Timeout, RequestException, ConnectionError
from dotenv import load_dotenv
load_dotenv()

def setup_openfaas():
    try:
        with open("/dev/null", "w") as nullfile:
            login_script = os.getenv("LOGIN_SCRIPT_RASPBERRYPI")  # Using RASP for this server
            subprocess.run(["sudo", "/bin/bash", login_script], 
                         check=True, stdout=nullfile, stderr=nullfile)
        print("OpenFaaS connection established successfully.")
        return True
    except subprocess.CalledProcessError:
        print("Error: Unable to connect to OpenFaaS server.")
        return False

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

if __name__ == "__main__":
    if not setup_openfaas():
        exit(1)
    url = os.getenv("OPENFAAS_URL_RASPBERRYPI")
    openfaas_url = url + "/function/crowdcountyolo"

    img_path = os.getenv("BUS_IMAGE_PATH")

    imdata = prepare_image(img_path)
    if imdata is None:
        exit(1)

    json_data = json.dumps({
        "image_data": {
            "image": base64.b64encode(imdata).decode('ascii')
        }
    })
    
    try:
        response = requests.post(openfaas_url, data=json_data, timeout=300, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        #print("Raw response:", response.content)
        try:
            result = response.json()
        except json.JSONDecodeError:
            matches = re.findall(rb'({.*})', response.content)
            if matches:
                result = json.loads(matches[-1].decode())
            else:
                print("Error: No JSON object found in response.")
                print("Raw response:", response.content)
                exit(1)

        print(f"Count: {result['count']}")
        print(f"Response time: {response.elapsed.total_seconds()} seconds")
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
        print("Raw response:", response.content)
   # print("Elapsed time:", response.elapsed.total_seconds(), "seconds")