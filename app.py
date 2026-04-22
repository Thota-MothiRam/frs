
##app.py

import cv2
import threading
import pygame
import json
import datetime
import tempfile
import os
from gtts import gTTS
from flask import Flask, Response, request, jsonify
from processor.OpenvinoFaceRecognition.face_build_argparser import *
from processor.OpenvinoFaceRecognition.FaceFrameProcessor import *
from face_recognitions import *
from processor.__DatabaseLayer__ import DataAccess
from queue import Queue
import mysql.connector
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import time
from processor.OpenvinoFaceRecognition.logger import trace, exc
import logging
from config import *
from flask_cors import CORS
from werkzeug.security import generate_password_hash
from flask_jwt_extended import JWTManager, create_access_token
import jwt
from scipy.spatial.distance import cosine
from flask import request, jsonify
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler

from pytz import timezone
from openvino.runtime import Core
import re
# from datetime import date 
import datetime
from math import radians, sin, cos, sqrt, asin
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask import send_from_directory
from flask import jsonify, url_for
import traceback  # Add this at the top
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
import base64
from Crypto.Hash import SHA256
import hashlib
from Crypto.Random import get_random_bytes
# from crypto_utils import *
from crypto import *
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# import time
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from werkzeug.security import check_password_hash, generate_password_hash
from dateutil.relativedelta import relativedelta
import math




# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# --- Enable APScheduler debug logs ---
logging.basicConfig()
logging.getLogger("apscheduler").setLevel(logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)


CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})






# Load RTSP URLs and distance limits from the config file
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

rtsp_urls = config["RTSP_URLS"]
distance_limits = config["distance_limits"]



pygame.mixer.init()

# Define a lock to prevent multiple sounds from playing simultaneously
sound_lock = threading.Lock()

def safe_remove(file_path, retries=5, delay=0.5):
    for attempt in range(retries):
        try:
            os.remove(file_path)
            print(f"File {file_path} removed successfully.")
            trace.info(f"File {file_path} removed successfully.")
            break
        except PermissionError:
            print(f"Attempt {attempt + 1}: File in use, retrying in {delay} seconds...")
            trace.info(f"Attempt {attempt + 1}: File in use, retrying in {delay} seconds...")
            time.sleep(delay)
    else:
        print(f"Failed to remove {file_path} after {retries} attempts due to file being in use.")
        exc.exception(f"Failed to remove {file_path} after {retries} attempts due to file being in use.")

def play_sound_async(message):
    def play_sound():
        tts = gTTS(message, lang='en')
        with tempfile.NamedTemporaryFile(delete=False, mode='w+b') as temp_file:
            tts.save(temp_file.name)
            file_path = temp_file.name

        acquired = sound_lock.acquire(blocking=False)
        if acquired:
            try:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()

                # Wait until the sound finishes playing
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)

            except Exception as e:
                print(f"Error playing sound file: {e}")
                exc.exception(f"Error playing sound file: {e}")
            finally:
                sound_lock.release()
                # Use safe_remove instead of os.remove
                threading.Thread(target=lambda: safe_remove(file_path)).start()

    sound_thread = threading.Thread(target=play_sound)
    sound_thread.start()


def save_config(config, filename='config.json'):
    try:
        with open(filename, 'w') as config_file:
            json.dump(config, config_file, indent=4)  # Save the config as pretty-printed JSON
        logging.debug(f"Configuration saved successfully to {filename}")
        trace.info(f"Configuration saved successfully to {filename}")
    except Exception as e:
        logging.error(f"Error saving configuration to {filename}: {e}")
        exc.exception(f"Error saving configuration to {filename}: {e}")
        raise  # Re-raise the exception for handling elsewhere


def markAttendanceWithTimeApi(tenant_id, employee_id, data_date, ttime, login_flag, logout_flag):
    try:
        print(f"Calling attendance API with Time for Tenant ID {tenant_id}, Employee ID {employee_id}, date {data_date}, time {ttime},login_flag {login_flag}, logout_flag {logout_flag}")
        trace.info(f"Calling attendance API with Time for Tenant ID {tenant_id}, Employee ID {employee_id}, date {data_date}, time {ttime}, login_flag {login_flag}, logout_flag {logout_flag}")
        
        # Constructing the data payload
        data = {
            "Tenant_id": "T001",
            "employee_id": employee_id,
            "date": data_date,
            "time": ttime,
            "LogJson": {
                "EmployeeID": employee_id,
                "Date": data_date,
                "Time": ttime,
                "login_flag": login_flag,
                "logout_flag": logout_flag
            }
        }

        # Configuring session with retries
        session = requests.Session()
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # Sending the POST request
        response = session.post(facelogWithAtimeApi1, json=data)  # Using `json` to send as JSON payload
        print(response)
        logger.info(response)
        trace.info(response)
        
        response = response.json()
        logger.info(response)
        trace.info(response)
        return response

    except Exception as error:
        print("markAttendanceWithTimeApi", error)
        logger.error(error)
        exc.exception("markAttendanceWithTimeApi", error)
        time.sleep(5)
        return {'status': 401, 'status_message': 'Server Down'}
    


def markEncryptedAttendanceApi(encrypted_payload):
    try:
        session = requests.Session()
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        data = {"encrypted": encrypted_payload}
        trace.info(f"[DEBUG] Sending payload to API: {data}")

        # --- Add your Referer header here ---
        headers = {
            "Referer": "https://192.168.5.198:1012/",   # the referer you need to send
            "Content-Type": "application/json"
        }

        # Send POST with headers included
        response = session.post(facelogWithAtimeApi1, json=data, headers=headers)
        # -------------------------------------

        trace.info(f"[DEBUG] API HTTP status: {response.status_code}")
        trace.info(f"[DEBUG] API raw response text: {response.text}")

        response_json = response.json()
        trace.info(f"[DEBUG] API parsed response JSON: {response_json}")

        return response_json

    except Exception as error:
        trace.info(f"[ERROR] markEncryptedAttendanceApi Exception: {error}")
        time.sleep(5)
        return {'status': 401, 'status_message': 'Server Down'}


