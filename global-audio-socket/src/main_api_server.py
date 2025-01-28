import json
import os,sys
from typing import Optional
import uuid

from fastapi.responses import HTMLResponse
# Add the project root directory to sys.path and then import llm_handler from callbot
sys.path.append('./')
from dbconn import models
from dbconn.database import SessionLocal, engine
from fastapi import FastAPI, Depends, Form, HTTPException, Query
from sqlalchemy.orm import Session
import uvicorn, requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta, timezone
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

# Define the GET endpoint to display the form
@app.get("/", response_class=HTMLResponse)
def show_call_form():
    # Directly returning HTML content
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Make a Call</title>
        <style>
            .logo {
                width: auto; /* Automatically adjust width */
                height: 40px; /* Set a specific height */
                margin-bottom: 20px;
                display: block;
                animation: spin 5s linear infinite; /* Animation for rotation */
            }

            @keyframes spin {
                from {
                transform: rotate(0deg);
                }
                to {
                transform: rotate(360deg);
                }
            }
            body {
                font-family: Arial, sans-serif; /* Sets a clean, modern font for the page */
                background-image: linear-gradient(to bottom, rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)), url('https://images.leadconnectorhq.com/image/f_webp/q_80/r_1200/u_https://storage.googleapis.com/msgsndr/b17H9oWDbOh07ygUe3gg/media/66d79cbfab806e5e553081e3.jpeg'); /* Black gradient overlay on top of the background image */
                background-size: cover; /* Covers the entire background without repeating */
                background-position: center; /* Centers the background image */
                margin: 0;
                padding: 20px;
            }
            form {
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1); /* Adds a subtle shadow to the form */
                width: fit-content; /* Ensures the form width fits its content */
                margin: auto; /* Centers the form horizontally */
                display: block; /* Ensures the form takes its own line */
            }
            h3 {
                text-align: center; /* Centers the title */
                color: black; /* Dark grey color for the text */
            }
            label {
                font-size: 16px; /* Increases font size for readability */
                color: #555; /* A darker grey for text */
            }
            input[type="text"],
            input[type="number"] {
                padding: 8px;
                margin-top: 5px;
                margin-bottom: 15px;
                border: 1px solid #ccc;
                border-radius: 4px;
                display: block; /* Makes input take the full width of the form */
                width: 95%; /* Makes sure the input fields are not too wide */
            }
            button {
                background-color: #0079C1; /* A nice green background */
                color: white;
                padding: 10px 15px;
                border: none;
                border-radius: 4px;
                cursor: pointer; /* Changes the cursor to indicate it's clickable */
                width: 100%; /* Makes the button take full width of the form */
            }
            button:hover {
                background-color: #0079C9; /* A slightly darker green for hover effect */
            }
        </style>
    </head>
    <body>
        <img src="https://wiseyak.com/assets/WiseYakHexagonLogo-8f84b4e0.png" alt="WiseYak Logo" class="logo">
        <!----
        <form action="/call" method="post">
            <h3>Make a Call <br>(Extension: 106 for nepali(global) | Extension: 101 for english(isp))</h3>
            <label for="number">Phone Number:</label>
            <input type="text" id="number" name="number" value="9851100067" required><br>
            <label for="extension">Extension:</label>
            <input type="number" id="extension" name="extension" value="106" required><br>
            <button type="submit">Call</button>
        </form><br> --->

        <form action="/schedule_call" method="post">
            <h3>Schedule a Call (in minutes) Use minutes=0 for immediate. bank="global/nabil/bnb/shikhar/worldlink"</h3>
            <label for="number">Phone Number:</label>
            <input type="text" id="number" name="number" value="9851100067" required>
            <label for="schedule">Schedule (in minutes):</label>
            <input type="number" id="schedule" name="schedule" value="0" required>
            <label for="bank">Bank</label>
            <input type="text" id="bank" name="bank" value="global" required>
            <button type="submit">Call</button>
        </form>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/call_logs/")
def create_call_log(caller_id:str, event_type: str, event_detail: str = None, db: Session = Depends(get_db)):
    db_call_log = models.CallLog(caller_id=caller_id, event_type=event_type, event_detail=event_detail)
    db.add(db_call_log)
    db.commit()
    db.refresh(db_call_log)
    return db_call_log

@app.get("/call_logs/")
def read_call_logs(complete_interaction: bool, db: Session = Depends(get_db)):

    if complete_interaction:
        # Query to find caller_id with "Call Hangup - Playing" followed by "Call Ended"
        alias1 = models.CallLog.__table__.alias("e1")
        alias2 = models.CallLog.__table__.alias("e2")

        query = (
            db.query(alias1.c.caller_id)
            .join(alias2, alias1.c.caller_id == alias2.c.caller_id)
            .filter(
                alias1.c.event_type == "Call Hangup - Playing",
                alias2.c.event_type == "Call Ended",
                alias1.c.inserted_on_utc < alias2.c.inserted_on_utc
            )
            .distinct()
        )

        result = query.all()
        return [row[0] for row in result]
        # return db.query(models.CallLog).limit(limit).all()
    
    if not complete_interaction:
        '''
            SELECT 
                DISTINCT caller_id
            FROM call_logs
            WHERE event_type = 'Call Ended'
            AND caller_id NOT IN (
                SELECT 
                    DISTINCT caller_id
                FROM call_logs
                WHERE event_type = 'Call Hangup - Playing'
            );
        '''
        # ORM Query for "Call Ended" without "Call Hangup - Playing"
        subquery = (
            db.query(models.CallLog.caller_id)
            .filter(models.CallLog.event_type == "Call Hangup - Playing")
            .subquery()
        )

        result = (
            db.query(models.CallLog.caller_id)
            .filter(
                models.CallLog.event_type == "Call Ended",
                ~(models.CallLog.caller_id.in_(subquery))
            )
            .distinct()
            .all()
        )
        
        return [row.caller_id for row in result]

