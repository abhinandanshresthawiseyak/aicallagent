import datetime
import os,sys
# Add the project root directory to sys.path and then import llm_handler from callbot
sys.path.append('./')
from dbconn import models
from dbconn.database import SessionLocal, engine
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import uvicorn, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone
# import pytz
import logging
# Create the database tables
models.Base.metadata.create_all(bind=engine)

# Configure logging to output to the console
logging.basicConfig(level=logging.INFO , format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

@app.post("/call_logs/")
def create_call_log(caller_id:str, event_type: str, event_detail: str = None, db: Session = Depends(get_db)):
    db_call_log = models.CallLog(caller_id=caller_id, event_type=event_type, event_detail=event_detail)
    db.add(db_call_log)
    db.commit()
    db.refresh(db_call_log)
    return db_call_log

@app.get("/call_logs/")
def read_call_logs(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return db.query(models.CallLog).offset(skip).limit(limit).all()

@app.post("/populate_docker_callhandler")
def populate_docker_callhandler(ip_range_start: str, ip_range_end: str, db:Session=Depends(get_db)):

    start = int(ip_range_start.split('.')[-1]) # get 101 from 192.x.x.101
    end = int(ip_range_end.split('.')[-1]) # get 105 from 192.1x.x.105

    # Base part of the IP address
    base_ip = '.'.join(ip_range_start.split('.')[:-1]) # get 192.x.x
    id=1

    for i in range(start,end+1):
        for j in range(1,3):
            container_ip=f"{base_ip}.{i}"
            container_status_record = models.DockerCallHandler(id=id, container_name="audiosocket-"+str(i), container_ip=container_ip, client_id=j, max_clients=2, extension=i, active=False,data_json=None)
            db.add(container_status_record)
            db.commit()
            db.refresh(container_status_record)
            id+=1
        
@app.get("/get_container_status")
def get_container_status(db: Session = Depends(get_db)):
    return db.query(models.DockerCallHandler).all()

# @app.get("/get_freed_containerip")
# def get_freed_containerip(db: Session = Depends(get_db)):
#     # Query to get all container_ip where active_clients < max_clients
#     result = db.query(models.DockerCallHandler.container_ip).filter(
#         models.DockerCallHandler.active_clients < models.DockerCallHandler.max_clients
#     ).all()
    
#     # Extract container_ip from the result and return as a list
#     return [container_ip[0] for container_ip in result][0]

@app.patch("/update_container_status")
def update_container_status(extension: int, client_id: int, active: bool, db:Session=Depends(get_db)):
    container = db.query(models.DockerCallHandler).filter(models.DockerCallHandler.extension == extension , models.DockerCallHandler.client_id == client_id).first()

    if not container:
        raise HTTPException(status_code=404, detail="container not found")
    
    container.active = active
    container.modified_on_utc = datetime.now(timezone.utc)  # Use timezone.utc directly
    
    db.commit()
    db.refresh(container)
    return container

# POST request to create a user by directly passing parameters
@app.post("/users/")
def create_user(
    caller_id: str,
    name: str,
    phone_number: str,
    call_type: str,
    tts_folder_location: str,
    status: str,
    assigned_container: str,
    scheduled_for_utc: datetime,
    db: Session = Depends(get_db)
):
    db_user = models.UserDetails(
        caller_id=caller_id,
        name=name,
        phone_number=phone_number,
        call_type=call_type,
        tts_folder_location=tts_folder_location,
        status=status,
        assigned_container=assigned_container,
        scheduled_for_utc=scheduled_for_utc
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# GET request to retrieve all users with optional pagination
@app.get("/users/")
def get_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(models.UserDetails).offset(skip).limit(limit).all()
    return users

# GET request to retrieve a user by ID
@app.get("/users/{phone_number}")
def get_user(phone_number: str, db: Session = Depends(get_db)):
    user = db.query(models.UserDetails).filter(models.UserDetails.phone_number == phone_number).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# GET request to retrieve a user by assigned_container
@app.get("/assigned_container_user")
def get_assigned_container_user(assigned_container: str, db: Session = Depends(get_db)):
    user = db.query(models.UserDetails).filter(models.UserDetails.assigned_container == assigned_container,
        models.UserDetails.status == 'called').first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# PATCH request to update a user's status
@app.patch("/users/status/{phone_number}")
def update_user_status(phone_number: str, status: str, db: Session = Depends(get_db)):
    # Find the user by ID
    user = db.query(models.UserDetails).filter(models.UserDetails.phone_number == phone_number).first()
    
    # Check if the user exists
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update the user's status
    user.status = status
    # user.scheduled_for_utc = datetime.now(timezone.utc)  # Update the modified timestamp
    user.modified_on_utc = datetime.now()

    # Commit the changes to the database
    db.commit()
    db.refresh(user)
    
    return user


# @app.get("/voip_users")
# def read_voip_users(db: Session = Depends(get_db)):
#     return db.query(models.VoIPUsers).all()

# @app.post("/voip_users/{ip_range_start}/{ip_range_end}")
# def populate_voip_users(ip_range_start: str, ip_range_end: str, db:Session=Depends(get_db)):

#     # Extract the last octet from the IP addresses
#     start = int(ip_range_start.split('.')[-1])
#     end = int(ip_range_end.split('.')[-1])

#     if start == 111:
#         host_start=151

#     # Base part of the IP address
#     base_ip = '.'.join(ip_range_start.split('.')[:-1])

#     id=1
#     # Loop through the range and print the IPs
#     for i in range(start, end + 1):
#         server_ip=f"{base_ip}.{i}"
#         host_ip=f"{base_ip}.{host_start}"
#         voip_user_record = models.VoIPUsers(id=id, server_ip=server_ip,host_ip=host_ip ,status="Free")
#         db.add(voip_user_record)
#         db.commit()
#         db.refresh(voip_user_record)
#         id+=1
#         host_start+=1

#     return {'message':'Success'}

# @app.patch("/voip_users/{server_ip}/{status}")
# def update_voip_users(server_ip: str, status:str, db:Session=Depends(get_db)):
#     user = db.query(models.VoIPUsers).filter(models.VoIPUsers.server_ip == server_ip).first()

#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
    
    
#     user.status = status
#     user.modified_on_utc = datetime.now(timezone.utc)  # Use timezone.utc directly
    
#     db.commit()
#     db.refresh(user)
#     return user


@app.post("/call")
def call(number:str, extension: int):
    # Define the URL and authentication
    url = "http://192.168.89.100:8088/ari/channels"
    auth = HTTPBasicAuth('test', 'test123')

    # Define the data payload
    data = {
        'endpoint': f'PJSIP/{number}@fusionPBX-Trunk-015970296',
        'extension': str(extension),
        'context': 'internal',
        'priority': '1',
        'callerId': 'CallerID'
    }

    response = requests.post(url, auth=auth, data=data)
    return {'Code':response.status_code, 'Response':response.text}


@app.post("/test-call")
def test_call(number):
    # Define the URL and authentication
    url = "http://192.168.89.100:8088/ari/channels"
    auth = HTTPBasicAuth('test', 'test123')

    # Define the data payload
    data = {
        'endpoint': f'PJSIP/{number}@fusionPBX-Trunk-015970296',
        'extension': '6',
        'context': 'internal',
        'priority': '1',
        'callerId': 'CallerID'
    }

    response = requests.post(url, auth=auth, data=data)
    return {'Response':'200 OK'}
    # return response


# @app.post("/call/{phone_number}")
# def call(phone_number: str):
#     base_url="http://localhost:8001/voip_users"
#     response = requests.get(f"{base_url}")

#     if response.status_code == 200:
#         available_servers = [row for row in response.json() if row['status'] != 'Busy']
#         if len(available_servers) == 0:
#             return {'message': 'All asterisk servers are busy'}
#         else:
#             assigned_server = available_servers[0]  # Get the first available server
#             assigned_server_ip = assigned_server['server_ip']
#             host_ip = assigned_server['host_ip']  # Retrieve corresponding host_ip

#     # Construct the URL to Post Request and initiate call using available asterisk server
#     url = f"http://{host_ip}/call/{phone_number}/{assigned_server_ip}"

#     # Make the POST request
#     try:
#         response = requests.post(url)

#         # Check the response status
#         if response.status_code == 200:
#             print(f"Call initiated successfully to {phone_number} using server {assigned_server_ip}")
#             return {'message': response.json() }# Assuming the server responds with a JSON body
#         else:
#             print(f"Failed to initiate call. Status code: {response.status_code}")
#             return {'message': response.text}
#     except requests.RequestException as e:
#         print(f"Error occurred: {e}")
#         return {'message': str(e)}
    

uvicorn.run(app, host="0.0.0.0", port=80)
# uvicorn.run(app,  port=8001)
