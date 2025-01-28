import wave
from threading import Thread
from call_handler import *
import time
import threading
import requests
import socket
import json
import sys
sys.path.append('./')
from audiosocket.audiosocket import Audiosocket

audiosocket = Audiosocket(("0.0.0.0", 5001))

def handle_connection(conn):
    
    ########### Get the duration of the audio file ###########
    with wave.open(f"/app/audios/Worldlink/internet_issue_en/internet_issue_en1yes.wav", 'r') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)
    
    call_type="receiver"
    
    ########### access keys from json file ###########
    with open('/app/receivertype_template/receiver_internet_en.json', 'r') as file:
        data = json.load(file)
        
    tts_next_states=data['tts_next_states'] 
    llm_states=data['llm_states']
    out_state=data['out_state']
    ########### Initialize all variables ###########
    tts_folder_location='audios/Worldlink/internet_issue_en'
    callHandler=CallHandler(initial_audio_in_seconds=duration,tts_next_states=tts_next_states, call_type=call_type, out_state=out_state, name="receiver",llm_states=llm_states,tts_folder_location=tts_folder_location)
    callHandler.caller=False # It's a receiver
    callHandler.nepali=False                                                                                                                                                                     # It's a receiver
    start_thread=False
    
    while conn.connected:
        # print('connected')
        audio_bytes = conn.read()
        # conn.write(audio_bytes)

        callHandler.audio_buffer.write(audio_bytes)
        
        # callHandler.audio_buffer.write(upsample_audio_stream(audio_bytes))
        if start_thread!=True:
            requests.post(callHandler.call_logs_url, params={'caller_id': callHandler.caller_id,'event_type': 'Receiver - Call Started','event_detail': f'{call_type}'}, headers={'accept': 'application/json'})
            time.sleep(1)
            logging.info("****",f"../{callHandler.tts_folder_location}/{tts_next_states['1']['repeat']['audio_file']}")
            conn.write_audio(get_audio_bytes(f"../{callHandler.tts_folder_location}/{tts_next_states['1']['repeat']['audio_file']}"))
            requests.post(callHandler.call_logs_url, params={'caller_id': callHandler.caller_id,'event_type': 'tts pushes','event_detail': f"../{callHandler.tts_folder_location}/{tts_next_states['1']['repeat']['audio_file']}"}, headers={'accept': 'application/json'})
            threading.Thread(target=callHandler.read_buffer_chunks, daemon=True).start()
            threading.Thread(target=callHandler.read_vad_dictionary, daemon=True).start()
            threading.Thread(target=callHandler.asr, daemon=True).start()
            threading.Thread(target=callHandler.llm_dynamic, daemon=True).start()
            threading.Thread(target=callHandler.tts_dynamic, daemon=True).start()
            threading.Thread(target=callHandler.send_audio_back, daemon=True, args=(conn,)).start()
            threading.Thread(target=callHandler.call_hangup, daemon=True, args=(conn,)).start()
            start_thread=True
            
    logging.info(conn, "Exited from while loop")
    conn.hangup()

while True:
    conn = audiosocket.listen()
    # handle_connection(conn)
    connection_thread = Thread(target=handle_connection, args=(conn,))
    connection_thread.start()
