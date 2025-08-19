import pickle
import cv2
import requests
import json
import subprocess
import base64
import numpy as np
import re
import datetime
from requests.exceptions import Timeout, RequestException, ConnectionError
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import serial
import threading
import os
import time
from dotenv import load_dotenv
load_dotenv()

def read_serial_and_compute_energy(shared_data, data_lock, port='/dev/ttyUSB0', baudrate=115200):
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            #print(f"Connected to {port} at {baudrate} baud.")
            #print("Time (ms) | Current (mA) | Voltage (V) | Power (mW) | Energy (mWh)")
            #print("-" * 70)

            prev_time = None
            shared_data["total_mWh"] = 0.0
            while True:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                try:
                    timestamp_str, current_str, voltage_str = line.split(";")
                    timestamp = int(timestamp_str)
                    current = float(current_str)
                    voltage = float(voltage_str)
                    power = current * voltage  # mW

                    if prev_time is not None:
                        delta_ms = timestamp - prev_time
                        energy_mWh = (power * delta_ms) / 3600000  # mWh
                        with data_lock:
                            shared_data["total_mWh"] += energy_mWh

                    else:
                        delta_ms = 0
                        energy_mWh = 0

                    prev_time = timestamp

                    #print(f"{timestamp} | {current:.2f} mA | {voltage:.2f} V | {power:.2f} mW | {total_mWh:.6f} mWh")

                except ValueError:
                    continue

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except KeyboardInterrupt:
        print("\nStopped by user.")

# === Google Sheets Setup ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credential = os.getenv("GOOGLE_CREDENTIAL_FILE")
creds = ServiceAccountCredentials.from_json_keyfile_name(credential, scope)

client = gspread.authorize(creds)

# Open your Google Sheet by ID
sheet_key = os.getenv("GOOGLE_SHEET_KEY1")
sheet = client.open_by_key(sheet_key).sheet1

def get_next_free_column(worksheet, row):
    col = 1
    while worksheet.cell(row+3, col).value:
        col += 6
    return col 

