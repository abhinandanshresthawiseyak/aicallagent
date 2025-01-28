import asyncio
import websockets
import json, os
from datetime import datetime

# CALL_ANSWERED = False 
# CALL_ENDED = False 

async def listen_events():
    global CALL_ANSWERED, CALL_ENDED
    url = f"ws://192.168.79.100:8088/ari/events?api_key=test:test123&app=test&&subscribeAll=yes"  # Adjust the app name as necessary

    async with websockets.connect(url) as websocket:
        print("Connected to Asterisk events WebSocket")

        while True:
            try:
                event = await websocket.recv() 
                logs=json.loads(event) 
                print(logs)

                # Write event to the log file
                if 'channel' in logs and 'id' in logs['channel']:
                    channel_id = logs['channel']['id']

                    # Ensure the directory exists, create it if it doesn't
                    os.makedirs(f'/app/websocket-logs/{str(datetime.today().date())}/', exist_ok=True)

                    with open(f'/app/websocket-logs/{str(datetime.today().date())}/{channel_id}.txt', 'a') as f:
                        f.write(event+'\n')
                        
                # with open('/home/bumblebee/wiseyak/abhi/global/global-audio-socket/logs/logs.txt','a') as f:
                #     f.write(event+'\n')
                    
                # # print(logs)
                # if 'channel' in logs and logs['channel']['name']:
                #     print(logs['channel']['name'])
                #     if 'type' in logs and logs['type']=='ChannelCreated' and logs['channel']['caller']['number'] !='':
                #         print(f"Calling from extension:{logs['channel']['caller']['number']} to {logs['channel']['dialplan']['exten']}" ,)

                #     if 'dialplan_app' in logs and logs['dialplan_app'] == 'AudioSocket':
                #         # print('Call Answered: ')
                #         CALL_ANSWERED = True

                #     if 'type' in logs and logs['type'] == 'ChannelDestroyed':
                #         CALL_ENDED=True
                #         # print('Call Ended with reason:',logs['cause_txt'])

                #         if CALL_ENDED and CALL_ANSWERED:
                #             print("Answered and Ended")
                #         elif CALL_ENDED and not CALL_ANSWERED:
                #             print("Didn't Answer")

            except websockets.ConnectionClosed:
                print("Connection closed, reconnecting...")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                break

if __name__ == "__main__":
    asyncio.run(listen_events()) 