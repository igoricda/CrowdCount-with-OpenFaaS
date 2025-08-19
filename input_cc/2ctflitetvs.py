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
import time
import concurrent.futures
import os
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
credentials = os.getenv("GOOGLE_CREDENTIALS")
creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
client = gspread.authorize(creds)

# Open your Google Sheet by ID
sheet_key = os.getenv("GOOGLE_SHEET_KEY2")
sheet = client.open_by_key(sheet_key).sheet1

def get_next_free_column(worksheet, row):
    col = 1
    while worksheet.cell(row+3, col).value:
        col += 6
    return col

def setup_openfaas():
    try:
        with open("/dev/null", "w") as nullfile:
            login_script = os.getenv("LOGIN_SCRIPT_TVBOX")
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

def prepare_sheet(sheet, start_row, col, img_spec):
    while(True):
        try:
            sheet.update_cell(start_row, col, f"Run {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            sheet.update_cell(start_row+1, col, f"Image: {img_spec}")
            sheet.update_cell(start_row + 2, col, "Iteration")
            sheet.update_cell(start_row + 2, col + 1, "Count1 and Count2")
            sheet.update_cell(start_row + 2, col + 2, "Elapsed Time")
            sheet.update_cell(start_row + 2, col + 3, "Energy Start")
            sheet.update_cell(start_row + 2, col + 4, "Energy End")
            sheet.update_cell(start_row + 2, col + 5, "Energy Request")
            break
        except:
            time.sleep(61)
            pass

def request(shared_data, data_lock, json_data, openfaas_url, current_energy):
            
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

        with data_lock:
                    energy_after = shared_data["total_mWh"]
        elapsed_time = response.elapsed.total_seconds()
        print(f"Response time: {elapsed_time:.2f} seconds")
        print(f"Count: {result['count']}, Energy Start: {current_energy}, Energy End: {energy_after}")

        return result['count'], elapsed_time, energy_after
    

if __name__ == "__main__":
    shared_data = {"total_mWh": 0.0}
    data_lock = threading.Lock()

    serial_thread = threading.Thread(
        target=read_serial_and_compute_energy,
        args=(shared_data, data_lock),
        daemon=True
    )
    serial_thread.start()
    """

    """
    image_list = [ "0p0f_0.jpg", "0p0f_1.jpg", "0p0f_2.jpg","0p0f_3.jpg", "0p0f_4.jpg", \
                   "1p1f_0.jpg", "1p1f_1.jpg", "1p1f_2.jpg","1p1f_3.jpg", "1p1f_4.jpg", \
                   "2p0f_0.jpg","2p1f_0.jpg","2p2f_0.jpg","2p2f_1.jpg", "2p2f_2.jpg", \
                   "3p0f_0.jpg","3p2f_0.jpg","3p3f_0.jpg","3p3f_1.jpg","3p3f_2.jpg", \
                   "4p1f_0.jpg","4p3f_0.jpg","4p3f_0.jpg", "4p3f_2.jpg", "4p4f_0.jpg", \
                   "5p0f_0.jpg", "5p1f_0.jpg", "6p6f_0.jpg", "8p7f_0.jpg", \
                    ]

    if not setup_openfaas():
        exit(1)
    url = os.getenv("OPENFAAS_URL_TVBOX")
    openfaas_url = url + "/function/crowdcounttflite"
    start_row = 1
    while(True):
        try:
            col = get_next_free_column(sheet, start_row)
            if col == 25:
                raise IndexError
            break
        except IndexError:
            if start_row == 1:
                start_row += 24
            else:
                start_row += 25
            continue
    
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


        prepare_sheet(sheet, start_row, col, img_spec)

        total_elapsed_time = 0
        times = []
        total_energy = 0
        energy = []
        count1l = []
        count2l = []
        request_energy = []
        for i in range (5):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                # Schedule the two 'do' threads to run
                with data_lock:
                    current_energy = shared_data["total_mWh"]
                sheet.update_cell(start_row+3+i, col + 3, current_energy)
                energy_before = current_energy
                print("Starting iteration", i+1, "for", img_spec)
                future1 = executor.submit(request, shared_data, data_lock, json_data, openfaas_url, current_energy)
                future2 = executor.submit(request, shared_data, data_lock, json_data, openfaas_url, current_energy)
                count1, time1, energy_request1 = future1.result()
                count2, time2, energy_request2 = future2.result()
                count1l.append((count1))
                count2l.append((count2))
                times.append(max(time1, time2))
                energy.append(max(energy_request1, energy_request2))
                total_elapsed_time += times[i]
                print(f"Iteration {i+1} for {img_spec} completed. Count1: {count1}, Count2: {count2}, Time: {times[i]}s, Energy Request: {energy[i]}mWh")
                request_energy.append(energy[i] - current_energy)
                total_energy += request_energy[i]
                    
            while(True):
                    try:
                        # Write data vertically in current column
                        sheet.update_cell(start_row + 3 + i, col, i + 1)  # Iteration
                        sheet.update_cell(start_row + 3 + i, col + 1 , str(count1l[i]) + ", " + str(count2l[i]) )  # Count
                        sheet.update_cell(start_row + 3 + i, col + 2, times[i])  # Elapsed Time
                        sheet.update_cell(start_row + 3 + i, col + 4 , energy[i])
                        sheet.update_cell(start_row + 3 + i, col + 5, request_energy[i])  # Energy Request
                        print(f"Iteration {i+1} for {img_spec} completed. Time: {times[i]}s, Energy: {energy[i]}mWh")
                        break
                    except:
                        time.sleep(60)
                        pass
                            # Summary stats
        summary_start_row = 4 + 5 + 3  # Leave 1 empty row after iterations
        while(True):
            try:
                sheet.update_cell(start_row + summary_start_row-1, col, "Summary")
                sheet.update_cell(start_row + summary_start_row, col, "Total Time")
                sheet.update_cell(start_row + summary_start_row , col+1, total_elapsed_time)
                sheet.update_cell(start_row + summary_start_row + 1, col, "Average Time")
                sheet.update_cell(start_row + summary_start_row + 1, col+1, total_elapsed_time / (len(times)*2))
                sheet.update_cell(start_row + summary_start_row + 2, col, "Variance")
                sheet.update_cell(start_row + summary_start_row + 2, col+1, np.var(times))
                sheet.update_cell(start_row + summary_start_row + 3, col, "Std Dev")
                sheet.update_cell(start_row + summary_start_row + 3, col+1, np.std(times))
                sheet.update_cell(start_row + summary_start_row + 4, col, "Min Time")
                sheet.update_cell(start_row + summary_start_row + 4, col+1, min(times))
                sheet.update_cell(start_row + summary_start_row + 5, col, "Max Time")
                sheet.update_cell(start_row + summary_start_row + 5, col+1, max(times))
                sheet.update_cell(start_row + summary_start_row + 6, col, "Total Requests")
                sheet.update_cell(start_row + summary_start_row + 6, col+1, (i+1)*2)
                sheet.update_cell(start_row + summary_start_row + 7, col, "Total Energy")
                sheet.update_cell(start_row + summary_start_row + 7, col+1, total_energy)
                sheet.update_cell(start_row + summary_start_row + 8, col, "Average Energy")
                sheet.update_cell(start_row + summary_start_row + 8, col+1, total_energy / (len(energy)*2))
                sheet.update_cell(start_row + summary_start_row + 9, col, "Variance Energy")
                sheet.update_cell(start_row + summary_start_row + 9, col+1, np.var(request_energy))
                sheet.update_cell(start_row + summary_start_row + 10, col, "Std Dev Energy")
                sheet.update_cell(start_row + summary_start_row + 10, col+1, np.std(request_energy))
                break
            except:
                time.sleep(61)
                pass

        col += 6
        if col == 25:
            col = 1
            if start_row == 1:
                start_row += 24
            else:
                start_row += 25


        print(f"Finished processing for {img_spec}. Waiting before next image...")
        time.sleep(61)
  
            


