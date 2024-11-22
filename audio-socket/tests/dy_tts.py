import requests
import pandas as pd
import socket
import json

call_type = {
    "states": {
        "1": {
            "yes": {"next_state": 2, "audio_file": "atm2yes.wav"},
            "no": {"next_state": "out_state", "audio_file": "atm2no.wav"},
            "repeat": {"next_state": 1, "audio_file": "atm1.wav"}
        },
        "2": {
            "yes": {"next_state": 3, "audio_file": "atm3yes.wav"},
            "no": {"next_state": "out_state", "audio_file": "atm3no.wav"},
            "repeat": {"next_state": 2, "audio_file": "atm2yes.wav"}
        },
        "3": {
            "yes": {"next_state": 4, "audio_file": "atm5.wav"},
            "no": {"next_state": "out_state", "audio_file": "atm4no.wav"},
            "repeat": {"next_state": 3, "audio_file": "atm3yes.wav"}
        },
        "4": {
            "yes": {"audio_file": "atm5.wav"},
            "no": {"audio_file": "atm5.wav"},
            "repeat": {"next_state": 4, "audio_file": "atm5.wav"}
        }
    }
}

def tts_dynamic(state, call_type, llm_output):
    # Convert state to string to use as a key
    state_key = str(state)
    # Check if the state is valid
    if state_key in call_type['states']:
        # Check if the input command (llm_output) is valid for the current state
        if llm_output in call_type['states'][state_key]:
            # Get the current state's response details
            response = call_type['states'][state_key][llm_output]
            # Play the associated audio file
            print("play", response['audio_file'])
            # Print the next state, handle cases where there may not be a 'next_state' defined
            if 'next_state' in response:
                print("state", response['next_state'])
            else:
                print("end of call flow")
        else:
            print(f"Invalid command '{llm_output}' for state {state_key}")
    else:
        print(f"Invalid state {state_key}")

if __name__=='__main__':
    # tts_dynamic(4, call_type=call_type, llm_output="yes")
    response=requests.get('http://192.168.89.109:8001/users',headers={'accept': 'application/json'})

    df=pd.DataFrame(response.json())
    mydf=df[(df['assigned_container']==socket.gethostname()) & (df['status']=='pending')]
    call_type=mydf['call_type'].iloc[0]
    call_type=json.loads(call_type)

    tts_dynamic(state=1, call_type=call_type, llm_output="yes")