def markEncryptedAttendanceApiforoutoflocation(encrypted_payload):
    try:
        session = requests.Session()
        retry = Retry(connect=5, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        data = {"encrypted": encrypted_payload}
        trace.info(f"[DEBUG] Sending payload to API: {data}")

        # --- Add your Referer header here ---
        headers = {
            "Referer": "https://192.168.5.198:1012/",   # the referer you need to send
            "Content-Type": "application/json"
        }

        # Send POST with headers included
        response = session.post(out_of_location, json=data, headers=headers)
        # -------------------------------------

        trace.info(f"[DEBUG] API HTTP status: {response.status_code}")
        trace.info(f"[DEBUG] API raw response text: {response.text}")

        response_json = response.json()
        trace.info(f"[DEBUG] API parsed response JSON: {response_json}")

        return response_json

    except Exception as error:
        trace.info(f"[ERROR] markEncryptedAttendanceApi Exception: {error}")
        time.sleep(5)
        return {'status': 401, 'status_message': 'Server Down'}




# Dictionary to track last login times per employee
last_login_times = {}
 

 



def process_attendance(face_image_original_path):
    if not face_image_original_path:
        return  
 
    processed_employees = set()

    # Load shift timings from config.json
    config_path = 'config.json'
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            shift_timings = config.get("Shift_Timings", {})
    
            NS_SHIFT_START = shift_timings.get("NS_SHIFT_START", "15:00:00")
            NS_SHIFT_END = shift_timings.get("NS_SHIFT_END", "11:00:00")
    except Exception as e:
        print(f"Error loading config: {e}")
        NS_SHIFT_START = "15:00:00"
        NS_SHIFT_END = "11:00:00"
    
    # Convert shift times to datetime format
    NS_SHIFT_START_TIME = datetime.datetime.strptime(NS_SHIFT_START, "%H:%M:%S").time()
    NS_SHIFT_END_TIME = datetime.datetime.strptime(NS_SHIFT_END, "%H:%M:%S").time()
 
    for face_crop, name, file_name in face_image_original_path:
        if name == "Unknown":
            continue
 
        message = f"{name[0]} Detected."
        # play_sound_async(message)  # Assuming this function exists
 
        try:
            # Extract only the filename without extension
            name = name.rsplit('.', 1)[0]  # Remove the ".jpg" extension

            # Use regex to match "name_ID_(number)"
            match = re.match(r"(.+?)_(\d+)_\(\d+\)$", name)

            if match:
                employee_name = match.group(1).replace('_', ' ')  # Replace underscores with spaces
                employee_id = match.group(2)  # Extract the ID
                print(f"Extracted Employee ID: {employee_id}, Name: {employee_name}")
                trace.info(f"Extracted Employee ID: {employee_id}, Name: {employee_name}")
            else:
                print(f"Invalid Employee Data: {name}")  # Debugging
                trace.info(f"Invalid Employee Data: {name}")  # Debugging
            # employee_id = name[-2]
            # trace.info({employee_id})
            cur_date = datetime.datetime.now().date()
            current_time = datetime.datetime.now()
 
 
            # Fetch shift type
            shift_data = DataAccess.get_employee_shift(employee_id)
            shift_type = shift_data.get("Shift") if isinstance(shift_data, dict) else None
 
            if not shift_type:
                print(f"Shift type not found for Employee ID {employee_id}")
                trace.info(f"Shift type not found for Employee ID {employee_id}")
                continue
 
            print(f"Shift type for Employee ID {employee_id}: {shift_type}")
            trace.info(f"Shift type for Employee ID {employee_id}: {shift_type}")
 
            # Retrieve attendance data
            attendance_db_data_today = DataAccess.get_attendance_data_by_name_and_date1(employee_id, cur_date)
            prev_date = cur_date - datetime.timedelta(days=1)
            attendance_db_data_prev = DataAccess.get_attendance_data_by_name_and_date1(employee_id, prev_date)
 
            # Ensure attendance data is a dictionary, not a list
            if isinstance(attendance_db_data_today, list) and attendance_db_data_today:
                attendance_db_data_today = attendance_db_data_today[0]
 
            if isinstance(attendance_db_data_prev, list) and attendance_db_data_prev:
                attendance_db_data_prev = attendance_db_data_prev[0]
 
            log_json = None
            shift_date = cur_date  # Default shift date

            # General Shift (GS) Processing
            if shift_type == "GS":
                # Apply 5-minute gap restriction only for GS employees
                if employee_id in last_login_times:
                    time_diff = (current_time - last_login_times[employee_id]).total_seconds() / 60
                    if time_diff < 5:
                        print(f"Skipping login for {employee_id}, already logged in within last 5 minutes.")
                        trace.info(f"Skipping login for {employee_id}, already logged in within last 5 minutes.")
                        continue  # Skip further processing for this employee
            
                if attendance_db_data_today and attendance_db_data_today.get("loginflag") == 1:
                    try:
                        DataAccess.insert_attendance1(employee_id, cur_date, current_time.strftime("%H:%M:%S"), loginflag=0, logoutflag=1)
                        DataAccess.update_logout_flags(employee_id, cur_date)
                        log_json = {"employee_id": employee_id, "date": cur_date.strftime('%Y-%m-%d'), "time": current_time.strftime("%H:%M:%S"), "login_flag": 0, "logout_flag": 1}
                        print(f"Logout time updated for Employee ID {employee_id}")
                        trace.info(f"Logout time updated for Employee ID {employee_id}")
                    except Exception as e:
                        print(f"Error updating logout for Employee ID {employee_id} (GS shift): {e}")
                        trace.info(f"Error updating logout for Employee ID {employee_id} (GS shift): {e}")
                        continue
                else:
                    try:
                        DataAccess.insert_attendance1(employee_id, cur_date, current_time.strftime("%H:%M:%S"), loginflag=1, logoutflag=0)
                        log_json = {"employee_id": employee_id, "date": cur_date.strftime('%Y-%m-%d'), "time": current_time.strftime("%H:%M:%S"), "login_flag": 1, "logout_flag": 0}
                        last_login_times[employee_id] = current_time  # Store last login time for GS employees only
                        print(f"Login time recorded for Employee ID {employee_id}")
                        trace.info(f"Login time recorded for Employee ID {employee_id}")
                    except Exception as e:
                        print(f"Error inserting login for Employee ID {employee_id} (GS shift): {e}")
                        trace.info(f"Error inserting login for Employee ID {employee_id} (GS shift): {e}")
                        continue

            # Night Shift (NS) Processing
            elif shift_type == "NS":
                current_time_only = current_time.time()
                shift_date = prev_date if current_time_only <= NS_SHIFT_END_TIME else cur_date

                has_prev_day_login = attendance_db_data_prev and attendance_db_data_prev.get("loginflag") == 1
                has_prev_day_logout = attendance_db_data_prev and attendance_db_data_prev.get("logoutflag") == 1
                has_today_login = attendance_db_data_today and attendance_db_data_today.get("loginflag") == 1

                # if not has_prev_day_login:
                if not has_prev_day_login and current_time_only >= NS_SHIFT_START_TIME:
                    try:
                        DataAccess.insert_attendance1(employee_id, cur_date, current_time.strftime("%H:%M:%S"), loginflag=1, logoutflag=0)
                        log_json = {"employee_id": employee_id, "date": cur_date.strftime('%Y-%m-%d'), "time": current_time.strftime("%H:%M:%S"), "login_flag": 1, "logout_flag": 0}
                        last_login_times[employee_id] = current_time
                        print(f"New login recorded for Employee ID {employee_id} (NS shift)")
                        trace.info(f"New login recorded for Employee ID {employee_id} (NS shift)")
                    except Exception as e:
                        print(f"Error inserting login for Employee ID {employee_id} (NS shift): {e}")
                        trace.info(f"Error inserting login for Employee ID {employee_id} (NS shift): {e}")
                        return 

                
                elif has_prev_day_login:
                    if current_time_only <= NS_SHIFT_END_TIME:  # Before 09:00:00
                        try:
                            # Logout should be recorded for the previous shift date (10-03-2025)
                            DataAccess.insert_attendance1(employee_id, prev_date, current_time.strftime("%H:%M:%S"), loginflag=0, logoutflag=1)
                            DataAccess.update_logout_flags(employee_id, prev_date)
                            log_json = {
                                "employee_id": employee_id,
                                "date": prev_date.strftime('%Y-%m-%d'),  # Use previous day
                                "time": current_time.strftime("%H:%M:%S"),
                                "login_flag": 0,
                                "logout_flag": 1
                            }
                            print(f"Logout time updated for Employee ID {employee_id} (NS shift) on {prev_date.strftime('%Y-%m-%d')}")
                            trace.info(f"Logout time updated for Employee ID {employee_id} (NS shift) on {prev_date.strftime('%Y-%m-%d')}")
                        except Exception as e:
                            print(f"Error updating logout for Employee ID {employee_id} (NS shift): {e}")
                            trace.info(f"Error updating logout for Employee ID {employee_id} (NS shift): {e}")



                if has_today_login:
                    # If the employee has already logged in today, update their logout time
                    try:
                        DataAccess.insert_attendance1(employee_id, cur_date, current_time.strftime("%H:%M:%S"), loginflag=0, logoutflag=1)
                        DataAccess.update_logout_flags(employee_id, cur_date)
                        log_json = {
                            "employee_id": employee_id,
                            "date": cur_date.strftime('%Y-%m-%d'),
                            "time": current_time.strftime("%H:%M:%S"),
                            "login_flag": 0,
                            "logout_flag": 1
                        }
                        print(f"Logout time updated for Employee ID {employee_id} (NS shift) on {cur_date.strftime('%Y-%m-%d')}")
                        trace.info(f"Logout time updated for Employee ID {employee_id} (NS shift) on {cur_date.strftime('%Y-%m-%d')}")
                    except Exception as e:
                        print(f"Error updating logout for Employee ID {employee_id} (NS shift): {e}")
                        trace.info(f"Error updating logout for Employee ID {employee_id} (NS shift): {e}")
                
                # If no login exists for today, insert a new login record
                elif current_time_only >= NS_SHIFT_START_TIME:
                    try:
                        DataAccess.insert_attendance1(employee_id, cur_date, current_time.strftime("%H:%M:%S"), loginflag=1, logoutflag=0)
                        log_json = {
                            "employee_id": employee_id,
                            "date": cur_date.strftime('%Y-%m-%d'),
                            "time": current_time.strftime("%H:%M:%S"),
                            "login_flag": 1,
                            "logout_flag": 0
                        }
                        last_login_times[employee_id] = current_time
                        print(f"New login recorded for Employee ID {employee_id} (Post-shift NS login)")
                        trace.info(f"New login recorded for Employee ID {employee_id} (Post-shift NS login)")
                    except Exception as e:
                        print(f"Error inserting new login for Employee ID {employee_id} after shift time exceeded: {e}")
                        trace.info(f"Error inserting new login for Employee ID {employee_id} after shift time exceeded: {e}")


            # Call API for Attendance Marking
            if log_json and employee_id not in processed_employees:
                api_response = markAttendanceWithTimeApi("T001", employee_id, shift_date.strftime('%Y-%m-%d'), current_time.strftime("%H:%M:%S"), log_json["login_flag"], log_json["logout_flag"])
                print(f"API Response for {employee_id}: {api_response}")
                trace.info(f"API Response for {employee_id}: {api_response}")
                processed_employees.add(employee_id)

        except Exception as e:
            print(f"Unexpected error processing attendance: {str(e)}")
            trace.info(f"Unexpected error processing attendance: {str(e)}")



data_set = r"face_dataset"
reid_path = r"model_files\\face-reidentification-retail-0095\\FP16\\face-reidentification-retail-0095.xml"
detect_face = r"model_files\\face-detection-adas-0001\\FP16\\face-detection-adas-0001.xml"
land_detect = r"model_files\\landmarks-regression-retail-0009\\FP16\\landmarks-regression-retail-0009.xml"
openvino_process_device = 'CPU'
face_reid_threshold = 0.18

face_args = build_argparser(None, detect_face, land_detect, reid_path, data_set, None, openvino_process_device, face_reid_threshold).parse_args()
face_frame_processor = FrameProcessor(face_args)
face_frame_num = 0
face_presenter = None
face_output_transform = None
cam_name = 'feed1'
face_path = r'Output_faces'

# Specify the folder for storing images
UPLOAD_FOLDER = r'face_dataset'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the images_upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/upload_image', methods=['POST'])
def upload_images():
    print("Request files:", request.files)  # Debugging line
    trace.info("Request files:", request.files) 

    if not request.files:
        return jsonify({'error': 'No images part in the request'}), 400
    
    saved_files = []
    for key, file in request.files.items():
        if file and file.filename != '':  # Check if file exists and has a filename
            # Save the file
            filename = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_files.append(filename)

    if not saved_files:
        return jsonify({'error': 'No valid files were uploaded'}), 400

    # return jsonify({'success': f'{len(saved_files)} images saved', 'files': saved_files}), 200
    return jsonify({'success': f'{len(saved_files)} image added successfully', 'files': saved_files}), 200


ie = Core()
face_det_model_path = r"model_files\\face-detection-adas-0001\\FP16\\face-detection-adas-0001.xml"
face_rec_model_path = r"model_files\\face-reidentification-retail-0095\\FP16\\face-reidentification-retail-0095.xml"
landmarks_model = r"model_files\\landmarks-regression-retail-0009\\FP16\\landmarks-regression-retail-0009.xml"

face_det_net = ie.compile_model(face_det_model_path, "CPU")
landmark_net = ie.compile_model(landmarks_model, "CPU")
face_reid_net = ie.compile_model(face_rec_model_path, "CPU")

FACE_DATASET_FOLDER = r"face_dataset"  # Folder containing known face images
THRESHOLD = 0.65 # Cosine similarity threshold




# Preprocessing function for OpenVINO models
def preprocess(image, input_shape):
    resized = cv2.resize(image, (input_shape[3], input_shape[2]))
    transposed = resized.transpose((2, 0, 1))  # HWC to CHW
    return np.expand_dims(transposed, axis=0)  # Add batch dimension

# Load face embeddings from dataset
def load_face_dataset():
    face_embeddings = {}
    for file in os.listdir(FACE_DATASET_FOLDER):
        if file.endswith(".jpg") or file.endswith(".png"):
            img_path = os.path.join(FACE_DATASET_FOLDER, file)
            img = cv2.imread(img_path)
            face_input = preprocess(img, face_reid_net.inputs[0].shape)
            embedding = face_reid_net(face_input)[face_reid_net.outputs[0]].flatten()
            face_embeddings[file] = embedding
    return face_embeddings

known_faces = load_face_dataset()




def encrypt_aes_cryptojs_compatible(data, password: str) -> str:
    """
    Encrypt data in Python compatible with CryptoJS AES-CBC OpenSSL format.
    Output: base64("Salted__" + salt + ciphertext)
    """
    # Convert data to string
    if not isinstance(data, str):
        data = json.dumps(data, separators=(',', ':'))  # match JS JSON.stringify

    # Random 8-byte salt
    salt = get_random_bytes(8)
    key_size = 32  # 256-bit AES
    iv_size = 16

    # OpenSSL EVP_BytesToKey derivation
    def evp_bytes_to_key(password_bytes, salt_bytes, key_len, iv_len):
        dtot = b""
        d = b""
        while len(dtot) < key_len + iv_len:
            d = hashlib.md5(d + password_bytes + salt_bytes).digest()
            dtot += d
        key = dtot[:key_len]
        iv = dtot[key_len:key_len + iv_len]
        return key, iv

    key, iv = evp_bytes_to_key(password.encode('utf-8'), salt, key_size, iv_size)

    # AES-CBC encryption with PKCS7 padding
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_bytes = cipher.encrypt(pad(data.encode('utf-8'), AES.block_size))

    # OpenSSL format: Salted__ + salt + ciphertext
    openssl_bytes = b"Salted__" + salt + encrypted_bytes

    # Base64 encode
    return base64.b64encode(openssl_bytes).decode('utf-8')





secret_key = '3a374c6f0e20f5656bb4b745ac8c0cb15056a339bc7a7bf836632b7b5143c7dd'


#------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
 
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
 
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c
 
def is_within_any_location_from_api(lat, lon, secret_key):
    try:
        trace.info(f"[GPS] Checking via API if lat={lat}, lon={lon} is within any known location")
        payload = {
            "Tenant_id": "T001"
        }

        response = requests.post(ehr_location_api, headers=ehr_location_headers,json=payload, timeout=10)
        response.raise_for_status()
 
        encrypted = response.json().get("encrypted")
        if not encrypted:
            trace.info("[GPS] No encrypted data received from API")
            return False, None, None
 
        # Decrypt API response
        decrypted_text = AESGCMCrypto.decrypt(encrypted, secret_key)
 
        if isinstance(decrypted_text, str):
            decrypted_data = json.loads(decrypted_text)
        else:
            decrypted_data = decrypted_text
 
        locations = decrypted_data.get("data", [])
        trace.info(f"[GPS] Retrieved {len(locations)} location(s) from API")
 
        if not locations:
            return False, None, None
 
        closest_distance = float('inf')
        closest_location_name = None
 
        for loc in locations:
            try:
                loc_name = loc.get("location_name")
                loc_lat = float(loc.get("latitude"))
                loc_lon = float(loc.get("longitude"))
 
                # API radius is in KM → convert to meters
                radius_meters = float(loc.get("radius"))
 
                distance = haversine(lat, lon, loc_lat, loc_lon)
 
                trace.info(
                    f"[GPS] {loc_name}: distance={distance:.2f} m "
                    f"(allowed={radius_meters:.2f} m)"
                )
 
                if distance <= radius_meters:
                    trace.info(f"[GPS] Match found: {loc_name} within {distance:.2f} meters")
                    return True, loc_name, distance
 
                if distance < closest_distance:
                    closest_distance = distance
                    closest_location_name = loc_name
 
            except Exception as e_inner:
                trace.info(f"[GPS ERROR] Failed processing location {loc}: {e_inner}")
 
        trace.info(
            f"[GPS] No match. Closest: {closest_location_name} "
            f"at {closest_distance:.2f} meters"
        )
        return False, closest_location_name, closest_distance
 
    except Exception as e:
        trace.info(f"[GPS ERROR] Failed in is_within_any_location_from_api: {e}")
        raise Exception(f"Error in is_within_any_location_from_api: {e}")

def is_within_any_location_from_api_test(lat, lon, secret_key):
    try:
        trace.info(f"[GPS] Checking via API if lat={lat}, lon={lon} is within any known location")
 
        response = requests.post(ehr_location_api_testing, headers=ehr_location_headers_testing, timeout=10)
        response.raise_for_status()
 
        encrypted = response.json().get("encrypted")
        if not encrypted:
            trace.info("[GPS] No encrypted data received from API")
            return False, None, None
 
        # Decrypt API response
        decrypted_text = AESGCMCrypto.decrypt(encrypted, secret_key)
 
        if isinstance(decrypted_text, str):
            decrypted_data = json.loads(decrypted_text)
        else:
            decrypted_data = decrypted_text
 
        locations = decrypted_data.get("data", [])
        trace.info(f"[GPS] Retrieved {len(locations)} location(s) from API")
 
        if not locations:
            return False, None, None
 
        closest_distance = float('inf')
        closest_location_name = None
 
        for loc in locations:
            try:
                loc_name = loc.get("location_name")
                loc_lat = float(loc.get("latitude"))
                loc_lon = float(loc.get("longitude"))
 
                # API radius is in KM → convert to meters
                radius_meters = float(loc.get("radius"))
 
                distance = haversine(lat, lon, loc_lat, loc_lon)
 
                trace.info(
                    f"[GPS] {loc_name}: distance={distance:.2f} m "
                    f"(allowed={radius_meters:.2f} m)"
                )
 
                if distance <= radius_meters:
                    trace.info(f"[GPS] Match found: {loc_name} within {distance:.2f} meters")
                    return True, loc_name, distance
 
                if distance < closest_distance:
                    closest_distance = distance
                    closest_location_name = loc_name
 
            except Exception as e_inner:
                trace.info(f"[GPS ERROR] Failed processing location {loc}: {e_inner}")
 
        trace.info(
            f"[GPS] No match. Closest: {closest_location_name} "
            f"at {closest_distance:.2f} meters"
        )
        return False, closest_location_name, closest_distance
 
    except Exception as e:
        trace.info(f"[GPS ERROR] Failed in is_within_any_location_from_api: {e}")
        raise Exception(f"Error in is_within_any_location_from_api: {e}")



def get_login_info_from_api(employee_id, cur_date, secret_key):
    try:
        trace.info(f"[API] Checking attendance for {employee_id}")

        payload = {
            "Tenant_id": "T007",   # ✅ Hardcoded like GPS function
            "Employee_id": employee_id,
            "date": cur_date.strftime('%Y-%m-%d')
        }

        payload_json = json.dumps(payload)

        #  Encrypt request
        encrypted_payload = AESGCMCrypto.encrypt(payload_json, secret_key)

        response = requests.post(
            VALIDATE_ATTENDANCE_API,
            headers=VALIDATE_ATTENDANCE_HEADERS,
            json={"encrypted": encrypted_payload},
            timeout=10
        )

        response.raise_for_status()

        encrypted = response.json().get("encrypted")

        if not encrypted:
            trace.info("[API] No encrypted data received")
            return None

        #  Decrypt response
        decrypted_text = AESGCMCrypto.decrypt(encrypted, secret_key)

        if isinstance(decrypted_text, str):
            data = json.loads(decrypted_text)
        else:
            data = decrypted_text

        trace.info(f"[API RESPONSE] {data}")

        from datetime import datetime

        login_time = data.get("login_time")
        logout_time = data.get("logout_time")

        #  Convert string → time
        if login_time:
            try:
                login_time = datetime.strptime(login_time, "%H:%M:%S").time()
            except:
                login_time = None

        if logout_time:
            try:
                logout_time = datetime.strptime(logout_time, "%H:%M:%S").time()
            except:
                logout_time = None

        return {
            "login_time": login_time,
            "logout_time": logout_time,
            "source": "api"
        }

    except Exception as e:
        trace.info(f"[ERROR] ValidateAttendance API failed: {e}")
        return None


#testing code for away-update
@app.route('/detect_faces', methods=['POST'])
def detect_faces():
    try:
        start_time = time.time()
 
        file = request.files['image']
        action = request.form.get('action')  # "clock_in" or "clock_out"
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        away_mode = request.form.get('away', 'off').lower() == 'on'
 
        image = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_COLOR)
        h, w = image.shape[:2]
 
        cur_date = datetime.datetime.now().date()
        current_time = datetime.datetime.now()
 
        input_tensor = preprocess(image, face_det_net.inputs[0].shape)
        detections = face_det_net(input_tensor)[face_det_net.outputs[0]]
 
        results = []
        face_image_original_path = []
 
        for det in detections[0][0]:
            confidence = float(det[2])
            if confidence < 0.3:
                continue
 
            xmin, ymin, xmax, ymax = (det[3:7] * [w, h, w, h]).astype(int)
            xmin, ymin = max(0, xmin), max(0, ymin)
            xmax, ymax = min(w, xmax), min(h, ymax)
            if xmax <= xmin or ymax <= ymin:
                continue
 
            face_crop = image[ymin:ymax, xmin:xmax]
 
            # Landmark & face embedding
            landmark_input = preprocess(face_crop, landmark_net.inputs[0].shape)
            landmarks = landmark_net(landmark_input)[landmark_net.outputs[0]][0].reshape(-1, 2)
            landmarks = [{"x": int(x * (xmax - xmin) + xmin), "y": int(y * (ymax - ymin) + ymin)} for x, y in landmarks]
 
            reid_input = preprocess(face_crop, face_reid_net.inputs[0].shape)
            face_embedding = face_reid_net(reid_input)[face_reid_net.outputs[0]].flatten()
 
            is_known, employee_id, employee_name = False, None, "Unknown"
            for name, known_embedding in known_faces.items():
                similarity = 1 - cosine(face_embedding, known_embedding)
                if similarity > THRESHOLD:
                    is_known = True
                    parts = name.split('_')
                    employee_name = ' '.join(parts[:-2])
                    employee_id = parts[-2]
                    break
 
            login_time, is_first_login, message = None, False, None
 
            if is_known and employee_id:
                if not lat or not lon:
                    trace.info(f"Missing GPS coordinates for employee {employee_id}")
                else:
                    try:
                        is_allowed, matched_location_name, distance = is_within_any_location_from_api(float(lat), float(lon),secret_key)
                        trace.info(f"[DEBUG] is_allowed={is_allowed}, type={type(is_allowed)}")
                        trace.info(f"[DEBUG] distance={distance}, location={matched_location_name}")

                        trace.info(f"Employee {employee_id} is within location '{matched_location_name}' at {distance:.2f} meters.")
                        if is_allowed:
                            if action == "clock_in":
                                # login_info = DataAccess.get_login_time_for_today(employee_id, cur_date)
                                login_info = get_login_info_from_api(employee_id, cur_date, secret_key)
 
                                if login_info and login_info["source"] == "face_data2":
                                    # Already clocked in today
                                    login_time = login_info["login_time"].strftime("%H:%M:%S") if login_info["login_time"] else None
                                    is_first_login = False
                                    trace.info(f"[INFO] Employee {employee_id} already clocked in today at {login_time}")
 
 
                                elif login_info and login_info["source"] == "pending_out_of_location":
                                    confirm_from_frontend = request.form.get("confirm_pending", "no").lower() == "yes"
                                    if confirm_from_frontend:
                                        DataAccess.confirm_out_of_location_clockin(employee_id, cur_date, current_time.strftime("%H:%M:%S"), matched_location_name)
                                        login_time = current_time.strftime("%H:%M:%S")
                                        is_first_login = True
                                        message = "Pending out-of-location declined, fresh clock-in stored"
                                        trace.info(f"[SUCCESS] {message} for {employee_id}")
                                    else:
                                        message = "Pending out-of-location clock-in exists. Please confirm to proceed."
                                        trace.info(f"[PENDING] {message} for {employee_id}")
 
                                else:
                                    # Fresh clock-in
                                    yesterday_date = cur_date - datetime.timedelta(days=1)
                                    yesterday_info = DataAccess.get_login_time_for_today(employee_id, yesterday_date)
                                    time_diff_hours = None
 
                                    if yesterday_info and yesterday_info.get("login_time"):
                                        existing_login_yesterday = yesterday_info["login_time"]
                                        if isinstance(existing_login_yesterday, datetime.datetime):
                                            time_diff = current_time - existing_login_yesterday
                                        else:
                                            login_time_obj = datetime.datetime.combine(yesterday_date, existing_login_yesterday if isinstance(existing_login_yesterday, datetime.time) else datetime.time(0, 0, 0))
                                            time_diff = current_time - login_time_obj
                                        time_diff_hours = time_diff.total_seconds() / 3600.0
 
                                    if (not yesterday_info or not yesterday_info.get("login_time")) or (time_diff_hours and time_diff_hours > 15):
                                        login_time = current_time.strftime("%H:%M:%S")
                                        DataAccess.insert_attendance1(employee_id, cur_date, login_time, loginflag=1, logoutflag=0, login_location=matched_location_name)
                                        is_first_login = True
                                        trace.info(f"[SUCCESS] Fresh clock-in recorded for Employee {employee_id} at {login_time} on {cur_date}")
                                        payload = {"Tenant_id": "T001","LogJson": {"EmployeeID": employee_id,"Date": cur_date.strftime('%Y-%m-%d'),"Time": login_time,"login_flag": "1","logout_flag": "0"}}
                                        # encrypted_payload = encrypt_aes_cryptojs_compatible(payload, secret_key)
                                        payload_json = json.dumps(payload)
                                        trace.info(f"payload_json: {payload_json}")
                                        encrypted_payload = AESGCMCrypto.encrypt(payload_json, secret_key)
                                        trace.info(f"encrypted playload sending to ehr api: {encrypted_payload}")
                                        api_response = markEncryptedAttendanceApi(encrypted_payload)
 
                                        if 'encrypted' in api_response and api_response['encrypted']:
                                            trace.info(f"[API SUCCESS] Clock-in API response successful for {employee_id}")
                                        else:
                                            trace.info(f"[API FAILURE] Clock-in API response failure for {employee_id}: {api_response}")
                                    else:
                                        trace.info(f"[INFO] Clock-in blocked: Existing login within {time_diff_hours:.2f} hours")

                            elif action == "clock_out":
                                # Fetch login info from today and yesterday
                                login_info_today = DataAccess.get_login_time_for_today(employee_id, cur_date)
                                login_info_yesterday = DataAccess.get_login_time_for_today(employee_id, cur_date - datetime.timedelta(days=1))
 
                                login_info = None
                                login_date = None
 

                                # Prefer today's login first
                                if login_info_today and login_info_today.get("login_time"):
                                    login_info = login_info_today
                                    login_date = cur_date
                                elif login_info_yesterday and login_info_yesterday.get("login_time"):
                                    login_info = login_info_yesterday
                                    login_date = cur_date - datetime.timedelta(days=1)
 
 
                                if login_info and login_info.get("login_time"):
                                    existing_login = login_info["login_time"]
                                    if isinstance(existing_login, datetime.datetime):
                                        login_time_obj = existing_login
                                    elif isinstance(existing_login, datetime.time):
                                        login_time_obj = datetime.datetime.combine(login_date, existing_login)
                                    elif isinstance(existing_login, datetime.timedelta):
                                        total_seconds = int(existing_login.total_seconds())
                                        hours = total_seconds // 3600
                                        minutes = (total_seconds % 3600) // 60
                                        seconds = total_seconds % 60
                                        login_time_obj = datetime.datetime.combine(login_date, datetime.time(hours, minutes, seconds))
 
                                if login_time_obj:
                                    time_diff_hours = (current_time - login_time_obj).total_seconds() / 3600.0
                                    if time_diff_hours <= 15:
                                        logout_time = current_time.strftime("%H:%M:%S")
                                        DataAccess.insert_attendance1(employee_id, login_date, logout_time, loginflag=0, logoutflag=1, logout_location=matched_location_name)
                                        DataAccess.update_logout_time_face_data2(employee_id, login_date, logout_time, logout_location=matched_location_name)
                                        trace.info(f"[SUCCESS] Logout time updated for Employee {employee_id} at {logout_time} on {login_date}")
 
                                        payload = {"Tenant_id": "T001", "LogJson": {"EmployeeID": employee_id, "Date": login_date.strftime('%Y-%m-%d'), "Time": logout_time, "login_flag": "0", "logout_flag": "1"}}
                                        # encrypted_payload = encrypt_aes_cryptojs_compatible(payload, secret_key)
                                        payload_json = json.dumps(payload)
                                        trace.info(f"payload_json: {payload_json}")
                                        encrypted_payload = AESGCMCrypto.encrypt(payload_json, secret_key)
                                        trace.info(f"encrypted playload sending to ehr api: {encrypted_payload}")
                                        api_response = markEncryptedAttendanceApi(encrypted_payload)
                                        if 'encrypted' in api_response and api_response['encrypted']:
                                            trace.info(f"[API SUCCESS] Clock-out API response successful for {employee_id}")
                                        else:
                                            trace.info(f"[API FAILURE] Clock-out API response failure for {employee_id}: {api_response}")
                                    else:
                                        trace.info(f"[INFO] Clock-out blocked: Time diff {time_diff_hours:.2f}h exceeds 15h for employee {employee_id}")
                                else:
                                    message = "You have not clocked in yet"
                                    trace.info(f"[WARNING] {message} for employee {employee_id}")
                                    results.append({"employee_id": employee_id, "employee_name": employee_name, "message": message, "action_performed": action, "Time": current_time.strftime("%H:%M:%S"), "Date": cur_date.strftime("%Y-%m-%d")})

                           
                        else:
                            trace.info(f"[INFO] Employee {employee_id} is OUT of location by {distance:.2f} meters.")
                            if away_mode:
                                update_flag = request.form.get("update", "no").lower() == "yes"

                                attendance = DataAccess.get_out_location_status(employee_id, cur_date)
                                login_info = DataAccess.get_login_time_for_today(employee_id, cur_date)

                                login_time1 = None
                                logout_time1 = None

                                if attendance:
                                    login_time1 = attendance[0]["login_time"]
                                    logout_time1 = attendance[0]["logout_time"]

                                trace.info(f"[AWAY CHECK] login_info: {login_info}")

                                if action == "clock_in":

                                    # if login_info and login_info.get("login_time") and login_info.get("source") == "out_of_location":
                                    if login_time1:
                                        if not update_flag:
                                            message = "Already clock-in done (away mode)"
                                            trace.info(message)

                                        else:
                                            DataAccess.log_out_of_location_attendance(
                                                employee_id,
                                                employee_name,
                                                cur_date,
                                                current_time.strftime("%H:%M:%S"),
                                                action,
                                                lat,
                                                lon,
                                                int(distance)
                                            )

                                            message = "Clock-in updated (away mode)"
                                            trace.info(message)
                                            is_first_login = False

                                    else:
                                        DataAccess.log_out_of_location_attendance(
                                            employee_id,
                                            employee_name,
                                            cur_date,
                                            current_time.strftime("%H:%M:%S"),
                                            action,
                                            lat,
                                            lon,
                                            int(distance)
                                        )

                                        message = "Away clock-in recorded"
                                        is_first_login = True


                                elif action == "clock_out":
                                    
                                    # if login_info and login_info.get("logout_time") and login_info.get("source") == "out_of_location":
                                    if not login_info and login_info["source"] == "face_data2":
                                        message = "Cannot clock-out before clock-in"
                                    elif logout_time1:
                                        if not update_flag:
                                            message = "Already clock-out done (away mode)"
                                            trace.info(message)

                                        else:
                                            DataAccess.log_out_of_location_attendance(
                                                employee_id,
                                                employee_name,
                                                cur_date,
                                                current_time.strftime("%H:%M:%S"),
                                                action,
                                                lat,
                                                lon,
                                                int(distance)
                                            )

                                            message = "Clock-out updated (away mode)"
                                            trace.info(message)
                                            is_first_login = False

                                    else:

                                        DataAccess.log_out_of_location_attendance(
                                            employee_id,
                                            employee_name,
                                            cur_date,
                                            current_time.strftime("%H:%M:%S"),
                                            action,
                                            lat,
                                            lon,
                                            int(distance)
                                        )

                                        message = "Away clock-out recorded"
                                        is_first_login = True
                                
                                payload = {
                                    "Tenant_id": "T001",
                                    "LogJson": {
                                        "EmployeeID": employee_id,
                                        "Date": str(cur_date),
                                        "Time": current_time.strftime("%H:%M:%S"),
                                        "Lattitude": lat,
                                        "Longitude": lon,
                                        "Distance": int(distance),
                                        "Face_Actions": action,
                                        "Away_Status": "412"
                                    }
                                }
 
                                # Convert dict → JSON string
                                payload_json = json.dumps(payload)
 
                                trace.info(f"payload_json: {payload_json}")
 
                                # Encrypt JSON string
                                encrypted_payload = AESGCMCrypto.encrypt(payload_json, secret_key)
 
                                trace.info(f"encrypted payload sending to ehr api: {encrypted_payload}")
 
                                # Call API
                                api_response = markEncryptedAttendanceApiforoutoflocation(encrypted_payload)
 
                                if 'encrypted' in api_response and api_response['encrypted']:
                                    trace.info(f"[API SUCCESS] Clock-out API response successful for {employee_id}")
                                else:
                                    trace.info(f"[API FAILURE] Clock-out API response failure for {employee_id}: {api_response}")
 
                            else:
                                trace.info(f"[INFO] Out-of-location attendance skipped (away mode OFF)")
                                is_first_login = False
                                message = "Away-mode OFF, attendance not recorded"
 
 
                    except Exception as gps_error:
                        trace.info(f"[ERROR] GPS validation error for {employee_id}: {gps_error}")
 
            # Save face crop temporarily & dataset
            file_name = f"{employee_name}.jpg" if employee_name != "Unknown" else "unknown.jpg"
            face_image_original_path.append((face_crop, employee_name if is_known else "unknown", file_name))
            save_dir = "detected_faces"
            os.makedirs(save_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_name = f"{employee_name}_{employee_id or 'unknown'}_{timestamp}.jpg"
            save_path = os.path.join(save_dir, save_name)
            cv2.imwrite(save_path, face_crop)
 
            # Update face dataset
            face_dataset_dir = "face_dataset"
            os.makedirs(face_dataset_dir, exist_ok=True)
            if is_known and employee_id:
                target_file_name = f"{employee_name}_{employee_id}_(9).jpg"
                target_file_path = os.path.join(face_dataset_dir, target_file_name)
                if os.path.exists(target_file_path):
                    os.remove(target_file_path)
                    trace.info(f"[INFO] Removed old face dataset image for {employee_name} ({employee_id})")
                cv2.imwrite(target_file_path, face_crop)
                trace.info(f"[INFO] Saved latest face image to dataset: {target_file_path}")
            else:
                trace.info(f"[INFO] Skipped saving face dataset image for unknown face")
 
            results.append({
                "bounding_box": {"xmin": int(xmin), "ymin": int(ymin), "xmax": int(xmax), "ymax": int(ymax)},
                "confidence": confidence,
                "landmarks": landmarks,
                "is_known": is_known,
                "employee_id": employee_id,
                "employee_name": employee_name,
                "Time": current_time.strftime("%H:%M:%S"),
                "Date": cur_date.strftime("%Y-%m-%d"),
                "login_time": login_time,
                "is_first_login": is_first_login,
                "action_performed": action,
                "message": message
            })
 
        total_time = time.time() - start_time
        return jsonify({"faces": results, "processing_time": f"{total_time:.2f}s"}), 200
 
    except Exception as e:
        trace.info(f"[ERROR] detect_faces endpoint failed: {e}")
        return jsonify({"faces": [], "error": str(e)}), 500



def send_email(to_email, new_password):
    try:
        sender_email = "facerecognitionempulseglobal@gmail.com"
        sender_password = "hmagxzztcdgbgsjk"
 
        # Email content
        subject = "Your New Password"
        body = f"Your new password is {new_password}\n\nPlease change it after logging in."
 
        # Email setup
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))
 
        # Sending email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.set_debuglevel(1)  # Enable debugging
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
 
 
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
 