def setup_openfaas():
    try:
        with open("/dev/null", "w") as nullfile:
            login_script = os.getenv("LOGIN_SCRIPT_TVBOX") # Using TVBOX for this server
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
    shared_data = {"total_mWh": 0.0}
    data_lock = threading.Lock()

    serial_thread = threading.Thread(
        target=read_serial_and_compute_energy,
        args=(shared_data, data_lock),
        daemon=True
    )
    serial_thread.start()
    image_list = [ "0p0f_0.jpg", "0p0f_1.jpg", "0p0f_2.jpg","0p0f_3.jpg", "0p0f_4.jpg",
                   "1p1f_0.jpg", "1p1f_1.jpg", "1p1f_2.jpg","1p1f_3.jpg", "1p1f_4.jpg",
                   "2p0f_0.jpg","2p1f_0.jpg","2p2f_0.jpg","2p2f_1.jpg", "2p2f_2.jpg",
                   "3p0f_0.jpg","3p2f_0.jpg","3p3f_0.jpg","3p3f_1.jpg","3p3f_2.jpg",
                   "4p1f_0.jpg","4p3f_0.jpg","4p3f_0.jpg", "4p3f_2.jpg", "4p4f_0.jpg",
                   "5p0f_0.jpg", "5p1f_0.jpg", "6p6f_0.jpg", "8p7f_0.jpg"]
    
    if not setup_openfaas():
        exit(1)
    openfaas_url = os.getenv("OPENFAAS_URL_TVBOX") + "/function/crowdcounttflite"
    start_row = 1
    flag = True
    try:
        col = get_next_free_column(sheet, start_row)
        if col == 25:
            raise IndexError
        flag = False
    except:
        start_row += 24
        flag = True
    
    while(flag):
        try:
            col = get_next_free_column(sheet, start_row)
            if col >= 24:
                raise IndexError
            flag = False
        except:
            start_row += 25
            flag = True
    for img_spec in image_list:
        directory = os.getenv("IMAGE_DIRECTORY")
        img_path = os.path.join(directory, img_spec)

        imdata = prepare_image(img_path)
        if imdata is None:
            exit(1)

        json_data = json.dumps({
            "image_data": {
                "image": base64.b64encode(imdata).decode('ascii')
            }
        })

        try:
            sheet.update_cell(start_row + 1, col, f"Run {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            sheet.update_cell(start_row + 2, col, f"Image: {img_spec}")
            sheet.update_cell(start_row + 3, col, "Iteration")
            sheet.update_cell(start_row + 3, col + 1, "Count")
            sheet.update_cell(start_row + 3, col + 2, "Elapsed Time")
            sheet.update_cell(start_row + 3, col + 3, "Energy Start")
            sheet.update_cell(start_row + 3, col + 4, "Energy End")
            sheet.update_cell(start_row + 3, col + 5, "Energy Request")
        except:
            time.sleep(61)
            sheet.update_cell(start_row + 1, col, f"Run {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            sheet.update_cell(start_row + 2, col, f"Image: {img_spec}")
            sheet.update_cell(start_row + 3, col, "Iteration")
            sheet.update_cell(start_row + 3, col + 1, "Count")
            sheet.update_cell(start_row + 3, col + 2, "Elapsed Time")
            sheet.update_cell(start_row + 3, col + 3, "Energy Start")
            sheet.update_cell(start_row + 3, col + 4, "Energy End")
            sheet.update_cell(start_row + 3, col + 5, "Energy Request")

        total_elapsed_time = 0
        times = []
        total_energy = 0
        energy = []

        n = 5
        for i in range(n):
            try:
                with data_lock:
                    current_energy = shared_data["total_mWh"]
                sheet.update_cell(start_row+4+i, col + 3, current_energy)
                energy_before = current_energy
                response = requests.post(openfaas_url, data=json_data, timeout=300, headers={'Content-Type': 'application/json'})
                response.raise_for_status()
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

                elapsed_time = response.elapsed.total_seconds()
                total_elapsed_time += elapsed_time
                times.append(elapsed_time)
                print(datetime.datetime.now().strftime('%H:%M:%S'))
                print(f"Iteration: {i}")
                print(f"Count: {result['count']}")
                print(f"Response time: {elapsed_time} seconds\n")
                with data_lock:
                    current_energy = shared_data["total_mWh"]
                energy_after = current_energy
                energy_request = energy_after - energy_before
                total_energy += energy_request
                energy.append(energy_request)

                try:
                    sheet.update_cell(start_row + 4 + i, col + 4, current_energy)
                    # Write data vertically in current column
                    sheet.update_cell(start_row + 4 + i, col, i + 1)  # Iteration
                    sheet.update_cell(start_row + 4 + i, col + 1, result['count'])  # Count
                    sheet.update_cell(start_row + 4 + i, col + 2, elapsed_time)  # Elapsed Time
                    sheet.update_cell(start_row + 4 + i, col + 5, energy_request)
                except:
                    time.sleep(60)
                    sheet.update_cell(start_row + 4 + i, col + 4, current_energy)
                    # Write data vertically in current column
                    sheet.update_cell(start_row + 4 + i, col, i + 1)  # Iteration
                    sheet.update_cell(start_row + 4 + i, col + 1, 4)  # Count
                    sheet.update_cell(start_row + 4 + i, col + 2, elapsed_time)  # Elapsed Time
                    sheet.update_cell(start_row + 4 + i, col + 5, energy_request)

            except Timeout:
                print("Error: Request timed out after 60 seconds")
            except ConnectionError as e:
                print(f"Connection error: {e}")
            except RequestException as e:
                print(f"Request failed: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
                print("Raw response:", response.content)

        i += 1  # Final value of iteration count

        # Summary stats
        summary_start_row = 4 + 5 + 3  # Leave 1 empty row after iterations
        try:
            sheet.update_cell(start_row + summary_start_row-1, col, "Summary")
            sheet.update_cell(start_row + summary_start_row, col, "Total Time")
            sheet.update_cell(start_row + summary_start_row , col+1, total_elapsed_time)
            sheet.update_cell(start_row + summary_start_row + 1, col, "Average Time")
            sheet.update_cell(start_row + summary_start_row + 1, col+1, total_elapsed_time / len(times))
            sheet.update_cell(start_row + summary_start_row + 2, col, "Variance")
            sheet.update_cell(start_row + summary_start_row + 2, col+1, np.var(times))
            sheet.update_cell(start_row + summary_start_row + 3, col, "Std Dev")
            sheet.update_cell(start_row + summary_start_row + 3, col+1, np.std(times))
            sheet.update_cell(start_row + summary_start_row + 4, col, "Min Time")
            sheet.update_cell(start_row + summary_start_row + 4, col+1, min(times))
            sheet.update_cell(start_row + summary_start_row + 5, col, "Max Time")
            sheet.update_cell(start_row + summary_start_row + 5, col+1, max(times))
            sheet.update_cell(start_row + summary_start_row + 6, col, "Total Requests")
            sheet.update_cell(start_row + summary_start_row + 6, col+1, i)
            sheet.update_cell(start_row + summary_start_row + 7, col, "Total Energy")
            sheet.update_cell(start_row + summary_start_row + 7, col+1, total_energy)
            sheet.update_cell(start_row + summary_start_row + 8, col, "Average Energy")
            sheet.update_cell(start_row + summary_start_row + 8, col+1, total_energy / len(energy))
            sheet.update_cell(start_row + summary_start_row + 9, col, "Variance Energy")
            sheet.update_cell(start_row + summary_start_row + 9, col+1, np.var(energy))
            sheet.update_cell(start_row + summary_start_row + 10, col, "Std Dev Energy")
            sheet.update_cell(start_row + summary_start_row + 10, col+1, np.std(energy))
        except:
            time.sleep(61)
            sheet.update_cell(start_row + summary_start_row-1, col, "Summary")
            sheet.update_cell(start_row + summary_start_row, col, "Total Time")
            sheet.update_cell(start_row + summary_start_row , col+1, total_elapsed_time)
            sheet.update_cell(start_row + summary_start_row + 1, col, "Average Time")
            sheet.update_cell(start_row + summary_start_row + 1, col+1, total_elapsed_time / len(times))
            sheet.update_cell(start_row + summary_start_row + 2, col, "Variance")
            sheet.update_cell(start_row + summary_start_row + 2, col+1, np.var(times))
            sheet.update_cell(start_row + summary_start_row + 3, col, "Std Dev")
            sheet.update_cell(start_row + summary_start_row + 3, col+1, np.std(times))
            sheet.update_cell(start_row + summary_start_row + 4, col, "Min Time")
            sheet.update_cell(start_row + summary_start_row + 4, col+1, min(times))
            sheet.update_cell(start_row + summary_start_row + 5, col, "Max Time")
            sheet.update_cell(start_row + summary_start_row + 5, col+1, max(times))
            sheet.update_cell(start_row + summary_start_row + 6, col, "Total Requests")
            sheet.update_cell(start_row + summary_start_row + 6, col+1, i)
            sheet.update_cell(start_row + summary_start_row + 7, col, "Total Energy")
            sheet.update_cell(start_row + summary_start_row + 7, col+1, total_energy)
            sheet.update_cell(start_row + summary_start_row + 8, col, "Average Energy")
            sheet.update_cell(start_row + summary_start_row + 8, col+1, total_energy / len(energy))
            sheet.update_cell(start_row + summary_start_row + 9, col, "Variance Energy")
            sheet.update_cell(start_row + summary_start_row + 9, col+1, np.var(energy))
            sheet.update_cell(start_row + summary_start_row + 10, col, "Std Dev Energy")
            sheet.update_cell(start_row + summary_start_row + 10, col+1, np.std(energy))
        col += 6
        if col == 25:
            col = 1
            if start_row == 1:
                start_row += 24
            else:
                start_row += 25
        time.sleep(61)
            


