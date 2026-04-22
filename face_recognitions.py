import datetime
import cv2
import json
import numpy as np
from common import FolderView
from multiprocessing.pool import ThreadPool
from utils1 import OutputTransform
import monitors
from processor.OpenvinoFaceRecognition.logger import trace, exc
import argparse
import logging
# from app_new1 import get_face_embedding, compare_with_dataset

face_pool = ThreadPool(processes=10)
annotation_list = []

# Initialize the logger
exc = logging.getLogger(__name__)

def load_config(config_path):
    """Load the JSON configuration from the specified path."""
    with open(config_path, 'r') as file:
        config = json.load(file)
    return config

def draw_detections(frame, frame_processor, detections, output_transform, img_h, img_w, face_path,config_path):
    try:
        # Load configuration
        config = load_config(config_path)
        min_distance_ft = config['distance_limits']['min_distance_ft']
        max_distance_ft = config['distance_limits']['max_distance_ft']
        
        global annotation_list
        fra = frame.copy()
        size = frame.shape[:2]
        frame = output_transform.resize(frame)
        face_ids_paths = []
        original_path = face_path + '/Original'
        detected_face_path = face_path + '/Detected_face/'
        unknown_face_path = face_path + '/Unknown_faces/'
        detected_face_date_path = detected_face_path + str(datetime.datetime.now().strftime("%d_%m_%Y"))
        unknown_face_date_path = unknown_face_path + str(datetime.datetime.now().strftime("%d_%m_%Y"))
        face_image_original_path = original_path + "/FaceDetection{}.jpeg".format(
            str(datetime.datetime.now().strftime("%d%m%Y%H%M%S")))
        face_image_path = face_path + "/FaceDetection{}.jpeg".format(
            str(datetime.datetime.now().strftime("%d%m%Y%H%M%S")))

        # Constants for distance calculation
        real_face_width_ft = 0.46  # Average face width in feet (5.5 to 6 inches)
        focal_length_px = 800  # You may need to adjust this based on your camera
        
        for roi, landmarks, identity in zip(*detections):
            text = frame_processor.face_identifier.get_identity_label(identity.id)
            name = text.split("_")
            xmin = max(int(roi.position[0]), 0)
            ymin = max(int(roi.position[1]), 0)
            xmax = min(int(roi.position[0] + roi.size[0]), size[1])
            ymax = min(int(roi.position[1] + roi.size[1]), size[0])
            xmin, ymin, xmax, ymax = output_transform.scale([xmin, ymin, xmax, ymax])

            # Calculate the perceived width of the face in pixels
            perceived_width_px = xmax - xmin
            
            # Estimate distance: D = (W * F) / P
            distance_ft = (real_face_width_ft * focal_length_px) / perceived_width_px
            
            # Filter faces between the loaded min and max distances
            if min_distance_ft <= distance_ft <= max_distance_ft:
                crp = fra[ymin:ymax, xmin:xmax]
                FolderView(face_path).createfolder()
                FolderView(original_path).createfolder()
                FolderView(detected_face_path).createfolder()
                FolderView(detected_face_date_path).createfolder()
                FolderView(unknown_face_path).createfolder()
                FolderView(unknown_face_date_path).createfolder()
    
                org_h, org_w, _ = frame.shape
                xmin = int(xmin * img_w / org_w)
                ymin = int(ymin * img_h / org_h)
                xmax = int(xmax * img_w / org_w)
                ymax = int(ymax * img_h / org_h)
    
                if text != "Unknown":
                    person_face_crop_path = detected_face_date_path + '/' + name[0] + "@{}.jpeg".format(
                        str(datetime.datetime.now().strftime("%H%M%S%f")))
                    cv2.imwrite(person_face_crop_path, crp, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    face_ids_paths.append((crp, name, person_face_crop_path))
                    cv2.putText(frame, name[0], (xmin, ymin - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 1)
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 225, 0), 1)
                else:
                    person_face_crop_path = unknown_face_date_path + '/' + name[0] + "@{}.jpeg".format(
                        str(datetime.datetime.now().strftime("%H%M%S%f")))
                    cv2.imwrite(person_face_crop_path, crp, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (0, 0, 255), 1)
            else:
                print(f"Face detected outside of {min_distance_ft}-{max_distance_ft} feet range (distance: {distance_ft} feet). Ignoring detection.")
                # trace.info(f"Face detected outside of {min_distance_ft}-{max_distance_ft} feet range (distance: {distance_ft} feet). Ignoring detection.")
 
        return frame, fra, face_ids_paths
    except Exception as ex:
        exc.exception(f"Error in draw_detections function in attendance face recognition: {ex}")
        return None, None, None


def attendance_face_identifier_main(face_rec_queue, frame_num, frame_processor, presenter, output_transform, args, cam_name, img_h, img_w, face_path, min_distance_ft, max_distance_ft):
    try:
        global annotation_list
        frame = face_rec_queue
        face_detect_flag = False
        
        if frame_num == 0:
            output_transform = OutputTransform(frame.shape[:2], args.output_resolution)
            output_resolution = (frame.shape[1], frame.shape[0])
            presenter = monitors.Presenter(args.utilization_monitors, 55,
                                           (round(output_resolution[0] / 4), round(output_resolution[1] / 8)))
        
        detections = frame_processor.process(frame)
        
        if detections[0]:
            face_detect_flag = True
        
        presenter.drawGraphs(frame)
        
        face_ret_value = face_pool.apply_async(draw_detections, (frame, frame_processor, detections,
                                                         output_transform, img_h, img_w, face_path,r"C:\inetpub\wwwroot\FRS_backend_mob\config.json"))

        
        face_ret = face_ret_value.get()
        
        # Ensure that face_ret is valid and contains the expected structure
        if face_ret is not None and len(face_ret) == 3:
            frame = face_ret[0]
            face_image_original_path = face_ret[2]  # Make sure this is a list or iterable
            return frame, presenter, output_transform, face_detect_flag, face_image_original_path
        else:
            print("No valid face image paths returned.")
            trace.info("No valid face image paths returned.")
            return frame, presenter, output_transform, face_detect_flag, []  # Return empty list instead of None

            
    except Exception as ex:
        print(f'Error Occurred in Face Recognition {ex} in camera name {cam_name}')
        exc.exception(f'Error Occurred in Face Recognition {ex} in camera name {cam_name}')
        return frame, presenter, output_transform, face_detect_flag, None  # Return None for face_image_original_path