# Function to generate random password
def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choices(characters, k=length))
 
@app.route('/forget_password', methods=['POST'])
def forget_password():
    db_config = {
    'host': '192.168.2.137',
    'port': 3307,
    'user': 'central',
    'password': 'Empulse@12345',
    'database': 'face_attendence'
}
    data = request.get_json()
    email = data.get('email')
   
 
    if not email:
        return jsonify({'error': 'Email is required'}), 400
 
    try:
        # Connect to the database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
 
        # Check if the email exists
        query = "SELECT id FROM admins WHERE username = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
 
        if not user:
            return jsonify({'error': 'Email not found'}), 404
 
        # Generate a new random password
        new_password = generate_random_password()
        hashed_password = generate_password_hash(new_password)
        print("DEBUG - Temp password sent to user:", new_password)

 
        # Update the password in the database
        update_query = "UPDATE admins SET password = %s WHERE username = %s"
        cursor.execute(update_query, (hashed_password, email))
        connection.commit()
 
        # Send the new password to the user's email
        if send_email(email, new_password):
            return jsonify({'message': 'A new password has been sent to your email.'}), 200
        else:
            return jsonify({'error': 'Failed to send email. Please try again later.'}), 500
 
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': 'Database error. Please try again later.'}), 500
 
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
 






