facelogWithAtimeApi = "http://103.2.232.82:8081/ehrnew20/empulse_ehr_apinew/src/public/face_time_login"

# facelogWithAtimeApi1 = "https://empulsehrms.com/ehr_application_uat_api/src/public/FaceTimeLogin"

##original API
facelogWithAtimeApi1 = "https://empulsehrms.com/ehr_application_api/src/public/FaceTimeLogin"

##Testing API
# facelogWithAtimeApi1 = "https://empulsehrms.com/ehr_application_uat_api/src/public/FaceTimeLogin"


# out_of_location  = "https://empulsehrms.com/ehr_application_uat_api/src/public/AwayAttendanceInsert"
out_of_location  = "https://empulsehrms.com/ehr_application_api/src/public/AwayAttendanceInsert"
 

ehr_location_api= "https://empulsehrms.com/ehr_application_api/src/public/getLocationList"
ehr_location_headers = {
            "Referer": "https://empulsehrms.com/"
        }

ehr_location_api_testing= "https://empulsehrms.com/ehr_application_uat_api/src/public/getLocationList"
ehr_location_headers_testing = {
            "Referer": "https://empulsehrms.com/"
        }
 
 

# Validate Attendance API
VALIDATE_ATTENDANCE_API = "https://empulsehrms.com/ehr_application_api/src/public/ValidateAttendance"
VALIDATE_ATTENDANCE_HEADERS = {
    "Referer": "https://empulsehrms.com/"
}


# SMTP Config
SMTP_CONFIG = {
    "server": "smtp.gmail.com",
    "port": 587,
    "username": "facerecognitionempulseglobal@gmail.com",
    "password": "hmagxzztcdgbgsjk"  # Use Gmail App Password
}



