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
    logging.info("Peer Address: ",conn.peer_addr)
    
    # Define the endpoint and parameters
    url = "http://192.168.89.109/assigned_container_user"
    params = {"assigned_container": socket.gethostname()}

    # Make the GET request
    response = requests.get(url, params=params, headers={"accept": "application/json"})
    row=response.json()
    # logging.log(row)
    call_template=json.loads(row['call_type'])
    # logging.log(call_template)
    name=row['name']
    caller_id=row['caller_id']
    call_type=call_template['type']
    out_state=call_template['out_state']
    llm_states=call_template['llm_states']
    tts_next_states=call_template['tts_next_states']
    tts_folder_location=row['tts_folder_location']

    with wave.open(f"../{tts_folder_location}/{tts_next_states['1']['repeat']['audio_file']}", 'r') as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)

    callHandler=CallHandler(initial_audio_in_seconds=duration,caller_id=caller_id, tts_next_states=tts_next_states, call_type=call_type, out_state=out_state, name=name,llm_states=llm_states,tts_folder_location=tts_folder_location)
    callHandler.caller=True
    callHandler.nepali=True
    start_thread=False

    while conn.connected:
        
        # print('connected')
        audio_bytes = conn.read()
        callHandler.audio_buffer.write(audio_bytes)
        
        # callHandler.audio_buffer.write(upsample_audio_stream(audio_bytes))
        if start_thread!=True:
            requests.post(callHandler.call_logs_url, params={'caller_id': callHandler.caller_id,'event_type': 'Call Started','event_detail': ''}, headers={'accept': 'application/json'})
            time.sleep(1)
            conn.write_audio(get_audio_bytes(f"../{tts_folder_location}/{tts_next_states['1']['repeat']['audio_file']}"))
            threading.Thread(target=callHandler.read_buffer_chunks, daemon=True).start()
            threading.Thread(target=callHandler.read_vad_dictionary, daemon=True).start()
            threading.Thread(target=callHandler.asr, daemon=True).start()
            threading.Thread(target=callHandler.llm_dynamic, daemon=True).start()
            threading.Thread(target=callHandler.tts_dynamic, daemon=True).start()
            threading.Thread(target=callHandler.send_audio_back, daemon=True, args=(conn,)).start()
            threading.Thread(target=callHandler.call_hangup, daemon=True, args=(conn,)).start()
            start_thread=True
    
    logging.info(conn, "Exited from while loop")
    callHandler.run_threads=False
    logging.info(callHandler.run_threads, "Stopping all threads by setting run_threads=")
    conn.hangup()

while True:
    conn = audiosocket.listen()
    # handle_connection(conn)
    connection_thread = Thread(target=handle_connection, args=(conn,))
    connection_thread.start()