@app.get("/call_logs/{caller_id}")
def get_user(caller_id: str, db: Session = Depends(get_db)):
    try:
        # To find out which which audio file the agent pushes and also the what is the output of ASR
        user = db.query(models.CallLog).filter(
            models.CallLog.caller_id == caller_id, 
            models.CallLog.event_type.in_(['tts pushes','ASROutput'])
            ).all()
        
        # To find out the location of vad_output
        vad_output = db.query(models.CallLog).filter(
            models.CallLog.caller_id == caller_id, 
            models.CallLog.event_type.in_(['VAD Saves file'])
        ).all()

        # To find out call type json details for finding out what agent speaks
        user_details=db.query(models.UserDetails).filter(
            models.UserDetails.caller_id == caller_id
            ).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        response = {} # Define a combined single response for dashboard

        # Parse values from user_details object
        response['name']=user_details.name
        response['phone_number']=user_details.phone_number
        response['assigned_container']=user_details.assigned_container
        response['scheduled_for_utc']=user_details.scheduled_for_utc
        response['status']=user_details.status

        call_type=json.loads(user_details.call_type)
        response['call_type']=call_type['type']
        response['conversation'] = {}

        c=0 # counter for state of conversation like "conversation":{"1":{"agent":{},"customer":{}}} where 1 is the state
        v=0 # counter for vad_output

        # based on odd/even, we can distinguish the order of conversation if it's agent or customer; agent will on odd rows and customer will be on even rows
        for i, row in enumerate(user,start=1):
            if i%2==0:
                response['conversation'][str(c)]['customer']={}
                response['conversation'][str(c)]['customer']['speaks'] =  row.event_detail #call_type['question_audio_for_tts'][state][yesno] 
                response['conversation'][str(c)]['customer']['timestamp'] = row.inserted_on_utc
                response['conversation'][str(c)]['customer']['audio_path'] = '/home/bumblebee/wiseyak/abhi/global/global-audio-socket/'+vad_output[v].event_detail
                v+=1
            elif i%2==1:
                c+=1
                audio_file=row.event_detail.split('/')[-1].split('.')[-2] #  extract atm_capture2yes from atm_capture2yes.wav
                stateyesno=audio_file[len(call_type['type']):] # extract 2yes from atm_capture2yes
                state=stateyesno[0] # extract first element 2 which denotes state
                yesno=stateyesno[1:] # extract remaining part yes | no
                # print(call_type['question_audio_for_tts'],state,yesno)
                response['conversation'][str(c)]={}
                response['conversation'][str(c)]['agent'] = {}
                response['conversation'][str(c)]['agent']['speaks'] =  call_type['question_audio_for_tts'][state]['yes'] if state in ('1','5') else call_type['question_audio_for_tts'][state][yesno] #  row.event_detail 
                response['conversation'][str(c)]['agent']['timestamp']=row.inserted_on_utc

        return response
    except Exception as e:
        return {"error":e}

# @app.post("/populate_docker_callhandler")
# def populate_docker_callhandler(ip_range_start: str, ip_range_end: str, db:Session=Depends(get_db)):

#     start = int(ip_range_start.split('.')[-1]) # get 101 from 192.x.x.101
#     end = int(ip_range_end.split('.')[-1]) # get 105 from 192.1x.x.105

#     # Base part of the IP address
#     base_ip = '.'.join(ip_range_start.split('.')[:-1]) # get 192.x.x
#     id=1

#     for i in range(start,end+1):
#         for j in range(1,3):
#             container_ip=f"{base_ip}.{i}"
#             container_status_record = models.DockerCallHandler(id=id, container_name="audiosocket-"+str(i), container_ip=container_ip, client_id=j, max_clients=2, extension=i, active=False,data_json=None)
#             db.add(container_status_record)
#             db.commit()
#             db.refresh(container_status_record)
#             id+=1
        
# @app.get("/get_container_status")
# def get_container_status(db: Session = Depends(get_db)):
#     return db.query(models.DockerCallHandler).all()

# # @app.get("/get_freed_containerip")
# # def get_freed_containerip(db: Session = Depends(get_db)):
# #     # Query to get all container_ip where active_clients < max_clients
# #     result = db.query(models.DockerCallHandler.container_ip).filter(
# #         models.DockerCallHandler.active_clients < models.DockerCallHandler.max_clients
# #     ).all()
    
# #     # Extract container_ip from the result and return as a list
# #     return [container_ip[0] for container_ip in result][0]

# @app.patch("/update_container_status")
# def update_container_status(extension: int, client_id: int, active: bool, db:Session=Depends(get_db)):
#     container = db.query(models.DockerCallHandler).filter(models.DockerCallHandler.extension == extension , models.DockerCallHandler.client_id == client_id).first()