from werkzeug.security import check_password_hash, generate_password_hash
 
@app.route('/change_password', methods=['POST'])
def change_password():
    db_config = {
        'host': '192.168.2.137',
        'port': 3307,
        'user': 'central',
        'password': 'Empulse@12345',
        'database': 'face_attendence'
    }
 
    data = request.get_json()
    email = data.get('email')
    old_password = data.get('old_password')
    new_password = data.get('new_password')
 
    if not email or not old_password or not new_password:
        return jsonify({'error': 'All fields are required'}), 400
 
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
 
        # Get the existing hashed password
        query = "SELECT password FROM admins WHERE username = %s"
        cursor.execute(query, (email,))
        user = cursor.fetchone()
 
        if not user:
            return jsonify({'error': 'User not found'}), 404
 
        # Check if the old password matches
        if not check_password_hash(user['password'], old_password):
            return jsonify({'error': 'Old password is incorrect'}), 401
 
        # Hash the new password and update it
        hashed_new_password = generate_password_hash(new_password)
        update_query = "UPDATE admins SET password = %s WHERE username = %s"
        cursor.execute(update_query, (hashed_new_password, email))
        connection.commit()
 
        return jsonify({'message': 'Password changed successfully'}), 200
 
    except mysql.connector.Error as err:
        print(f"Database error: {err}")
        return jsonify({'error': f'Database error: {str(err)}'}), 500
 
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()




# #API to set the location and change RTSP URL
@app.route('/set_location/<location>', methods=['GET'])
def set_location(location):
    global current_rtsp_url, vid
    if location in rtsp_urls:
        # Release the previous video capture if it exists
        if vid is not None:
            vid.release()
            vid = None  # Reset the VideoCapture object

        current_rtsp_url = rtsp_urls[location]
        trace.info(f"Success: {current_rtsp_url}")
        return jsonify({"success": True, "url": current_rtsp_url}), 200
    else:
        trace.info("Invalid location")
        return jsonify({"success": False, "error": "Invalid location"}), 400


CORS(app, resources={r"/update_max_distance": {"origins": "http://localhost:4200"}}, 
          allow_headers=["Content-Type", "Authorization"])