#     if not container:
#         raise HTTPException(status_code=404, detail="container not found")
    
#     container.active = active
#     container.modified_on_utc = datetime.now(timezone.utc)  # Use timezone.utc directly
    
#     db.commit()
#     db.refresh(container)
#     return container

@app.post("/users/", description="Endpoint is used to save details after pulling data from Global's API to TTS scheduling.")
def create_user(
    caller_id: str,
    name: str,
    phone_number: str,
    call_type: str,
    status: str,
    tts_folder_location: Optional[str] = None,
    assigned_container: Optional[str] = None,
    scheduled_for_utc: Optional[datetime] = None,
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

# # POST request to create a user by directly passing parameters
# @app.post("/users/")
# def create_user(
#     caller_id: str,
#     name: str,
#     phone_number: str,
#     call_type: str,
#     tts_folder_location: str,
#     status: str,
#     assigned_container: str,
#     scheduled_for_utc: datetime,
#     db: Session = Depends(get_db)
# ):
#     db_user = models.UserDetails(
#         caller_id=caller_id,
#         name=name,
#         phone_number=phone_number,
#         call_type=call_type,
#         tts_folder_location=tts_folder_location,
#         status=status,
#         assigned_container=assigned_container,
#         scheduled_for_utc=scheduled_for_utc
#     )
#     db.add(db_user)
#     db.commit()
#     db.refresh(db_user)
#     return db_user

# GET request to retrieve all users with optional pagination
@app.get("/users/")
def get_users(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    users = db.query(models.UserDetails).offset(skip).limit(limit).all()
    return users


# PATCH request to update a user's status
@app.patch("/users/status/{caller_id}", description="Endpoint is used to schedule Airflow to call at defined time in scheduled_for_utc. Update status = 'tts_saved_to_location' and scheduled_for_utc which will trigger Airflow. Make sure tts_folder_location is accurate.")
def update_user_status(
    caller_id: str, 
    call_type: str = Query(..., description="Type of the call which is json type"), 
    tts_folder_location: str = Query(..., description="Location of the TTS folder"), 
    status: str = Query(..., description="Current status of the user"), 
    assigned_container: str = Query(..., description="Container assigned to the user"), 
    scheduled_for_utc: datetime = Query(..., description="Scheduled time for the user in UTC"), 
    db: Session = Depends(get_db)
):
    user = db.query(models.UserDetails).filter(models.UserDetails.caller_id == caller_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.call_type = call_type
    user.tts_folder_location = tts_folder_location
    user.status = status
    user.assigned_container = assigned_container
    user.scheduled_for_utc = scheduled_for_utc
    user.modified_on_utc = datetime.now()

    db.commit()
    db.refresh(user)
    
    return user

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
    # user = db.query(models.UserDetails).filter(models.UserDetails.assigned_container == assigned_container,
    #     models.UserDetails.status == 'called').first()
    user = db.query(models.UserDetails).filter(
        models.UserDetails.assigned_container == assigned_container,
        models.UserDetails.status == 'tts_saved_to_location'
    ).order_by(models.UserDetails.scheduled_for_utc.asc()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.post("/schedule_call")
def schedule_call(number: str = Form(...), schedule:int= Form(...), bank:str=Form(), db: Session = Depends(get_db)):
    scheduled_time = datetime.utcnow() + timedelta(minutes=schedule)

    if bank=='global':
        user_id=str(uuid.uuid4())
        return create_user(
            caller_id=f"demo-scheduled-from-ui-global{user_id}",
            name="Pawan Ji",
            phone_number=number,
            call_type=json.dumps({'type': 'atm_capture',
 'out_state': 4,
 'question_audio_for_tts': {'1': {'yes': 'नमस्ते! म ग्लोबल बैंकबाट प्रतिवा बोल्दैछु! के तपाईं पवन जी बोल्दै हुनुहुन्छ!'},
  '2': {'yes': 'तपाईंको एटीएम कार्ड क्याप्चर भएको विषयमा कुरा गर्नु थियो। अहिले हजुरसँग कुरा गर्न मिल्छ?',
   'no': 'तपाईंको समयको लागि धन्यवाद। म कुनै पनि अवरोधको लागि क्षमा चाहन्छु।'},
  '3': {'yes': 'हामीले तपाईंको कार्डलाई अस्थायी रूपमा ब्लक गरेका छौं। तपाईंको कार्ड एक हप्ता पछि मात्र बैंकमा आउनेछ र कार्ड फिर्ता लिनको लागि तपाईं आफ्नो नागरिकता वा ड्राइभिङ लाइसेन्स वा पासपोर्ट लिएर ग्लोबल बैंकको कमलादी शाखामा जानुहोला।',
   'no': 'मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु। तपाईंको समयको लागि धन्यवाद।'},
  '4': {'no': 'मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु, तपाईंको समयको लागि धन्यवाद।'},
  '5': {'yes': 'हुन्छ, तपाईंको समयको लागि धन्यवाद। केही गार्हो पर्यो भने सम्पर्क गर्नुहोला।'}},
 'llm_states': {'1': {'positive': ['हो म पवन बोल्दै छु ',
    'हजुर हो पवन',
    'हजुर पवन बोल्दै छु ',
    'के कुरा को लागि हो',
    'हजुर भन्नुस म सुनिरहेको छु',
    'ओभाओ भन्नुस् न',
    'हजार भनोस् न के काम पर्यो',
    'हजार भनोस् न'],
   'negative': ['हैन',
    'हैन नि',
    'म त अर्कै मान्छे हो',
    'मेरो नाम त रमेश हो',
    'रंग नम्बर पर्यो',
    'रङ नम्बर पर्\u200dयो',
    'होइन']},
  '2': {'positive': ['मिल्छ',
    'मिल्छ मिल्छ',
    'हजुर भन्नुस न',
    'अहिले मिल्छ',
    'हजुर मिल छ'],
   'negative': ['अहिले त मिल्दैन',
    'मिल्दैन',
    'भोलि मात्रै मिल्छ',
    'एकै छिन पछि मात्रै मिल्छ',
    'अहिले मिल्दैन',
    'हजुर मिल दैन','अहिले busy']},
  '3': {'positive': ['हुन्छ',
    'हुन्छ, समय मिलाएर जान पर्ला',
    'धन्यवाद, म जान्छु',
    'म छिट्टै जान्छु'],
   'negative': ['हुँदैन',
    'अलि छिटो गर्न मिल्दैन?',
    'मलाई हतार छ, अलि चाँडो मिल्छ कि?',
    'म सँग अहिले डकुमेन्टहरू केही पनि छैन',
    'अलि समय पछि जाँदा पनि हुन्छ?']},
  '4': {'positive': ['बुझे', 'राम्ररी बुझे', 'बुझे नि, धन्यवाद'],
   'negative': ['बुझिन', 'बुझिएन']},
  'repeat': [['could you speak louder',
    "i can't hear you",
    'repeat',
    'repeat please',
    'can you speak alittle louder?',
    'pardon?',
    'can you repeat?',
    'could you repeat?',
    'मैले बुझिन',
    'मलाई फेरी भनि दिनुस न',
    'हजुरले के भन्नु भएको मैले बुझिन',
    'हजुर के भन्नु भाको?']]},
 'tts_next_states': {'1': {'yes': {'next_state': 2,
    'audio_file': 'atm_capture2yes.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'atm_capture2no.wav'},
   'repeat': {'next_state': 1, 'audio_file': 'atm_capture1.wav'}},
  '2': {'yes': {'next_state': 3, 'audio_file': 'atm_capture3yes.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'atm_capture3no.wav'},
   'repeat': {'next_state': 2, 'audio_file': 'atm_capture2yes.wav'}},
  '3': {'yes': {'next_state': 4, 'audio_file': 'atm_capture5.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'atm_capture4no.wav'},
   'repeat': {'next_state': 3, 'audio_file': 'atm_capture3yes.wav'}},
  '4': {'yes': {'audio_file': 'atm_capture5.wav'},
   'no': {'audio_file': 'atm_capture5.wav'},
   'repeat': {'next_state': 4, 'audio_file': 'atm_capture5.wav'}}}},ensure_ascii=False
  ),
            tts_folder_location="audios/Pawan Ji",
            status="tts_saved_to_location",
            assigned_container="global-audiosocket-102",
            scheduled_for_utc=scheduled_time,
            db=db
        )
    elif bank=='nabil':
        user_id=str(uuid.uuid4())
        return create_user(
            caller_id=f"demo-scheduled-from-ui-nabil{user_id}",
            name="Gyanendra Ji",
            phone_number=number,
            call_type=json.dumps({
                "type": "atm_capture",

                "out_state": 4,

                "question_audio_for_tts":{
                    "1":{
                        "yes": "नमस्ते! म नबिल बैंक लिमिटेड बाट प्रतिवा बोल्दैछु। के तपाईं ज्ञानेन्द्र जी बोल्दै हुनुहुन्छ?"
                    },
                    "2":{
                        "yes":"तपाईंको एटीएम कार्ड क्याप्चर भएको विषयमा कुरा गर्नु थियो। अहिले हजुरसँग कुरा गर्न मिल्छ?",
                        "no": "तपाईंको समयको लागि धन्यवाद। म कुनै पनि अवरोधको लागि क्षमा चाहन्छु।"
                    },
                    "3":{
                        "yes":"तपाईंको कार्ड तयार भएको छ र कार्ड फिर्ता लिनको लागि तपाईंले आफ्नो नागरिकता, ड्राइभिङ लाइसेन्स वा पासपोर्ट लिएर नबिल बैंकको कमलादी शाखामा जानुहोला।",
                        "no": "मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु। तपाईंको समयको लागि धन्यवाद।"
                    },
                    "4":{
                        "no": "मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु, तपाईंको समयको लागि धन्यवाद।"
                    },
                    "5":{
                        "yes":"हुन्छ, तपाईंको समयको लागि धन्यवाद। केही गार्हो पर्यो भने सम्पर्क गर्नुहोला।"
                    }
                },

                "llm_states":{
                    "1":{
                        "positive": ["हो म ज्ञानेन्द्र बोल्दै छु ", "हजुर हो ", "हजुर बोल्दै छु ", "के कुरा को लागि हो", "हजुर भन्नुस म सुनिरहेको छु", "ओभाओ भन्नुस् न", "हजार भनोस् न के काम पर्‍यो","हजार भनोस् न"],
                        "negative": ["हैन",  "हैन नि", "म त अर्कै मान्छे हो", "मेरो नाम त रमेश हो", "रंग नम्बर पर्यो", "रङ नम्बर पर्‍यो", "होइन"]
                    },
                    "2":{
                        "positive" : ["मिल्छ","मिल्छ मिल्छ","हजुर भन्नुस न", "अहिले मिल्छ", "हजुर मिल छ"],
                        "negative" : [ "अहिले त मिल्दैन", "मिल्दैन", "भोलि मात्रै मिल्छ", "एकै छिन पछि मात्रै मिल्छ", "अहिले मिल्दैन", "हजुर मिल दैन"]
                    },
                    "3":{
                        "positive" : ["हुन्छ", "हुन्छ, समय मिलाएर जान पर्ला", "धन्यवाद, म जान्छु", "म छिट्टै जान्छु"],
                        "negative" : ["हुँदैन", "अलि छिटो गर्न मिल्दैन?", "मलाई हतार छ, अलि चाँडो मिल्छ कि?", "म सँग अहिले डकुमेन्टहरू केही पनि छैन","अलि समय पछि जाँदा पनि हुन्छ?"]
                    },
                    "4":{
                        "positive" : ["बुझे","राम्ररी बुझे","बुझे नि, धन्यवाद"],
                        "negative" : ["बुझिन", "बुझिएन"]
                    },
                    "repeat": [["could you speak louder","i can't hear you","repeat","repeat please","can you speak alittle louder?", "pardon?", "can you repeat?", "could you repeat?","मैले बुझिन", "मलाई फेरी भनि दिनुस न", "हजुरले के भन्नु भएको मैले बुझिन", "हजुर के भन्नु भाको?"]]
                },
                
                "tts_next_states": {
                "1": {
                    "yes": {
                    "next_state": 2,
                    "audio_file": "atm_capture2yes.wav"
                    },
                    "no": {
                    "next_state": "out_state",
                    "audio_file": "atm_capture2no.wav"
                    },
                    "repeat": {
                    "next_state": 1,
                    "audio_file": "atm_capture1.wav"
                    }
                },
                "2": {
                    "yes": {
                    "next_state": 3,
                    "audio_file": "atm_capture3yes.wav"
                    },
                    "no": {
                    "next_state": "out_state",
                    "audio_file": "atm_capture3no.wav"
                    },
                    "repeat": {
                    "next_state": 2,
                    "audio_file": "atm_capture2yes.wav"
                    }
                },
                "3": {
                    "yes": {
                    "next_state": 4,
                    "audio_file": "atm_capture5.wav"
                    },
                    "no": {
                    "next_state": "out_state",
                    "audio_file": "atm_capture4no.wav"
                    },
                    "repeat": {
                    "next_state": 3,
                    "audio_file": "atm_capture3yes.wav"
                    }
                },
                "4": {
                    "yes": {
                    "audio_file": "atm_capture5.wav"
                    },
                    "no": {
                    "audio_file": "atm_capture5.wav"
                    },
                    "repeat": {
                    "next_state": 4,
                    "audio_file": "atm_capture5.wav"
                    }
                }
                }
            },ensure_ascii=False)
            ,
            tts_folder_location="audios/Gyanendra",
            status="tts_saved_to_location",
            assigned_container="global-audiosocket-103",
            scheduled_for_utc=scheduled_time,
            db=db
        )
    elif bank=='shikhar':
        user_id=str(uuid.uuid4())
        return create_user(
            caller_id=f"demo-scheduled-from-ui-shikharinsurance{user_id}",
            name="Ravi Basyal",
            phone_number=number,
            call_type=json.dumps(
  {'type': 'insurance_claim',
 'out_state': 4,
 'question_audio_for_tts': {'1': {'yes': 'नमस्ते! म शिखर इन्स्योरेन्सबाट निर्मला बोल्दैछु। के तपाईं रवि बस्याल जी बोल्दै हुनुहुन्छ?'},
  '2': {'yes': 'हामीलाई तपाईंको गाडीको बीमा दावीको बारेमा कुरा गर्नु थियो। अहिले हजुरसँग कुरा गर्न मिल्छ?',
   'no': 'तपाईंको समयको लागि धन्यवाद। म कुनै पनि अवरोधको लागि क्षमा चाहन्छु।'},
  '3': {'yes': 'तपाईंको बीमा दावीको प्रक्रिया सुरू गरिएको छ। ५ दिनको भित्र हामीले तपाईंलाई अपडेट पठाउनेछौं, हुन्छ?',
   'no': 'मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु। तपाईंको समयको लागि धन्यवाद।'},
  '4': {'no': 'हुन्छ, मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु। तपाईंको समयको लागि धन्यवाद।'},
  '5': {'yes': 'हुन्छ, तपाईंको समयको लागि धन्यवाद। कुनै पनि समस्या आएमा हामीलाई सम्पर्क गर्नुहोस्।'}},
 'llm_states': {'1': {'positive': ['हो म रवि बस्याल बोल्दै छु',
    'हो रवि बस्याल हो',
    'हजुर हो',
    'हजुर बोल्दै छु',
    'के कुरा को लागि हो',
    'हजुर भन्नुस म सुनिरहेको छु',
    'ओभाओ भन्नुस न',
    'हजार भनोस् न के काम पर्यो',
    'हजार भनोस् न'],
   'negative': ['हैन',
    'हैन नि',
    'म त अर्कै मान्छे हो',
    'मेरो नाम त रमेश हो',
    'रंग नम्बर पर्यो',
    'रङ नम्बर पर्यो',
    'होइन']},
  '2': {'positive': ['मिल्छ',
    'मिल्छ मिल्छ',
    'हजुर भन्नुस न',
    'अहिले मिल्छ',
    'हजुर मिल छ'],
   'negative': ['अहिले त मिल्दैन',
    'मिल्दैन',
    'भोलि मात्रै मिल्छ',
    'एकै छिन पछि मात्रै मिल्छ',
    'अहिले मिल्दैन',
    'हजुर मिल दैन']},
  '3': {'positive': ['हुन्छ',
    'हुन्छ, समय मिलाएर जान पर्ला',
    'धन्यवाद, म जान्छु',
    'म छिट्टै जान्छु'],
   'negative': ['हुँदैन',
    'अलि छिटो गर्न मिल्दैन?',
    'मलाई हतार छ, अलि चाँडो मिल्छ कि?',
    'म सँग अहिले डकुमेन्टहरू केही पनि छैन',
    'अलि समय पछि जाँदा पनि हुन्छ?']},
  '4': {'positive': ['बुझे', 'राम्ररी बुझे', 'बुझे नि, धन्यवाद'],
   'negative': ['बुझिन', 'बुझिएन']},
  'repeat': [['could you speak louder',
    "i can't hear you",
    'repeat',
    'repeat please',
    'can you speak alittle louder?',
    'pardon?',
    'can you repeat?',
    'could you repeat?',
    'मैले बुझिन',
    'मलाई फेरी भनि दिनुस न',
    'हजुरले के भन्नु भएको मैले बुझिन',
    'हजुर के भन्नु भाको?']]},
 'tts_next_states': {'1': {'yes': {'next_state': 2,
    'audio_file': 'insurance_claim2yes.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'insurance_claim2no.wav'},
   'repeat': {'next_state': 1, 'audio_file': 'insurance_claim1.wav'}},
  '2': {'yes': {'next_state': 3, 'audio_file': 'insurance_claim3yes.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'insurance_claim3no.wav'},
   'repeat': {'next_state': 2, 'audio_file': 'insurance_claim2yes.wav'}},
  '3': {'yes': {'next_state': 4, 'audio_file': 'insurance_claim5.wav'},
   'no': {'next_state': 'out_state', 'audio_file': 'insurance_claim4no.wav'},
   'repeat': {'next_state': 3, 'audio_file': 'insurance_claim3yes.wav'}},
  '4': {'yes': {'audio_file': 'insurance_claim5.wav'},
   'no': {'audio_file': 'insurance_claim5.wav'},
   'repeat': {'next_state': 4, 'audio_file': 'insurance_claim5.wav'}}}},ensure_ascii=False
  ),
            tts_folder_location="audios/Ravi Basyal",
            status="tts_saved_to_location",
            assigned_container="global-audiosocket-104",
            scheduled_for_utc=scheduled_time,
            db=db
        )
    elif bank=='bnb':
        user_id=str(uuid.uuid4())
        return create_user(
            caller_id=f"demo-scheduled-from-ui-bnb{user_id}",
            name="Arjun",
            phone_number=number,
            call_type=json.dumps(
{'type': 'doctor_appointment',
 'out_state': 4,
 'question_audio_for_tts': {'1': {'yes': 'नमस्ते! म बियनबि हस्पिटल बाट निर्मला बोल्दै छु! के तपाईं अर्जुन खत्रीजी बोल्दै हुनुहुन्छ!'},
  '2': {'yes': 'तपाईंको डाक्टरको अपोइन्टमेन्टको बारेमा कुरा गर्नु थियो। अहिले हजुरसँग कुरा गर्न मिल्छ?',
   'no': 'तपाईंको समयको लागि धन्यवाद। म कुनै पनि अवरोधको लागि क्षमा चाहन्छु।'},
  '3': {'yes': 'हामीले तपाईंको अपोइन्टमेन्ट सफलतापूर्वक बुक गरेका छौं। तपाईंको डाक्टर अर्जुन सिंहसंग तपाईंको अपोइन्टमेन्ट आइतबार ३ बजेलाई हुनेछ। कृपया समयमा अस्पतालमा आउने सुनिश्चित गर्नुहोस्।',
   'no': 'मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु। तपाईंको समयको लागि धन्यवाद।'},
  '4': {'no': 'मैले तपाईंको प्रतिक्रिया रेकर्ड गरेकी छु, तपाईंको समयको लागि धन्यवाद।'},
  '5': {'yes': 'हुन्छ, तपाईंको समयको लागि धन्यवाद। केही गार्हो पर्यो भने सम्पर्क गर्नुहोला।'}},
 'llm_states': {'1': {'positive': ['हो म अर्जुन खत्री बोल्दै छु',
    'हो अर्जुन खत्री हो',
    'हजुर हो',
    'हजुर बोल्दै छु',
    'के कुरा को लागि हो',
    'हजुर भन्नुस म सुनिरहेको छु',
    'ओभाओ भन्नुस् न',
    'हजार भनोस् न के काम पर्\u200dयो',
    'हजार भनोस् न'],
   'negative': ['हैन',
    'हैन नि',
    'म त अर्कै मान्छे हो',
    'मेरो नाम त रमेश हो',
    'रंग नम्बर पर्यो',
    'रङ नम्बर पर्\u200dयो',
    'होइन']},
  '2': {'positive': ['मिल्छ',
    'मिल्छ मिल्छ',
    'हजुर भन्नुस न',
    'अहिले मिल्छ',
    'हजुर मिल छ'],
   'negative': ['अहिले त मिल्दैन',
    'मिल्दैन',
    'भोलि मात्रै मिल्छ',
    'एकै छिन पछि मात्रै मिल्छ',
    'अहिले मिल्दैन',
    'हजुर मिल दैन']},
  '3': {'positive': ['हुन्छ, म आउँछु।',
    'हुन्छ, समयमै आउँछु।',
    'धन्यवाद, म आउँछु।',
    'म छिट्टै आउँछु।'],
   'negative': ['हुँदैन',
    'अलि छिटो गर्न मिल्दैन?',
    'मलाई हतार छ, अलि चाँडो मिल्छ कि?',
    'म सँग अहिले डकुमेन्टहरू केही पनि छैन',
    'अलि समय पछि जाँदा पनि हुन्छ?',
    'म आउन सक्दिन, माफ गर्नुहोस्।',
    'म आउन सक्दिन, अर्को पटकको लागि तय गर्न सक्छौं।']},
  '4': {'positive': ['बुझे', 'राम्ररी बुझे', 'बुझे नि, धन्यवाद'],
   'negative': ['बुझिन', 'बुझिएन']},
  'repeat': [['could you speak louder',
    "i can't hear you",
    'repeat',
    'repeat please',
    'can you speak a little louder?',
    'pardon?',
    'can you repeat?',
    'could you repeat?',
    'मैले बुझिन',
    'मलाई फेरी भनि दिनुस न',
    'हजुरले के भन्नु भएको मैले बुझिन',
    'हजुर के भन्नु भाको?']]},
 'tts_next_states': {'1': {'yes': {'next_state': 2,
    'audio_file': 'doctor_appointment2yes.wav'},
   'no': {'next_state': 'out_state',
    'audio_file': 'doctor_appointment2no.wav'},
   'repeat': {'next_state': 1, 'audio_file': 'doctor_appointment1.wav'}},
  '2': {'yes': {'next_state': 3, 'audio_file': 'doctor_appointment3yes.wav'},
   'no': {'next_state': 'out_state',
    'audio_file': 'doctor_appointment3no.wav'},
   'repeat': {'next_state': 2, 'audio_file': 'doctor_appointment2yes.wav'}},
  '3': {'yes': {'next_state': 4, 'audio_file': 'doctor_appointment5.wav'},
   'no': {'next_state': 'out_state',
    'audio_file': 'doctor_appointment4no.wav'},
   'repeat': {'next_state': 3, 'audio_file': 'doctor_appointment3yes.wav'}},
  '4': {'yes': {'audio_file': 'doctor_appointment5.wav'},
   'no': {'audio_file': 'doctor_appointment5.wav'},
   'repeat': {'next_state': 4, 'audio_file': 'doctor_appointment5.wav'}}}}
            ,ensure_ascii=False
            ),
            tts_folder_location="audios/Arjun",
            status="tts_saved_to_location",
            assigned_container="global-audiosocket-105",
            scheduled_for_utc=scheduled_time,
            db=db
        )
    elif bank=='worldlink':
        user_id=str(uuid.uuid4())
        return create_user(
            caller_id=f"demo-scheduled-from-ui-worldlink{user_id}",
            name="Sachin",
            phone_number=number,
            call_type=json.dumps(
                {
                    "type": "subscription_renewal",
                    "out_state": 4,
                    "question_audio_for_tts": {
                        "1": {
                            "yes": "नमस्ते! म worldlinkबाट प्रतिवा बोल्दैछु! के तपाईं {name} जी बोल्दै हुनुहुन्छ!"
                        },
                        "2": {
                            "yes": "तपाईंको इन्टरनेट सर्भिसको विषयमा कुरा गर्नु थियो। अहिले हजुरसँग कुरा गर्न मिल्छ?",
                            "no": "तपाईंको समयको लागि धन्यवाद। म कुनै पनि अवरोधको लागि क्षमा चाहन्छु।"
                        },
                        "3": {
                            "yes": "तपाईंको इन्टरनेट सर्भिस जनवरी २७ मा समाप्त हुँदैछ। के तपाईं रिन्यु गर्न चाहनुहुन्छ?",
                            "no": "तपाईंको प्रतिक्रिया रेकर्ड गरिएको छ, तपाईंको समयको लागि धन्यवाद।"
                        },
                        "4": {
                            "no": "मैले तपाईंको प्रतिक्रिया रेकर्ड गरेको छु, तपाईंको समयको लागि धन्यवाद।"
                        },
                        "5": {
                            "yes": "हुन्छ, तपाईंको समयको लागि धन्यवाद। केही पर्यो भने सम्पर्क गर्नुहोला।"
                        }
                    },
                    "llm_states": {
                        "1": {
                            "positive": ["म बोल्दैछु","हो म sachin बोल्दै छु ", "हजुर हो ", "हजुर बोल्दै छु ", "के कुरा को लागि हो", "हजुर भन्नुस म सुनिरहेको छु", "ओभाओ भन्नुस् न", "हजार भनोस् न के काम पर्‍यो", "हजार भनोस् न"],
                            "negative": ["हैन", "हैन नि", "म त अर्कै मान्छे हो", "मेरो नाम त रमेश हो", "रंग नम्बर पर्यो", "रङ नम्बर पर्‍यो", "होइन"]
                        },
                        "2": {
                            "positive": ["मिल्छ", "मिल्छ मिल्छ", "हजुर भन्नुस न", "अहिले मिल्छ", "हजुर मिल छ","मिल छ","मिल छ भन्नुस्"],
                            "negative": ["अहिले त मिल्दैन", "मिल्दैन", "अहिले मिल्दैन", "हजुर मिल दैन"]
                        },
                        "3": {
                            "positive": ["हुन्छ, रिन्यु गर्न चाहन्छु", "जी, म रिन्यु गर्ने योजनामा छु", "हुन्छ, नवीकरण गर्नुस्","हुन्छ"],
                            "negative": ["अहिले रिन्यु गर्दिन", "मलाई सोच्ने समय चाहिन्छ", "हुन्न, यो पटक रिन्यु गर्दिन"]
                        },
                        "4": {
                            "positive": ["बुझे", "राम्ररी बुझे", "बुझे नि, धन्यवाद"],
                            "negative": ["बुझिन", "बुझिएन"]
                        },
                        "repeat": [["could you speak louder", "i can't hear you", "repeat", "repeat please", "can you speak a little louder?", "pardon?", "can you repeat?", "could you repeat?", "मैले बुझिन", "मलाई फेरी भनि दिनुस न", "हजुरले के भन्नु भएको मैले बुझिन", "हजुर के भन्नु भाको?"]]
                    },
                    "tts_next_states": {
                        "1": {
                            "yes": {
                                "next_state": 2,
                                "audio_file": "subscription_renewal2yes.wav"
                            },
                            "no": {
                                "next_state": "out_state",
                                "audio_file": "subscription_renewal2no.wav"
                            },
                            "repeat": {
                                "next_state": 1,
                                "audio_file": "subscription_renewal1.wav"
                            }
                        },
                        "2": {
                            "yes": {
                                "next_state": 3,
                                "audio_file": "subscription_renewal3yes.wav"
                            },
                            "no": {
                                "next_state": "out_state",
                                "audio_file": "subscription_renewal3no.wav"
                            },
                            "repeat": {
                                "next_state": 2,
                                "audio_file": "subscription_renewal2yes.wav"
                            }
                        },
                        "3": {
                            "yes": {
                                "next_state": 4,
                                "audio_file": "subscription_renewal5.wav"
                            },
                            "no": {
                                "next_state": "out_state",
                                "audio_file": "subscription_renewal4no.wav"
                            },
                            "repeat": {
                                "next_state": 3,
                                "audio_file": "subscription_renewal3yes.wav"
                            }
                        },
                        "4": {
                            "yes": {
                                "audio_file": "subscription_renewal5.wav"
                            },
                            "no": {
                                "audio_file": "subscription_renewal5.wav"
                            },
                            "repeat": {
                                "next_state": 4,
                                "audio_file": "subscription_renewal5.wav"
                            }
                        }
                    }
                }
            ,ensure_ascii=False
            ),
            tts_folder_location="audios/Sachin",
            status="tts_saved_to_location",
            assigned_container="global-audiosocket-105",
            scheduled_for_utc=scheduled_time,
            db=db
        )

# @app.post("/call")
# def call(number: str = Form(...), extension: int = Form(...)):
#     # Define the URL and authentication
#     url = f"http://{os.getenv('ASTERISK_SERVER')}/ari/channels"
#     auth = HTTPBasicAuth('test', 'test123')

#     # Define the data payload
#     data = {
#         'endpoint': f'PJSIP/{number}@fusionPBX-Trunk-015970296',
#         'extension': str(extension),
#         'context': 'internal',
#         'priority': '1',
#         'callerId': number,
#         'channelId': f"{number}{number}{number}{number}",
#         # 'app':'abhi'
#     }

#     response = requests.post(url, auth=auth, data=data)
#     return {'Code':response.status_code, 'Response':response.text,"url": f"http://{os.getenv('ASTERISK_SERVER')}/ari/channels"}


@app.post("/call")
def test_call(number: str = Form(...), extension: int = Form(...), channelId: str = Form(None)):

    # Define the URL and authentication
    url = f"http://{os.getenv('ASTERISK_SERVER')}/ari/channels"
    auth = HTTPBasicAuth('test', 'test123')

    if not channelId:
        channelId=str(uuid.uuid4())

    # Define the data payload
    data = {
        'endpoint': f'PJSIP/{number}@fusionPBX-Trunk-015970296',
        'extension': str(extension),
        'context': 'internal',
        'priority': '1',
        'callerId': number,
        'channelId': channelId
        # 'app':'abhi'
    }

    response = requests.post(url, auth=auth, data=data)
    return {'Code':response.status_code, 'Response':response.text,"url": f"http://{os.getenv('ASTERISK_SERVER')}/ari/channels"}





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
    

uvicorn.run(app, host="0.0.0.0", port=8001)
# uvicorn.run(app,  port=8001)