# Route to update max_distance_ft
config_file_path = 'config.json'
@app.route('/update_max_distance', methods=['POST'])
def update_max_distance():
    try:
        # Parse the JSON data from the request
        data = request.get_json()
        if not data or 'max_distance_ft' not in data:
            trace.info("Invalid JSON format. 'max_distance_ft' key is missing.")
            return jsonify({"error": "Invalid JSON format. 'max_distance_ft' key is missing."}), 400
        
        max_distance = data['max_distance_ft']
        
        # Load the existing config.json
        with open(config_file_path, 'r') as f:
            config = json.load(f)

        # Update the max_distance_ft value
        config['distance_limits']['max_distance_ft'] = max_distance

        # Save the updated config.json
        with open(config_file_path, 'w') as f:
            json.dump(config, f, indent=4)

        # Return a success response
        trace.info(f"Max distance updated to {max_distance} feet")
        return jsonify({"message": f"Max distance updated to {max_distance} feet"}), 200

    except Exception as e:
        exc.exception(f"An error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

# API to get employees' attendance
@app.route('/employees', methods=['GET'])
def get_employees():
    DataAccess.db_details()  # Ensure database details are loaded
    DataAccess.connection_open()  # Open the connection once

    try:
        # Sample code to fetch all attendance data for today
        # Adjust date or parameters if required by the request query string
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Placeholder for query if specific employee name is passed
        name = request.args.get('name')
        
        # Check if the name parameter is provided, otherwise get all for the date
        if name:
            results = DataAccess.get_attendance_data_by_name_and_date(name, date)
            if results:
                employees = [{
                    'comp_id': 2,
                    'employee_id': results['employee_id'],
                    'date': results['data_date'].strftime('%Y-%m-%d'),
                    'time': results['ttime'],
                    'loginflag': results['loginflag'],
                    'logoutflag': results['logoutflag']
                }]
            else:
                employees = []
        else:
            # Alternative method if a method to retrieve all for a date is defined in DatabaseLayer
            # Assuming DataAccess has a method to fetch all for a date, we should define it
            employees = DataAccess.get_all_attendance_for_date(date)  # You may need to implement this function

        return jsonify(employees)

    except Exception as ex:
        print(f"Error fetching employees' attendance: {ex}")
        exc.exception(f"Error fetching employees' attendance: {ex}")
        return jsonify({'error': 'Failed to retrieve data'}), 500

    finally:
        DataAccess.connection_close()  # Close the connection when done

# Configure your JWT secret key
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Change this to a random secret key
jwt = JWTManager(app)



@app.route('/admin_add', methods=['POST', 'GET'])
def add_admin():
    data = request.get_json(force=True)
    if data is None:
        trace.info("Invalid input, JSON required.")
        return jsonify({'error': 'Invalid input, JSON required'}), 400
 
    username = data.get('username')
    password = data.get('password')
 
    if not username or not password:
        trace.info("Username and password are required")
        return jsonify({'error': 'Username and password are required'}), 400
 
    try:
        # Step 1: Check if email exists in employees_details table
        if not DataAccess.check_employee_email_exists(username):
            trace.info(f"Email {username} not found in employee records.")
            return jsonify({'error': 'Email ID not found in employee records'}), 403
 
        # Step 2: Check if admin already exists
        if DataAccess.check_admin_exists(username):
            trace.info(f"Admin with username {username} already exists.")
            return jsonify({'error': 'User already exists'}), 409
 
        # Step 3: Proceed to create admin
        hashed_password = generate_password_hash(password)
        DataAccess.insert_admin(username, hashed_password)
 
        access_token = create_access_token(identity=username)
        return jsonify({
            'message': 'User created successfully',
            'token': access_token
        }), 201
 
    except Exception as e:
        exc.exception(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/admin/<int:id>', methods=['POST'])
def update_admin(id):
    data = request.get_json(force=True)
    if data is None:
        trace.info("error: Invalid input, JSON required")
        return jsonify({'error': 'Invalid input, JSON required'}), 400

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        trace.info("error: Username and password are required")
        return jsonify({'error': 'Username and password are required'}), 400

    hashed_password = generate_password_hash(password)

    try:
        DataAccess.update_admin(id, username, hashed_password)
        trace.info("message: User role updated successfully")
        return jsonify({'message': 'User role updated successfully'}), 200
    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def encrypt_aes_cryptojs_compatible1(data, secret_key):
    """
    Encrypts a Python dict using AES-GCM for CryptoJS-compatible output.
    """
    plaintext = json.dumps(data).encode('utf-8')
    nonce = get_random_bytes(12)  # GCM standard nonce length
    cipher = AES.new(base64.b64decode(secret_key), AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)

    json_k = ['nonce', 'ciphertext', 'tag']
    json_v = [base64.b64encode(x).decode('utf-8') for x in (nonce, ciphertext, tag)]
    return dict(zip(json_k, json_v))


SECRET_KEY = 'klpn4huRzOKUkLybNWN+hHd6uILbDiGC/nupLKj+lGo='

@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Missing username or password"}), 400

    try:
        login_result = DataAccess.query_admin_table(username, password)

        if login_result and login_result["login_successful"]:
            access_token = create_access_token(identity={"username": username, "role": login_result.get("role")})
            trace.info(f"message: Login successful,token: {access_token},username:{username},role: {login_result.get('role')}")
            return jsonify({
                "message": "Login successful",
                "token": access_token,
                "username": username,
                "role": login_result.get("role")  # Ensure role is included
            }), 200
        else:
            trace.info("error: Invalid username or password")
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        exc.exception(f"error: Internal server error {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500






@app.route('/admin/get_all', methods=['POST'])
def get_all_admins():
    try:
        admins = DataAccess.get_all_admins()  # Call the method to fetch all admins
        return jsonify([dict(admin) for admin in admins]), 200  # Convert rows to dicts

    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/get_user/<username>', methods=['POST'])
def get_admin_by_username(username):
    try:
        admin = DataAccess.get_admin_by_username(username)  # Call the method to fetch the admin
        if admin:
            return jsonify(dict(admin)), 200  # Return admin details
        else:
            trace.info("message: User not found")
            return jsonify({'message': 'User not found'}), 404  # Handle user not found
    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({'error': str(e)}), 500  # Handle any exceptions
    





    
@app.route('/get_employee_by_id/<int:employee_id>', methods=['POST'])
def get_employee_by_id(employee_id):
    employee_details = DataAccess.get_employee_details_by_id(employee_id)  

    if employee_details:
        trace.info(f"{employee_details}")
        return jsonify(employee_details), 200
    else:
        trace.info("message: Employee not found")
        return jsonify({"message": "Employee not found"}), 404
  

## Testing the camera location

@app.route('/get_camera_details', methods=['GET'])
def get_camera_details():
    try:
        # Retrieve all camera details
        camera_details = DataAccess.get_camera_details()
        location = request.args.get('location')  # Get the location from query parameters

        # Check if a location is provided
        if location:
            # Find the camera details matching the location
            detail = next((detail for detail in camera_details if detail['location'] == location), None)
            
            if detail:
                # Return only the URL of the matched location
                trace.info(f"url: {detail['url']}")
                return jsonify({"url": detail['url']}), 200
            else:
                trace.info("message: Location not found")
                return jsonify({"message": "Location not found"}), 404
        else:
            # Return all camera details if no specific location is provided
            response = [
                {
                    "location": detail['location'],
                    "url": detail['url'],
                    "min_distance_ft": detail['min_distance_ft'],
                    "max_distance_ft": detail['max_distance_ft']
                } for detail in camera_details
            ]
            return jsonify(response), 200
    except Exception as e:
        print(f'Error retrieving camera details: {e}')
        exc.exception("error: Internal server error")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/update_camera_setup', methods=['POST'])
def update_camera_setup():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        trace.info(f"Invalid JSON: {str(e)}")
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400
    trace.info(f"Received data: {data}")
    logging.debug(f"Received data: {data}")

    # Validate that 'location' and 'url' are provided
    if not data or 'location' not in data or 'url' not in data:
        trace.info("error: Location or URL not provided")
        return jsonify({'error': 'Location or URL not provided'}), 400
    
    location = data['location']
    url = data['url']
    
    # Hardcoded min_distance_ft and max_distance_ft
    min_distance_ft = 0.5  # Hardcoded value
    max_distance_ft = data.get('max_distance_ft', 2.0)  # Can still accept max_distance_ft from request

    # Load existing config from config.json
    config_path = 'config.json'  # Specify your config file path here
    config = load_config(config_path)  # Pass the config_path

    config['RTSP_URLS'][location] = url
    save_config(config)

    # Store the new camera details using the DataAccess class
    try:
        DataAccess.insert_camera_details(location, url, min_distance_ft, max_distance_ft)
    except Exception as err:
        exc.exception(f"error: {str(err)}")
        return jsonify({'error': str(err)}), 500
    trace.info(f"message: RTSP URL added successfully, RTSP_URLS: {config['RTSP_URLS']}")
    return jsonify({'message': 'RTSP URL added successfully', 'RTSP_URLS': config['RTSP_URLS']}), 200


@app.route('/get_all_employees', methods=['GET'])
@jwt_required()
def get_all_employees():
    try:
        current_user = get_jwt_identity()
        trace.info(f"Accessing employee list by: {current_user}")
        trace.info(f"Token verified for user: {current_user}")
        # Retrieve all employee data from the database
        all_employees = DataAccess.get_all_employees()

        # Check if employee data was found
        if all_employees:
            trace.info(f"All Employee Data: {all_employees}")  # Corrected logging
            return jsonify(all_employees), 200
        else:
            trace.info("error: No employees found")
            return jsonify({"error": "No employees found"}), 404

    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

## updating the employee details using below api
@app.route('/get_employee/<int:employee_id>', methods=['GET'])
def get_employee(employee_id):
    try:
        # Retrieve employee data from the database using the provided employee_id
        employee_data = DataAccess.get_employee_id(employee_id)

        # Check if employee data was found
        if employee_data:
            trace.info(f"{employee_data}")
            return jsonify(employee_data), 200
        else:
            trace.info("error: Employee not found")
            return jsonify({"error": "Employee not found"}), 404

    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({"error": str(e)}), 500

    

@app.route('/delete_employee', methods=['POST'])
def delete_employee():
    # Retrieve employee_id from the request body
    data = request.get_json()
    employee_id = data.get('employee_id')

    # Check if employee_id is provided
    if not employee_id:
        trace.info("error: Missing employee ID")
        return jsonify({"error": "Missing employee ID"}), 400

    try:
        # Assuming DataAccess.delete_employee() performs the delete operation
        success = DataAccess.delete_employee(employee_id)
        
        # Debugging print statement
        print(f'Delete operation success: {success}, Employee ID: {employee_id}')
        trace.info(f'Delete operation success: {success}, Employee ID: {employee_id}')

        # Check if the deletion was successful
        if not success:
            trace.info("error: Employee not found or could not be deleted")
            return jsonify({"error": "Employee not found or could not be deleted"}), 404

        # Return success message
        trace.info("message: Employee deleted successfully!")
        return jsonify({"message": "Employee deleted successfully!"}), 200

    except Exception as e:
        exc.exception(f"error: {str(e)}")
        return jsonify({"error": str(e)}), 500










@app.route('/get_employee_data_by_location', methods=['GET'])
def get_employee_data():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_employee_data_by_location()

        # Return the data as a JSON response
        trace.info(f"{results}")
        return jsonify(results)

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        exc.exception(f"error: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route('/get_employee_details_from_single_location', methods=['POST'])
def get_employee_details_from_single_location():
    try:
        # Get the location from the JSON body of the request
        request_data = request.get_json()
        loc_name = request_data.get('location', None)
        
        if not loc_name:
            return jsonify({"error": "Location parameter is required"}), 400

        # Fetch the data using the DataAccess method
        results = DataAccess.get_employee_details_from_single_location(loc_name)

        # Return the data as a JSON response
        return jsonify(results)

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        return jsonify({"error": str(e)}), 500


##Below api is to get the employee face_data who are interested with perticulat location

@app.route('/get_missing_facedata', methods=['POST'])
def get_missing_facedata():
    try:
        # Get the location from the JSON body of the request
        request_data = request.get_json()
        location = request_data.get('location', None)

        # Validate if location is provided
        if not location:
            return jsonify({"status": "error", "message": "Location parameter is required"}), 400

        # Fetch missing face data using the DataAccess method
        results = DataAccess.get_missing_face_data_from_location(location)

        # Check if results are empty
        if not results:
            return jsonify({"status": "error", "message": "No missing face data found"}), 404

        # Return the results
        return jsonify({"status": "success", "data": results}), 200

    except Exception as e:
        # Log or return any errors
        print(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



@app.route('/get_missing_face_data_from_all_locations', methods=['GET'])
def get_missing_facedata_from_locations():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_missing_face_data_from_all_locations()

        # Return the data as a JSON response
        return jsonify(results)

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        return jsonify({"error": str(e)}), 500


@app.route('/get_time_difference', methods=['GET'])
def get_time_difference():
    try:
        # Call the DataAccess method to fetch data
        results = DataAccess.get_time_difference()

        # Check if the results contain an error
        if 'error' in results:
            print(f"Error in get_time_difference: {results['error']}")
            trace.info(f"Error in get_time_difference: {results['error']}")
            return jsonify(results), 500  # Return the error message as JSON

        # Return the data as a JSON response
        return jsonify(results)

    except Exception as e:
        # Log the exception
        exc.exception(f"Error fetching time difference: {str(e)}")
        print(f"Error: {str(e)}")

        # Return the error as a JSON response
        return jsonify({"error": str(e)}), 500


@app.route('/get_location_employees_count', methods=['GET'])
def get_location_employees_count():
    try:
        # Call the DataAccess method to fetch data
        results = DataAccess.get_single_location_employees_count()

        # Check if the results are empty
        if not results:
            print("No data found for any location.")
            trace.info("No data found for any location.")
            return jsonify({"message": "No data found for any location"}), 404

        # Return the data as a JSON response
        return jsonify(results)

    except Exception as e:
        # Log the exception
        exc.exception(f"Error fetching employee counts for all locations: {str(e)}")
        print(f"Error: {str(e)}")

        # Return the error as a JSON response
        return jsonify({"error": str(e)}), 500



@app.route('/get_menu_permissions', methods=['GET'])
def get_menu_permissions():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_menu_permissions()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No menu permissions found.")
            return jsonify({"message": "No menu permissions found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching menu permissions: {str(e)}")
        exc.exception(f"Error fetching menu permissions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_menu_permission_by_id/<int:permission_id>', methods=['GET'])
def get_menu_permission_by_id(permission_id):
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_menu_permission_by_id(permission_id)
        print(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            return jsonify({"message": "No menu permissions found"}), 404

        # Return the raw results directly as JSON
        return jsonify(results), 200

    except Exception as e:
        print(f"Error fetching menu permissions: {str(e)}")  # Log error
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_menu_data', methods=['GET'])
def get_menu_data():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_menu_data()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No menu data found.")
            return jsonify({"message": "No menu data found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching menu data: {str(e)}")
        exc.exception(f"Error fetching menu data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_roles', methods=['GET'])
def get_all_roles():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_all_roles()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No roles found.")
            return jsonify({"message": "No roles found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching roles data: {str(e)}")
        exc.exception(f"Error fetching roles data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/update_access', methods=['POST'])
def update_access():
    try:
        # Get the data from the JSON body of the request
        request_data = request.get_json()

        # Validate the request is an array of objects
        if not isinstance(request_data, list):
            return jsonify({"status": "error", "message": "Expected an array of objects"}), 400

        # Validate and process each object in the array
        results = []
        for item in request_data:
            role_id = item.get('role_id', None)
            menu_id = item.get('menu_id', None)
            access = item.get('access', None)

            # Validate if all required parameters are provided
            if role_id is None or menu_id is None or access is None:
                return jsonify({"status": "error", "message": "Each object must include role_id, menu_id, and access"}), 400

            # Validate that access is either 0 or 1
            if access not in [0, 1]:
                return jsonify({"status": "error", "message": "Access must be 0 or 1 for each object"}), 400

            # Call the DataAccess method to update access
            result = DataAccess.update_access(role_id, menu_id, access)
            results.append(result)

        # Return the aggregated results
        return jsonify({"status": "success", "message": "Access updated successfully", "data": results}), 200

    except Exception as e:
        # Log or return any errors
        print(f"Error: {e}")
        exc.exception(f"Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/get_admin_roles', methods=['GET'])
def get_admin_roles():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_admin_roles()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No admin roles found.")
            return jsonify({"message": "No admin roles found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching admin roles data: {str(e)}")
        exc.exception(f"Error fetching admin roles data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/delete_admin', methods=['POST'])
def delete_admin():
    try:
        # Parse the JSON request body
        data = request.get_json()

        # Validate that 'id' is provided
        if 'id' not in data:
            trace.info("Admin ID not provided in request.")
            return jsonify({"error": "Admin ID is required"}), 400

        admin_id = data['id']

        # Check if the admin ID is 1 and block deletion
        if admin_id == 2:
            trace.info("Attempt to delete the superadmin.")
            return jsonify({"error": "Admin with ID 1 cannot be deleted"}), 403

        # Call the DataAccess method to delete the admin
        result = DataAccess.delete_admin_by_id(admin_id)
        trace.info(f"Result: {result}")  # Log the result

        # Return success response
        return jsonify(result), 200

    except Exception as e:
        # Handle errors that occur during the deletion
        print(f"Error deleting admin: {str(e)}")
        exc.exception(f"Error deleting admin: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/update_admin_role', methods=['POST'])
def update_admin_role():
    try:
        # Parse the JSON request body
        data = request.get_json()
        admin_id = data.get("admin_id")
        role_id = data.get("role_id")

        # Validate the input data
        if not admin_id or not role_id:
            return jsonify({"error": "Missing required parameters"}), 400

        # Update the admin role using the DataAccess method
        result = DataAccess.update_admin_role(admin_id, role_id)
        trace.info(f"Update result: {result}")  # Log the result

        # Return the result
        return jsonify(result), 200

    except Exception as e:
        # Handle any errors that occur during the update
        print(f"Error updating admin role: {str(e)}")
        exc.exception(f"Error updating admin role: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/delete_role', methods=['POST'])
def delete_role():
    try:
        # Parse the JSON request body
        data = request.get_json()

        # Validate that 'role_id' is provided
        if 'role_id' not in data:
            trace.info("Role ID not provided in request.")
            return jsonify({"error": "Role ID is required"}), 400

        role_id = data['role_id']

        # Call the DataAccess method to delete the role
        result = DataAccess.delete_role_by_id(role_id)
        trace.info(f"Result: {result}")  # Log the result

        # Return success response
        return jsonify(result), 200

    except Exception as e:
        # Handle errors that occur during the deletion
        print(f"Error deleting role: {str(e)}")
        exc.exception(f"Error deleting role: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500



@app.route('/get_admin_permissions', methods=['GET'])
def get_admin_permissions():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_admin_permissions()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No admin permissions found.")
            return jsonify({"message": "No admin permissions found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching admin permissions: {str(e)}")
        exc.exception(f"Error fetching admin permissions: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_admin_permissions_with_role_name', methods=['GET'])
def get_admin_permissions_with_role_name():
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_admin_permissions_with_role_name()
        trace.info(f"Results: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info("No admin permissions with role names found.")
            return jsonify({"message": "No admin permissions with role names found"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching admin permissions with role name: {str(e)}")
        exc.exception(f"Error fetching admin permissions with role name: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_admin_permissions_with_role_name_by_role_id/<int:role_id>', methods=['GET'])
def get_admin_permissions_with_role_name_by_role_id(role_id):
    try:
        # Fetch the data using the DataAccess method
        results = DataAccess.get_admin_permissions_with_role_name_by_role_id(role_id)
        trace.info(f"Results for role_id {role_id}: {results}")  # Log the retrieved results

        # Check if the results are empty
        if not results:
            trace.info(f"No admin permissions found for role_id {role_id}.")
            return jsonify({"message": f"No admin permissions found for role_id {role_id}"}), 404

        # Return the data as a JSON response
        return jsonify(results), 200

    except Exception as e:
        # Handle any errors that occur during the data retrieval
        print(f"Error fetching admin permissions with role name for role_id {role_id}: {str(e)}")
        exc.exception(f"Error fetching admin permissions with role name for role_id {role_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    

@app.route('/get_time_difference_by_date', methods=['POST'])
def get_time_difference_by_date():
    try:
        # Extract input_date from the JSON body
        input_data = request.get_json()
        print(f"Received input_data: {input_data}")  # Log received data
        trace.info(f"Received input_data: {input_data}")

        if not input_data:
            return jsonify({"error": "Request body is missing or invalid JSON"}), 400

        input_date = input_data.get("input_date")
        if not input_date:
            print("Missing 'input_date' parameter")
            trace.info("Missing 'input_date' parameter")
            return jsonify({"error": "Missing 'input_date' parameter"}), 400

        # Fetch the data using the DataAccess method
        results = DataAccess.get_time_difference_using_date(input_date)
        print(f"Results fetched for date {input_date}: {results}")  # Log results

        if not results or ('message' in results[0] and results[0]['message'] == 'No data'):
            print(f"No data found for date {input_date}")
            trace.info(f"No data found for date {input_date}")
            return jsonify({"message": f"No data found for date {input_date}"}), 404

        return jsonify({"data": results}), 200

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Log exception details
        exc.exception(f"Error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500    







from flask_jwt_extended import jwt_required, get_jwt_identity
 
@app.route('/get_time_difference_by_date_range', methods=['POST'])

@jwt_required()

def get_time_difference_by_date_range():

    try:

        current_user = get_jwt_identity()

        trace.info(f"{current_user} is requesting time difference by date range.")
 
        input_data = request.get_json()

        print(f"Received input_data: {input_data}")

        trace.info(f"Received input_data: {input_data}")

        if not input_data:

            return jsonify({"error": "Request body is missing or invalid JSON"}), 400

        start_date = input_data.get("start_date")

        end_date = input_data.get("end_date")

        admin_email = input_data.get("admin_email")

        role_id = input_data.get("role_id")

        if not start_date or not end_date or not admin_email or role_id is None:

            return jsonify({"error": "Missing required parameters"}), 400

        # Fetch data from DB layer

        results = DataAccess.get_time_difference_between_dates(start_date, end_date, admin_email, role_id)

        print(f"Results fetched for range {start_date} to {end_date}: {results}")

        trace.info(f"Results fetched: {results}")

        if not results or ('message' in results[0] and results[0]['message'] == 'No data'):

            return jsonify({"message": f"No data found for range {start_date} to {end_date}"}), 404

        return jsonify({"data": results}), 200

    except Exception as e:

        print(f"Error occurred: {str(e)}")

        exc.exception(f"Error occurred: {str(e)}")

        return jsonify({"error": "Internal server error"}), 500

 



@app.route('/face_data_empl_count_timediff_emp_location', methods=['GET', 'POST'])
def face_data_empl_count_timediff_emp_location():
    try:
        if request.method == 'GET':
            # Extract SP name and params from query arguments
            sp_name = request.args.get('sp_name')
            if not sp_name:
                return jsonify({"error": "Stored procedure name is required"}), 400

            # Fetch parameters from query args (optional)
            params = request.args.to_dict(flat=True)
            params.pop('sp_name', None)  # Remove sp_name from params

        elif request.method == 'POST':
            # Parse JSON body for SP name and parameters
            data = request.get_json()
            if not data or 'sp_name' not in data:
                return jsonify({"error": "Stored procedure name is required"}), 400

            sp_name = data['sp_name']
            params = data.get('params', {})  # Default to an empty dict if no params provided

        # Call the DataAccess specific method
        results = DataAccess.face_data_empl_count_timediff_emp_location(sp_name, params)

        # Return the results as a JSON response
        return jsonify(results)

    except Exception as e:
        exc.exception(f"Error executing stored procedure {sp_name}: {str(e)}")
        return jsonify({"error": str(e)}), 500




@app.route('/get_employee_summary', methods=['POST'])
def get_employee_summary():
    try:
        # Parse the JSON request body
        data = request.get_json()

        # Check if 'data' is provided and not empty; if empty, set to None
        input_date = data.get('date', None)
        if input_date == "":
            input_date = None  # Treat empty string as NULL

        # Call the DataAccess method to fetch the employee summary
        result = DataAccess.get_employee_summary_with_date(input_date)

        # Return the result as a JSON response
        return jsonify(result), 200

    except Exception as e:
        # Capture exception details for debugging
        error_message = f"Error fetching employee summary: {str(e)}"
        print(error_message)  # Print to the console (or log it)

        # Return a detailed error message to the client
        return jsonify({"error": error_message}), 500


@app.route('/get_message_by_festival', methods=['POST'])
def get_message_by_festival():
    try:
        # Extract festival_name from the JSON body
        input_data = request.get_json()
        print(f"Received input_data: {input_data}")  # Log received data
        trace.info(f"Received input_data: {input_data}")

        if not input_data:
            return jsonify({"error": "Request body is missing or invalid JSON"}), 400

        festival_name = input_data.get("festival_name")
        if not festival_name:
            print("Missing 'festival_name' parameter")
            trace.info("Missing 'festival_name' parameter")
            return jsonify({"error": "Missing 'festival_name' parameter"}), 400

        # Fetch the data using the DataAccess method
        results = DataAccess.get_message_by_festival(festival_name)
        print(f"Results fetched for festival {festival_name}: {results}")  # Log results

        if not results or ('message' in results[0] and results[0]['message'] == 'No data'):
            print(f"No data found for festival {festival_name}")
            trace.info(f"No data found for festival {festival_name}")
            return jsonify({"message": f"No data found for festival {festival_name}"}), 404

        return jsonify({"data": results}), 200

    except Exception as e:
        print(f"Error occurred: {str(e)}")  # Log exception details
        exc.exception(f"Error occurred: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_message', methods=['GET'])
def get_message():
    # Load existing config from config.json
    config_path = 'config.json'  # Specify your config file path here
    try:
        config = load_config(config_path)  # Assuming you have a load_config function
        message = config.get('MESSAGE', None)  # Retrieve the MESSAGE key
    except Exception as e:
        trace.info(f"Error loading config: {str(e)}")
        return jsonify({'error': f"Error loading config: {str(e)}"}), 500

    if message is None:
        trace.info("Message not found in config.json")
        return jsonify({'error': 'Message not found in config.json'}), 404

    trace.info(f"Message retrieved successfully: {message}")
    return jsonify({'message': message}), 200









@app.route('/add_message', methods=['GET'])
def get_message_gif():
    config = load_config('config.json')
    message = config.get('MESSAGE')
    gif_path = config.get('GIF_PATH')  # e.g., "uploads/das_2_1728697195438.webp"

    # Make the path absolute relative to the static folder
    static_folder = app.static_folder  # usually 'static'
    absolute_gif_path = os.path.join(static_folder, gif_path)

    if not gif_path or not os.path.exists(absolute_gif_path):
        return jsonify({'error': 'GIF not found'}), 404

    # Build the URL relative to the static folder
    gif_url = url_for('static', filename=gif_path, _external=True)

    return jsonify({
        'message': message,
        'gif_url': gif_url
    }), 200



#### To get time_difference single day data

@app.route('/get_time_difference_by_single_date', methods=['POST'])
def get_time_difference_by_single_date():
    try:
        # Log the raw request body
        print(f"Raw request body: {request.data}")

        # Manually parse the JSON using json.loads()
        input_data = json.loads(request.data.decode("utf-8"))
        print(f"Manually parsed JSON: {input_data}")
        trace.info(f"Manually parsed JSON: {input_data}")

        if not input_data:
            return jsonify({"error": "Request body is missing or invalid JSON"}), 400

        single_date = input_data.get("date")

        if not single_date:
            return jsonify({"error": "Missing 'date' parameter"}), 400

        # Fetch the data using the DataAccess method
        results = DataAccess.get_time_difference_for_single_date(single_date)
        print(f"Results fetched for date {single_date}: {results}")
        trace.info(f"Results fetched for date {single_date}: {results}")

        if not results or ('message' in results[0] and results[0]['message'] == 'No data'):
            return jsonify({"message": f"No data found for date {single_date}"}), 404

        # Format 'data_date' to "Thu, 06 Feb 2025"
        for record in results:
            if "data_date" in record and record["data_date"]:
                record["data_date"] = record["data_date"].strftime("%a, %d %b %Y")  # Format date

        # Return data in JSON format
        return jsonify({"date": single_date, "records": results}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Log the error in the terminal
        exc.exception(f"Error occurred: {e}") 

        return jsonify({"error": f"Internal server error: {str(e)}"}), 500  # Return the error message in the response


#### To get monthly average data









@app.route('/get_time_difference_by_date_range_monthly_average', methods=['POST'])
@jwt_required()
def get_time_difference_by_date_range_monthly_average():
    try:
        current_user = get_jwt_identity()
        trace.info(f"{current_user} is requesting monthly average time difference.")
 
        input_data = request.get_json()
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")
        email = input_data.get("email")
        role_id = input_data.get("role_id")
        if not start_date or not end_date or not email or not role_id:
            return jsonify({"error": "Missing required parameters"}), 400
        results = DataAccess.get_time_difference_between_dates_monthly_average(start_date, end_date, email, role_id)
        if not results or not results.get("daily_logins"):
            return jsonify({"message": f"No data found for range {start_date} to {end_date}"}), 404
        return jsonify(results), 200
    except Exception as e:
        exc.exception(f"API Error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_total_working_hours_by_date_range', methods=['POST'])
def get_total_working_hours_by_date_range():
    try:
        input_data = json.loads(request.data.decode("utf-8"))
        start_date = input_data.get("start_date")
        end_date = input_data.get("end_date")

        if not start_date or not end_date:
            return jsonify({"error": "Missing 'start_date' or 'end_date' parameter"}), 400

        results = DataAccess.get_total_working_hours_by_date_range(start_date, end_date)

        if not results:
            return jsonify({"message": f"No data found for range {start_date} to {end_date}"}), 404

        return jsonify({"total_working_hours": results}), 200

    except Exception as e:
        print(f"Error occurred: {e}")
        exc.exception(f"Error occurred: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    

def decrypt_data(encrypted_b64: str, secret_key: str):
    """
    Decrypts AES-GCM CryptoJS compatible encrypted Base64 string 
    and returns the parsed JSON object (dict or list).
    """
    decrypted_text = AESGCMCrypto.decrypt(encrypted_b64, secret_key)

    if decrypted_text is None:
        raise ValueError("Decryption failed (AESGCMCrypto returned None)")

    try:
        return json.loads(decrypted_text)
    except json.JSONDecodeError:
        raise ValueError("Decrypted text is not valid JSON")

    
def fetch_and_store_leave_data():
    from_date = "2025-03-01"
    to_date = datetime.datetime.now().strftime("%Y-%m-%d")
    url = "https://empulsehrms.com/ehr_application_api/src/public/GetLeaveDetails"
    payload = {"FromDate": from_date, "ToDate": to_date}
    headers = {
        "Content-Type": "application/json",
        "Referer": "https://empulsehrms.com"
    }




    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        trace.info(f"API Raw Response: {json.dumps(data, indent=2)}")

        if not isinstance(data, dict) or "encrypted" not in data:
            trace.info(f"Invalid data received from API: {data}")
            return {"error": "Invalid data format from API"}

        encrypted_data_b64 = data["encrypted"]
        if not encrypted_data_b64:
            trace.info(f"Missing 'encrypted' data in API response: {data}")
            return {"error": "No encrypted data in API response"}

        secret_key_str = '3a374c6f0e20f5656bb4b745ac8c0cb15056a339bc7a7bf836632b7b5143c7dd'

        decrypted_data = decrypt_data(encrypted_data_b64, secret_key_str)

        
     
        # trace.info(f"Decrypted Data: {json.dumps(decrypted_data, indent=2)}")

        # Extract the list of records
        if isinstance(decrypted_data, dict) and "data" in decrypted_data:
            leave_records = decrypted_data["data"]
            trace.info(f"Extracted leave records: {leave_records}")
        else:
            trace.info(f"'data' key missing in decrypted data: {decrypted_data}")
            return {"error": "Decrypted data does not contain 'data' key"}

        if not isinstance(leave_records, list):
            trace.info(f"'data' key is not a list: {leave_records}")
            return {"error": "Decrypted data 'data' is not a list of records"}

        if len(leave_records) == 0:
            trace.info("No leave records found after decryption")
            return {"message": "No leave records found after decryption"}

        # Store the data into DB
        trace.info(f"Storing {len(leave_records)} leave records into DB")
        return DataAccess._store_leave_data(leave_records, from_date, to_date)

    except requests.RequestException as e:
        trace.info(f"API request failed: {str(e)}")
        return {"error": f"Failed to fetch data: {str(e)}"}
    except ValueError as ve:
        trace.info(f"Decryption error: {str(ve)}")
        return {"error": f"Decryption failed: {str(ve)}"}
    except Exception as e:
        trace.info(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}


    




# ---------------- Your leave fetch function ----------------
def fetch_leave_data_task():
    try:
        trace.info("Running scheduled fetch_leave_data_task...")
        result = fetch_and_store_leave_data()  # Replace with actual function
        trace.info(f"Scheduled API response: {result}")
    except Exception as e:
        trace.info(f"Error in fetch_leave_data_task: {e}")


scheduler = BackgroundScheduler()
tz = timezone("Asia/Kolkata")

# Leave fetch job
today = datetime.date.today()
start_time = datetime.datetime.combine(today, datetime.time(9, 30))
end_time = datetime.datetime.combine(today, datetime.time(18, 0))

scheduler.add_job(
    fetch_leave_data_task,
    trigger=IntervalTrigger(
        hours=1,
        start_date=start_time,
        end_date=end_time,
        timezone=tz
    ),
    id="fetch_leave_data",
    replace_existing=True,
    misfire_grace_time=300
)


# Start scheduler
scheduler.start()
trace.info("Scheduler started with leave fetch")

@app.route('/fetch_leave_data', methods=['GET'])
def fetch_leave_data():
    result = fetch_and_store_leave_data()
    trace.info(result)
    return jsonify({"message": "Leave data fetched successfully", "result": result})




@app.route('/update_both_times', methods=['POST'])
def update_both_times():
    try:
        data = request.get_json()
 
        employeeID = data.get("employeeID")
        cur_date = data.get("date")
        login_time = data.get("login_time")
        logout_time = data.get("logout_time")
 
        if not employeeID or not cur_date:
            return jsonify({"error": "Missing required fields"}), 400
 
        DataAccess.update_both_login_logout(employeeID, cur_date, login_time, logout_time)
 
        return jsonify({
            "status": "success",
            "message": f"Times updated for employeeID {employeeID} on {cur_date}"
        })
 
    except Exception as e:
        print(f"Error in update_both_times: {e}")
        return jsonify({"error": str(e)}), 500






@app.route('/add_location', methods=['POST'])
def add_location():
    try:
        data = request.get_json()
        location_name = data.get('location_name')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        radius = data.get('radius')

        # Log received input
        trace.info(f"Received data for add_location: {data}")

        # Validate input
        if not all([location_name, latitude, longitude, radius]):
            trace.info("Missing required fields in request data.")
            return jsonify({"message": "Missing required fields"}), 400

        # Store in DB via DataAccess
        DataAccess.add_location(location_name, latitude, longitude, radius)
        trace.info("Location added successfully.")

        return jsonify({"message": "Location added successfully"}), 200

    except Exception as e:
        print(f"Error adding location: {str(e)}")
        trace.info(f"Error adding location: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/update_location', methods=['POST'])
def update_location():
    try:
        data = request.get_json()
        location_id = data.get('location_id')
        location_name = data.get('location_name')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        radius = data.get('radius')

        trace.info(f"Received data for update_location: {data}")

        if not all([location_id, location_name, latitude, longitude, radius]):
            trace.info("Missing required fields for updating location.")
            return jsonify({"message": "Missing required fields"}), 400

        DataAccess.update_location(location_id, location_name, latitude, longitude, radius)
        trace.info("Location updated successfully.")

        return jsonify({"message": "Location updated successfully"}), 200

    except Exception as e:
        trace.info(f"Error updating location: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
    

@app.route('/get_locations', methods=['GET'])
def get_locations():
    try:
        all_locations = DataAccess.get_all_locations()

        if all_locations:
            trace.info(f"All Location Data: {all_locations}")
            return jsonify(all_locations), 200
        else:
            trace.info("error: No locations found")
            return jsonify({"error": "No locations found"}), 404

    except Exception as e:
        print(f"API Exception: {e}")
        trace.info(f"error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route('/get_out_of_location_attendance', methods=['POST'])

def get_out_of_location_attendance():

    try:

        trace.info("API hit: /get_out_of_location_attendance")
 
        # Read JSON input

        input_data = request.get_json()

        if not input_data:

            return jsonify({"error": "Missing request body"}), 400
 
        p_email = input_data.get("email")

        p_role_id = input_data.get("role_id")
 
        if not p_email or not p_role_id:

            return jsonify({"error": "email and role_id are required"}), 400
 
        # Call DB layer with parameters

        attendance_records = DataAccess.get_out_of_location_attendance(p_email, p_role_id)
 
        if attendance_records:

            trace.info(f"API Response: Returning {len(attendance_records)} records.")

            return jsonify(attendance_records), 200

        else:

            trace.info("API Response: No out-of-location attendance data found.")

            return jsonify({"error": "No out-of-location attendance data found"}), 404
 
    except Exception as e:

        trace.error(f"API Exception: {e}")

        exc.exception(f"API Exception: {e}")

        return jsonify({"error": str(e)}), 50


@app.route('/update_out_of_location_status', methods=['POST'])
def update_out_of_location_status():
    try:
        data = request.get_json()
        p_id = data.get('id')
        p_status = data.get('status')  # 'approved' or 'declined'

        if not p_id or not p_status:
            return jsonify({"error": "Missing id or status"}), 400

        trace.info(f"API hit: /update_out_of_location_status with ID: {p_id}, status: {p_status}")

        # Step 1: Update status in DB via SP
        result = DataAccess.update_out_of_location_status(p_id, p_status)
        if "error" in result:
            return jsonify(result), 500

        # Step 2: Fetch updated attendance record using SP
        attendance_record = DataAccess.get_out_of_location_attendance_by_id_for_api(p_id)
        if not attendance_record:
            return jsonify({"error": "Attendance record not found"}), 404

        # Step 3: Determine login/logout flags based on action
        action = attendance_record['action']
        login_flag = "1" if action == "clock_in" else "0"
        logout_flag = "1" if action == "clock_out" else "0"

        # Helper function to handle timedelta / time / None
        def format_time(t):
            if t is None:
                return None
            if isinstance(t, datetime.timedelta):
                total_seconds = int(t.total_seconds())
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return t.strftime('%H:%M:%S')

        # Step 4: Prepare EHR payload
        payload = {
            "Tenant_id": "T001",
            "LogJson": {
                "EmployeeID": attendance_record['employee_id'],
                "Date": attendance_record['data_date'].strftime('%Y-%m-%d'),
                "Time": format_time(attendance_record['logout_time'] or attendance_record['login_time']),
                "login_flag": login_flag,
                "logout_flag": logout_flag
            }
        }
        # Step 7: Convert to JSON string before encryption
        payload_json = json.dumps(payload)
        trace.info(f"payload_json for out_of_location: {payload_json}")
        # Step 5: Encrypt and call EHR API
        # encrypted_payload = encrypt_aes_cryptojs_compatible(payload, secret_key)
        encrypted_payload = AESGCMCrypto.encrypt(payload_json, secret_key)
        trace.info(f"encrypted_payload for out_of_location: {encrypted_payload}")
        api_response = markEncryptedAttendanceApi(encrypted_payload)
        

        if 'encrypted' in api_response and api_response['encrypted']:
            trace.info(f"[API SUCCESS] EHR API successful for {attendance_record['employee_id']}.")
        else:
            trace.error(f"[API FAILURE] EHR API failed for {attendance_record['employee_id']}: {api_response}")

        return jsonify(result), 200

    except Exception as e:
        trace.error(f"API Exception: {e}")
        return jsonify({"error": str(e)}), 500




@app.route('/delete_location', methods=['POST'])
def delete_location():
    try:
        data = request.get_json()
        location_id = data.get('location_id')
 
        trace.info(f"Received data for delete_location: {data}")
 
        if not location_id:
            trace.info("Missing location_id in request.")
            return jsonify({"message": "Missing location_id"}), 400
 
        DataAccess.delete_location(location_id)
        trace.info("Location deleted successfully.")
 
        return jsonify({"message": "Location deleted successfully"}), 200
 
    except Exception as e:
        trace.info(f"Error deleting location: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@app.route('/get_attendance_summary', methods=['GET'])
@jwt_required()
def get_attendance_summary():
    try:
        current_user = get_jwt_identity()
        trace.info(f"{current_user} is requesting attendance summary.")

        # Get query params
        employee_id = request.args.get('employee_id')
        date = request.args.get('date')  # Format: YYYY-MM-DD
        email_id = request.args.get('email_id')

        summary_data = DataAccess.get_employee_attendance_summary(employee_id, date, email_id)

        trace.info(f"Attendance Data: {summary_data}")

        if summary_data:
            return jsonify(summary_data), 200
        else:
            return jsonify({"message": "No attendance data found"}), 404

    except Exception as e:
        exc.exception(f"API Error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    



 


@app.route('/my_profile', methods=['GET'])
@jwt_required()
def get_my_profile():
    try:
        identity = get_jwt_identity()
        trace.info("Identity:", identity)
 
        if not identity or 'username' not in identity:
            return jsonify({"error": "Invalid token or missing username"}), 401
 
        email = identity.get("username")
        trace.info("Email from token:", email)
 
        profile_data = DataAccess.get_profile_by_email(email)
 
        if profile_data:
            return jsonify(profile_data), 200
        else:
            return jsonify({"error": "Profile not found"}), 404
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500


PROFILE_PIC_FOLDER = os.path.join(os.getcwd(), 'uploads', 'profile_pics')
os.makedirs(PROFILE_PIC_FOLDER, exist_ok=True)




ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/uploads/profile_pics/<filename>')
def serve_profile_pic(filename):
    # return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    return send_from_directory(PROFILE_PIC_FOLDER, filename)


@app.route('/upload_profile_photo', methods=['POST'])
@jwt_required()
def upload_profile_photo():
    try:
        identity = get_jwt_identity()
        current_user_email = identity['username']

        file = request.files.get('profile_pic')
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid or missing file"}), 400

        import uuid
        unique_id = uuid.uuid4().hex[:8]
        filename = secure_filename(f"{current_user_email}_{unique_id}_{file.filename}")

        file_path = os.path.join(PROFILE_PIC_FOLDER, filename)  # ✅ changed
        file.save(file_path)

        success = DataAccess.save_profile_pic(current_user_email, filename)

        if success:
            image_url = f"/uploads/profile_pics/{filename}"
            return jsonify({"message": "Profile photo uploaded", "url": image_url}), 200
        else:
            return jsonify({"error": "DB update failed"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/delete_profile_photo', methods=['DELETE'])
@jwt_required()
def delete_profile_photo():
    try:
        identity = get_jwt_identity()
        current_user_email = identity['username']

        # Get current profile photo filename from DB
        filename = DataAccess.get_profile_pic(current_user_email)
        if not filename:
            return jsonify({"error": "No profile photo found"}), 404
        file_path = os.path.join(PROFILE_PIC_FOLDER, filename)  

        
        # Delete the file from disk if it exists
        if os.path.exists(file_path):
            os.remove(file_path)

        # Remove reference from DB
        success = DataAccess.delete_profile_pic(current_user_email)
        if success:
            return jsonify({"message": "Profile photo deleted"}), 200
        else:
            return jsonify({"error": "Failed to update database"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/add_employee', methods=['POST'])
@jwt_required()
def add_employee():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
 
    required = ["Employee_ID", "Employee_Name",
                "Employee_Email", "Location", "Shift", "manager_id"]
    if not all(field in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400
 
    # --- 1️⃣ Check uniqueness ---------------------------------
    if DataAccess.get_employee_by_id(data["Employee_ID"]):
        return jsonify({"error": "User already exists"}), 409
 
    if DataAccess.get_employee_by_email(data["Employee_Email"]):
        return jsonify({"error": "User already exists"}), 409
 
    # --- 2️⃣ Insert employee ----------------------------------
    try:
        inserted = DataAccess.add_employee(
            data["Employee_ID"],
            data["Employee_Name"],
            data["Employee_Email"],
            data["Location"],
            data["Shift"],
            data["manager_id"]
        )
    except Exception as e:
        # Log the actual error so you can debug DB issues
        app.logger.exception("Insert failed")
        return jsonify({"error": "Failed to add employee"}), 500
 
    # --- 3️⃣ Final response -----------------------------------
    if inserted:
        return jsonify({"message": "User added successfully"}), 201
    else:
        return jsonify({"error": "Failed to add user"}), 500
 

@app.route('/edit_employee', methods=['POST'])
@jwt_required()
def edit_employee():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
 
    emp_id = data.get("Employee_ID")
    if not emp_id:
        return jsonify({"error": "Employee ID is required"}), 400
 
    # Fetch current record
    existing = DataAccess.get_employee_by_id(emp_id)
    if not existing:
        return jsonify({"error": f"Employee ID {emp_id} not found"}), 404
 
    # Use current values as defaults if a field is missing
    new_name   = data.get("Employee_Name", existing["Employee_Name"])
    new_loc    = data.get("Location", existing["Location"])
    new_shift  = data.get("Shift", existing["Shift"])
    new_mgr_id = data.get("manager_id", existing.get("manager_id"))
 
    ok = DataAccess.edit_employee(
        emp_id, new_name, new_loc, new_shift, new_mgr_id
    )
 
    if ok:
        return jsonify({"message": "User updated successfully"}), 200
    else:
        return jsonify({"error": "Failed to update user"}), 500
 
 
@app.route('/my_profile_with_attendance', methods=['POST'])

@jwt_required()

def get_my_profile_with_attendance():

    try:

        # 1️⃣ Identity check

        identity = get_jwt_identity()

        if not identity or 'username' not in identity:

            return jsonify({"error": "Invalid token or missing username"}), 401

        email = identity.get("username")
 
        # 2️⃣ Input validation

        input_data = request.get_json()

        if not input_data:

            return jsonify({"error": "Missing request body"}), 400

        start_date = input_data.get("start_date")

        end_date = input_data.get("end_date")

        role_id = input_data.get("role_id")

        if not start_date or not end_date or role_id is None:

            return jsonify({"error": "Missing required parameters"}), 400
 
        # 3️⃣ Profile

        profile_data = DataAccess.get_profile_by_email(email)

        if not profile_data:

            return jsonify({"error": "Profile not found"}), 404

        emp_id = profile_data.get("Employee_ID")
 
        # 4️⃣ Attendance

        attendance_data = DataAccess.get_time_difference_between_dates(start_date, end_date, email, role_id)

        emp_attendance = [row for row in attendance_data if row.get("employeeID") == emp_id]

        emp_attendance_sorted = sorted(emp_attendance, key=lambda x: x['data_date'])
 
        # 5️⃣ Continuous 9-hour streak

        streak = 0

        today = datetime.date.today()

        for day in reversed(emp_attendance_sorted):

            data_date_val = day.get('data_date')

            total_time_diff = day.get('total_time_diff')

            logout_time = day.get('logout_time')
 
            if isinstance(data_date_val, str):

                try:

                    data_date_val = datetime.datetime.strptime(data_date_val, "%Y-%m-%d").date()

                except Exception:

                    continue
 
            if data_date_val == today and not logout_time:

                continue
 
            weekday = data_date_val.weekday()

            if weekday >= 5 and not total_time_diff:

                continue

            if not total_time_diff:

                break
 
            try:

                h, m = map(int, total_time_diff.split(':'))

                hours_worked = h + m / 60

            except Exception:

                break
 
            if hours_worked >= 9:

                streak += 1

            else:

                break
 
        # 6️⃣ Leave summary

        leave_summary = DataAccess.get_employee_leave_summary_by_date_range(email, start_date, end_date)

        total_leave_count = sum(int(item.get("LeaveCount", 0)) for item in leave_summary if item.get("LeaveCount"))

        leave_summary_data = {"summary": leave_summary, "total_leave_count": total_leave_count}
 
        # 7️⃣ Longest working day

        longest_work = {"data_date": None, "login_time": None, "logout_time": None, "hours_worked": "00:00"}

        for day in emp_attendance_sorted:

            total_time_diff = day.get('total_time_diff')

            if total_time_diff:

                try:

                    h, m = map(int, total_time_diff.split(':'))

                    current_duration = f"{h:02d}:{m:02d}"

                except Exception:

                    continue
 
                h_long, m_long = map(int, longest_work["hours_worked"].split(':'))

                if h * 60 + m > h_long * 60 + m_long:

                    longest_work.update({

                        "data_date": day.get('data_date'),

                        "login_time": day.get('login_time'),

                        "logout_time": day.get('logout_time'),

                        "hours_worked": current_duration

                    })
 
        # 8️⃣ Average work hours for 5,15,30,60,90 days

        avg_periods = {}

        for days in [5, 15, 30, 60, 90]:

            period_start = (today - datetime.timedelta(days=days - 1)).strftime("%Y-%m-%d")

            period_end = today.strftime("%Y-%m-%d")
 
            avg_result = DataAccess.get_time_difference_between_dates_monthly_average(period_start, period_end, email, role_id)

            if isinstance(avg_result, list) and avg_result:

                avg_periods[f"{days}_days_average"] = avg_result[0].get("average_hours_per_day", "00:00")

            else:

                avg_periods[f"{days}_days_average"] = "00:00"
 
        # 9️⃣ Last 3 full months average

        last_3_months_avg = {}

        first_of_current = today.replace(day=1)

        for i in range(1, 4):

            month_date = first_of_current - relativedelta(months=i)

            month_start = month_date.replace(day=1).strftime("%Y-%m-%d")

            next_month_start = (month_date + relativedelta(months=1)).replace(day=1).strftime("%Y-%m-%d")

            month_end = (datetime.datetime.strptime(next_month_start, "%Y-%m-%d") - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

            month_name = month_date.strftime("%B")
 
            avg_result = DataAccess.get_time_difference_between_dates_monthly_average(month_start, month_end, email, role_id)

            if isinstance(avg_result, list) and avg_result:

                last_3_months_avg[month_name] = avg_result[0].get("average_hours_per_day", "00:00")

            else:

                last_3_months_avg[month_name] = "00:00"
 
        # 1️⃣0️⃣ Final output

        combined_result = {

            "profile": profile_data,

            "day_wise_summary": emp_attendance_sorted,

            "leave_summary": leave_summary_data,

            "continuous_9hr_streak": streak,

            "longest_working_day": longest_work,

            "average_work_hours": avg_periods,

            "last_3_months_average": last_3_months_avg

        }
 
        return jsonify(combined_result), 200
 
    except Exception as e:

        trace.exception(f"Error in get_my_profile_with_attendance: {str(e)}")

        return jsonify({"error": str(e)}), 500
 
 
#--------------------------------------
DATASET_PATH = r"face_dataset"
 
def check_employee_by_id(dataset_path, emp_id):
    emp_id = str(emp_id)
    pattern = re.compile(rf"_{emp_id}($|[^0-9])")
 
    for filename in os.listdir(dataset_path):
        name_without_ext = os.path.splitext(filename)[0]
        if pattern.search(name_without_ext):
            return True
 
    return False
 
@app.route("/check_employee", methods=["POST"])
def check_employee():
    data = request.get_json()
    emp_name = data.get("EmpName")
    emp_id = data.get("EmpId")
 
    if not emp_id:
        return jsonify({
            "success": False,
            "message": "EmpId is required"
        }), 400
 
    emp_id = str(emp_id)
    pattern = re.compile(rf"_{emp_id}($|[^0-9])")
 
    image_count = 0
 
    for file in os.listdir(DATASET_PATH):
        name_without_ext = os.path.splitext(file)[0]
 
        if pattern.search(name_without_ext):
            image_count += 1
 
    exists = image_count >= 2   # Must have at least 2 images
 
    return jsonify({
        "EmpName": emp_name,
        "EmpId": emp_id,
        "image_count": image_count,
        "exists": exists
    })
        

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=8081, debug=True,use_reloader=False)
    # app.run(host='0.0.0.0', port=8080, ssl_context=('C:\Users\user\cert.pem', 'C:\Users\user\key.pem'))

 



