import json
import time
# from pyVoIP.VoIP import CallState
import wave
import uuid
import io
import numpy as np
import torch
import math
import threading
import requests
import queue
from datetime import datetime
import scipy.io.wavfile as wav
from scipy.signal import resample
import sys
# from llm_handler import *
from llm_dynamic import *
import requests
import logging
import pytz
# import librosa
# from scipy.signal import resample_poly, butter, lfilter

logging.basicConfig(level=logging.DEBUG)

model, utils = torch.hub.load(repo_or_dir='/app/src/silero-vad',
                              source='local',
                              model='silero_vad',
                              force_reload=True,
                              onnx=False)

# Check if a GPU is available
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
logging.info(f'Using device: {device}')

model = model.to(device)

# Global constants related to the audio input format and chosen chunk values.
# SAMPLE_RATE = 8000 * 2 # Note: Sample rate of received audio bytes is 8000 and we are upsampling to 16000 for VAD because VAD couldn't detect small speech like "No", "Noooo" etc.
SAMPLE_RATE=8000
SILENCE_TIME = 2  # seconds
# CHUNK_SAMPLES = 512
CHUNK_SAMPLES = 256
CHANNELS = 1
BIT_DEPTH = 2
CHUNK_SIZE = int(CHUNK_SAMPLES * CHANNELS * BIT_DEPTH) # amt of bytes per chunk

SILENCE_SAMPLES = SAMPLE_RATE * SILENCE_TIME
SILENCE_CHUNKS = math.ceil(SILENCE_SAMPLES / (CHUNK_SAMPLES * BIT_DEPTH * CHANNELS))

def convert_8bit_to_16bit(audio_data):
    audio_data = np.frombuffer(audio_data, dtype=np.uint8).astype(np.int16)
    audio_data = (audio_data - 128) * 256  # Scale from 8-bit to 16-bit
    return audio_data.tobytes()

def split_audio_bytes(audio_bytes, sample_rate=8000, sample_width=1):
    bytes_per_second = sample_rate * sample_width
    chunks = [audio_bytes[i:i + bytes_per_second] for i in range(0, len(audio_bytes), bytes_per_second)]
    return chunks

def upsample_audio_stream(audio_bytes, sample_rate=8000, new_sample_rate=16000):
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)  # Assuming 16-bit PCM
    num_samples = int(len(audio_data) * new_sample_rate / sample_rate) # Calculate the number of samples after upsampling
    upsampled_data = resample(audio_data, num_samples) # Resample the audio data
    upsampled_bytes = upsampled_data.astype(np.int16).tobytes() # Convert the numpy array back to bytes
    return upsampled_bytes

def get_audio_bytes(input_path):
    # Load the audio file
    sample_rate, data = wav.read(input_path)
    logging.info('%s',sample_rate)
    # Check if the audio is in 16-bit PCM format
    if data.dtype != np.int16:
        raise ValueError("Input audio is not in 16-bit PCM format")

    # Resample the audio to 8000 Hz
    target_sample_rate = 8000
    num_samples = int(len(data) * target_sample_rate / sample_rate)
    resampled_data = resample(data, num_samples)
    resampled_data = resampled_data.astype(np.int16)  # Scale and convert to int16

    return resampled_data.tobytes()
    
def upsample_audio_stream(audio_bytes, sample_rate=8000, new_sample_rate=16000):
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)  # Assuming 16-bit PCM
    num_samples = int(len(audio_data) * new_sample_rate / sample_rate) # Calculate the number of samples after upsampling
    upsampled_data = resample(audio_data, num_samples) # Resample the audio data
    upsampled_bytes = upsampled_data.astype(np.int16).tobytes() # Convert the numpy array back to bytes
    return upsampled_bytes

class CallHandler:
    def __init__(self,initial_audio_in_seconds=None, caller_id=uuid.uuid4(), tts_next_states=None, call_type=None, out_state=4, name=None,llm_states=None, tts_folder_location=None) -> None:
        self.name=name
        self.caller_id=caller_id
        self.initial_audio_in_seconds=initial_audio_in_seconds
        self.chunks_to_skip = math.ceil(((self.initial_audio_in_seconds*BIT_DEPTH)*SAMPLE_RATE) / (CHUNK_SAMPLES * BIT_DEPTH * CHANNELS))  # Number of initial chunks to skip
        self.skipped_chunks = 0
        self.skipped_bytes = 0
        self.speech_threshold = 0.0
        self.voiced_chunk_count = 0
        self.silence_count = 0
        self.prob_data = []
        self.vad_dictionary = {}
        self.buffer_lock = threading.Lock()
        self.audio_buffer = io.BytesIO()  # BytesIO object that will be used to store the audio bytes that the user speaks
        self.silence_found=False
        self.last_position=0
        self.asr_queue=queue.Queue()
        self.llm_queue=queue.Queue()
        self.tts_queue=queue.Queue()
        self.audio_sender_queue=queue.Queue()
        self.state=1
        self.out_state=out_state

        self.replace_track=False # Flag to indicate that track has to be replaced inside send_audio_back co-routine
        self.audio_array=b'' # an array that holds audio that has to be streamed back to the Client
        self.out_stream_status=False # Flag to indicate that server is streaming 
        self.stream_chunks=[]

        self.played_reminder=False # Flag to indicate that reminder-audio has to be played
        self.logs={}
        self.caller=False
        self.run_threads=True
        self.call_logs_url=f"http://{os.getenv('FAST_API')}/call_logs/"
        self.nepali=False

        self.llm_states = llm_states
        self.tts_folder_location=tts_folder_location
        self.tts_next_states = tts_next_states
        self.call_type = call_type
        
    def call_hangup(self, conn):
        while self.run_threads:
            time.sleep(0.00001)
            if self.state==self.out_state:
                requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'Call Hangup - Playing','event_detail': ''}, headers={'accept': 'application/json'})   
                time.sleep(10)
                self.logs['Hangup']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'Call Hangup','event_detail': ''}, headers={'accept': 'application/json'})   
                conn.hangup()
                self.run_threads=False
                # with open('logs/'+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+'.json', 'w', encoding='utf-8') as json_file:
                #         json.dump(self.logs, json_file, ensure_ascii=False, indent=4)
                if self.caller:

                    sys.exit()


    def send_audio_back(self, conn):
        
        while self.run_threads:
            
            time.sleep(0.00001)
            if self.audio_sender_queue:
                if not self.audio_sender_queue.empty():  # Check if the queue is empty

                    # logging.info('audio_sender_queue has new item')
                    requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'audio_sender_queue has new item','event_detail': ''}, headers={'accept': 'application/json'})
                    self.audio_array = self.audio_sender_queue.get()
                    self.out_stream_status=True

                    
                    requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'replaced track','event_detail': ''}, headers={'accept': 'application/json'})   
                    self.replace_track=True

                if self.replace_track:
                    # conn.write_audio(self.audio_array)
                    self.stream_chunks=split_audio_bytes(self.audio_array,sample_width=2)

                    for i in self.stream_chunks:
                        conn.write_audio(i)
                        time.sleep(0.9)  
                        if self.out_stream_status==True and self.voiced_chunk_count>0:
                            logging.info('%s',self.voiced_chunk_count)
                            logging.info("Detected interruption --> Stream Silence")
                            self.stream_chunks.clear()
                            self.out_stream_status=False
                            requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'interrupt detected','event_detail': f'voice chunk count: {self.voiced_chunk_count}'}, headers={'accept': 'application/json'})   
                            self.logs['Detected interruption']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            break

                    self.replace_track=False

    def tts_dynamic(self):
        while self.run_threads:
            
            time.sleep(0.00001)
            if self.tts_queue and not self.tts_queue.empty():
                logging.info("tts queue has new item")
                requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
                current_state = self.tts_next_states[str(self.state)]
                llm_output = self.tts_queue.get() # Get data from the queue

                if llm_output in current_state:
                    action = current_state[llm_output]
                    audio_file = action['audio_file']
                    print(audio_file)
                    
                    next_state = action.get('next_state', self.state)  # Default to current state if not specified
                    if isinstance(next_state, str) and next_state == 'out_state':
                        self.state = self.out_state
                    else:
                        self.state = next_state
                    
                    audio_array=get_audio_bytes(f"../{self.tts_folder_location}/{audio_file}")
                    requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': f"../{self.tts_folder_location}/{audio_file}"}, headers={'accept': 'application/json'})

                    logging.info('text converted to audio %s',self.state)
                    requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'TTS pushed audio to audio_sender_queue','event_detail': ''}, headers={'accept': 'application/json'})   

                    self.audio_sender_queue.put(audio_array)
                    logging.info('pushed audio array to audio_sender_queue')

    def llm_dynamic(self):
        while self.run_threads:
            
            time.sleep(0.00001)
            if self.llm_queue and not self.llm_queue.empty():
                requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'llm_queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
                text = self.llm_queue.get() # Get data from the queue

                try:
                    text_embedding =  get_embedding(text)
                    # logging.info(text_embedding)
                except:
                    logging.info('£'*100)
                    logging.info("Could not get text embedding")
                    requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'couldn\'t get text embedding','event_detail': ''}, headers={'accept': 'application/json'})   

                positive_embeds, negative_embeds, repeat_embeds=generate_response_embeddings_dynamic(self.llm_states)

                if self.state in [i for i in range(1,self.out_state)]:
                    similarity = find_similarity_dynamic(text_embedding, positive_embeds[self.state-1], negative_embeds[self.state-1],repeat_embeds[0])
                    if similarity == 0:
                        response = 'yes'
                    elif similarity == 1:
                        response = 'repeat'
                    else :
                        response = 'no'
                else:
                    out_state = 4
                    response = 'no'

                logging.info('%s %s',response,self.state)
                self.logs['LLMOutput: '+ response]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'LLMOutput','event_detail': response}, headers={'accept': 'application/json'})   
                    
                self.tts_queue.put(response)

    def asr(self):
            
            if self.nepali:
                # asr_base_url='http://192.168.88.10:8029/transcribe_sip_ne'
                # asr_base_url='http://192.168.88.10:8029/transcribe_sip_ne'
                asr_base_url='http://192.168.88.30:8048/transcribe_sip_ne'
            else:
                # asr_base_url='http://192.168.88.10:8028/transcribe_sip_en'
                asr_base_url='http://192.168.88.30:8048/transcribe_sip_en'
                

            # asr_base_url='http://192.168.88.10:8028/transcribe_sip_en16000/'

            while self.run_threads:
                
                time.sleep(0.00001)
                # logging.info(self.vad_dictionary)
                if self.asr_queue:
                    if not self.asr_queue.empty():  # Check if the queue is empty
                        logging.info('audiobytes added to asr queue')
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'asr_queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    

                        audio_bytes = self.asr_queue.get() # Get data from the queue
                        
                        # Prepare for POST request
                        files = {
                            "audio_file": ("audio.wav", audio_bytes, "audio/wav")
                        }

                        response = requests.post(asr_base_url, files=files)

                        asr_output_text=response.json()
                        logging.info('%s',asr_output_text)
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'ASROutput','event_detail': asr_output_text}, headers={'accept': 'application/json'})   
                    
                        self.logs['ASROutput: '+asr_output_text]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        self.llm_queue.put(asr_output_text)

    def read_vad_dictionary(self):
            # logging.info('Reading VAD Dictionary')
            # global silence_found, vad_dictionary, voiced_chunk_count, asr_queue
            c=0 # counter for saving audio chunks as file temporarily

            while self.run_threads:
                time.sleep(0.00001)
                # logging.info(self.voiced_chunk_count)
                # logging.info('Reading VAD Dictionary in iteration')
                # logging.info('in read_vad_dictionary',.vad_dictionary)
                # check if there's number of chunks in vad_dictionary with all consecutive silence chunks then pop the chunks samples
                if not self.silence_found:
                    if self.vad_dictionary and all(i==0 for i in list(self.vad_dictionary.values())[- SILENCE_CHUNKS:]):
                        
                        popped_chunks=list(self.vad_dictionary.keys())[:]

                        # # Filter out silence chunks before joining chunks to get only chunks that has audio
                        # popped_chunks = [k for k, v in self.vad_dictionary.items() if v != 0]
                        
                        logging.info('popped chunks %s',len(popped_chunks))
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'popped chunks','event_detail':f'popped chunks {len(popped_chunks)}' }, headers={'accept': 'application/json'})   
                    
                        audio_bytes=b''.join(popped_chunks)
                        
                        # self.vad_dictionary = {k: v for k, v in self.vad_dictionary.items() if k not in set(popped_chunks)}
                        # self.vad_dictionary = {}
                        for i in popped_chunks:
                            del self.vad_dictionary[i]
                        
                        # Save the audio bytes as a .wav file to test if VAD is working correctly
                        save_time = datetime.now(pytz.timezone('Asia/Kathmandu')).strftime('%Y-%m-%d %H:%M:%S')
                        with wave.open('/app/vad_output/'+save_time+'___'+str(self.caller_id)+'__'+str(c)+'.wav', 'wb') as wf:
                            wf.setnchannels(1)  # Assuming mono audio
                            wf.setsampwidth(2)  # Assuming 16-bit audio
                            # wf.setframerate(16000)  # Assuming a sample rate of 8kHz * 2 because of upsampling
                            wf.setframerate(8000)  # Assuming a sample rate of 8kHz * 2 because of upsampling
                            wf.writeframes(audio_bytes)
                            # wf.writeframes(processed_audio)
                        
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'VAD Saves file','event_detail':'vad_output/'+save_time+'___'+str(self.caller_id)+'__'+str(c)+'.wav' }, headers={'accept': 'application/json'})   
                    
                        self.voiced_chunk_count=0

                        c+=1
                        self.silence_found=True
                        logging.info("Silence Found")
                        self.logs['Silence Found:']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'Silence Found','event_detail': ''}, headers={'accept': 'application/json'})   
                        self.asr_queue.put(audio_bytes)
                        # self.asr_queue.put(processed_audio)
                else:
                    # logging.info(self.voiced_chunk_count)
                    # if self.vad_dictionary and list(self.vad_dictionary.values())[-1]==1:
                    # if self.vad_dictionary and 1 in list(self.vad_dictionary.values())[:]:
                    if self.vad_dictionary and self.voiced_chunk_count>0:
                        logging.info("Detected Voice with voiced_chunk_count %s",self.voiced_chunk_count)
                        logging.info('%s',self.voiced_chunk_count)
                        self.logs['Detected Voice:']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'detected voice','event_detail': ''}, headers={'accept': 'application/json'})   
                    
                        self.silence_found=False


    def VAD(self, chunk, threshold_weight=0.85):
        # global voiced_chunk_count, silence_count, speech_threshold, prob_data, vad_dictionary
        # logging.info('Vad Function Started')
        np_chunk = np.frombuffer(chunk, dtype=np.int16)
        np_chunk = np_chunk.astype(np.float32) / 32768.0
        chunk_audio = torch.from_numpy(np_chunk).to(device)

        self.speech_prob = model(chunk_audio, SAMPLE_RATE).item()
        self.prob_data.append(self.speech_prob)

        if self.speech_prob >= self.speech_threshold:
            self.voiced_chunk_count += 1
            self.silence_count = 0
            self.vad_dictionary[chunk] = 1
        else:
            self.vad_dictionary[chunk] = 0
            self.silence_count += 1

        # logging.info(vad_dictionary)
        if self.prob_data:
            self.speech_threshold = threshold_weight * max([i**2 for i in self.prob_data]) + (1 - threshold_weight) * min([i**2 for i in self.prob_data])

    def read_buffer_chunks(self):
        
        # global voiced_chunk_count, silence_count, vad_dictionary, prob_data, audio_buffer, last_position
        while self.run_threads:
                
                time.sleep(0.00001)
                self.audio_buffer.seek(0, io.SEEK_END)  # seek to end of audio
                size = self.audio_buffer.tell()  # size of audio

                if size >= self.last_position + CHUNK_SIZE:
                # if size >= CHUNK_SIZE:
                    self.audio_buffer.seek(self.last_position)  # Seek to the last read position

                    if self.skipped_chunks < self.chunks_to_skip:
                        # Skip the specified number of chunks
                        self.skipped_bytes = min(self.chunks_to_skip * CHUNK_SIZE, size - self.last_position)
                        self.audio_buffer.seek(self.last_position + self.skipped_bytes)
                        self.last_position += self.skipped_bytes
                        self.skipped_chunks += self.skipped_bytes // CHUNK_SIZE
                        continue  # proceed remaining loop

                    # audio_buffer.seek(0)  # Seek to the last read position
                    chunk = self.audio_buffer.read(CHUNK_SIZE)  # Read the next chunk of data
                    # logging.info(chunk)
                    # Implement VAD in this chunk
                    self.VAD(chunk)

                    self.last_position += CHUNK_SIZE

                    # audio_buffer.seek(0)
                    # audio_buffer.truncate()
                    # Truncate the buffer to remove processed data
                    # remaining_data = audio_buffer.read()  # Read the rest of the buffer
                    # audio_buffer.seek(0)  # Move to the start
                    # audio_buffer.truncate()  # Clear the buffer
                    # audio_buffer.write(remaining_data)  # Write back the remaining data

    # def tts_ne(self):

    #     while self.run_threads:
            
    #         time.sleep(0.00001)
    #         if self.tts_queue and not self.tts_queue.empty():
    #             logging.info("tts queue has new item")
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
    #             llm_output = self.tts_queue.get() # Get data from the queue
                
    #             if self.state==1:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/atm2yes.wav')
    #                     self.logs['TTS Plays: 2_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_yes.wav'}, headers={'accept': 'application/json'})   
    #                     self.state+=1
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/atm2no.wav')
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_no.wav'}, headers={'accept': 'application/json'})
    #                     self.logs['TTS Plays: 2_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     self.state=self.out_state
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/atm1.wav')
    #                     self.logs['TTS Plays: 1.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp1.wav'}, headers={'accept': 'application/json'})
    #                     self.state=1
    #             elif self.state==2:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/atm3yes.wav')
    #                     self.logs['TTS Plays: 3_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state+=1
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/atm3no.wav')
    #                     self.logs['TTS Plays: 3_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_no.wav'}, headers={'accept': 'application/json'})
    #                     self.state=self.out_state
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/atm2yes.wav')
    #                     self.logs['TTS Plays: 2_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state=2
    #             elif self.state==3:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/atm5.wav')
    #                     self.logs['TTS Plays: 4_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp4_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state+=1
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/atm4no.wav')
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp4_no.wav'}, headers={'accept': 'application/json'})
    #                     self.logs['TTS Plays: 4_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     self.state=self.out_state
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/atm3yes.wav')
    #                     self.logs['TTS Plays: 3_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state=3
    #             elif self.state==4:
    #                 # if llm_output=='yes':
    #                 audio_array=get_audio_bytes('../audios/atm5.wav')
    #                 self.logs['TTS Plays: 5_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                 requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp5.wav'}, headers={'accept': 'application/json'})
    #             logging.info('text converted to audio %s',self.state)
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'TTS pushed audio to audio_sender_queue','event_detail': ''}, headers={'accept': 'application/json'})   
    #             # logging.info()

    #             self.logs['TTSOutput'+str(uuid.uuid4())+'.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    #             self.audio_sender_queue.put(audio_array)
    #             logging.info('pushed audio array to audio_sender_queue')

    # def llm_ne(self):

    #     while self.run_threads:
            
    #         time.sleep(0.00001)
    #         if self.llm_queue and not self.llm_queue.empty():
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'llm_queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
    #             text = self.llm_queue.get() # Get data from the queue

    #             try:
    #                 text_embedding =  get_embedding(text)
    #                 # logging.info(text_embedding)
    #             except:
    #                 logging.info('£'*100)
    #                 logging.info("Could not get text embedding")
    #                 requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'couldn\'t get text embedding','event_detail': ''}, headers={'accept': 'application/json'})   

    #             # out_state = self.state+1 # Out state increase by 1

    #             # logging.info("&"*100)
    #             # logging.info(np.array(text_embedding).shape)
    #             # logging.info(np.array(positive_embeds[0]).shape)
    #             # logging.info("&"*100)

    #             if self.state == 1:
    #                 similarity = find_similarity_ne(text_embedding, positive_embeds_ne[self.state-1], negative_embeds_ne[self.state-1],repeat_embeds_ne[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
                
    #             elif self.state == 2:
    #                 similarity =   find_similarity_ne(text_embedding, positive_embeds_ne[self.state-1], negative_embeds_ne[self.state-1], repeat_embeds_ne[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
                        
    #             elif self.state==3:
    #                 similarity =   find_similarity_ne(text_embedding, positive_embeds_ne[self.state-1], negative_embeds_ne[self.state-1],repeat_embeds_ne[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'

    #             elif self.state==4:
    #                 similarity =   find_similarity_ne(text_embedding, positive_embeds_ne[self.state-1], negative_embeds_ne[self.state-1],repeat_embeds_ne[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
    #             else:
    #                 out_state = 4
    #                 response = 'no'

    #             logging.info('%s %s',response,self.state)
    #             self.logs['LLMOutput: '+ response]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'LLMOutput','event_detail': response}, headers={'accept': 'application/json'})   
                    
    #             self.tts_queue.put(response)


    # def tts(self):

    #     while self.run_threads:
            
    #         time.sleep(0.00001)
    #         if self.tts_queue and not self.tts_queue.empty():
    #             logging.info("tts queue has new item")
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
    #             llm_output = self.tts_queue.get() # Get data from the queue
                
    #             if self.state==1:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/isp2_yes (2).wav')
    #                     self.logs['TTS Plays: isp2_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_yes.wav'}, headers={'accept': 'application/json'})   
    #                     self.state+=1
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/isp2_no (2).wav')
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_no.wav'}, headers={'accept': 'application/json'})
    #                     self.logs['TTS Plays: isp2_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     self.state=self.out_state
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/isp1 (2).wav')
    #                     self.logs['TTS Plays: isp1.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp1.wav'}, headers={'accept': 'application/json'})
    #                     self.state=1
    #             elif self.state==2:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/isp3_yes (2).wav')
    #                     self.logs['TTS Plays: isp3_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state=self.out_state
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/isp3_no (2).wav')
    #                     self.logs['TTS Plays: isp3_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_no.wav'}, headers={'accept': 'application/json'})
    #                     self.state+=1
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/isp2_yes (2).wav')
    #                     self.logs['TTS Plays: isp2_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp2_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state=2
    #             elif self.state==3:
    #                 if llm_output=='yes':
    #                     audio_array=get_audio_bytes('../audios/isp4_yes (2).wav')
    #                     self.logs['TTS Plays: isp4_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp4_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state+=1
    #                 elif llm_output=='no':
    #                     audio_array=get_audio_bytes('../audios/isp4_no (2).wav')
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp4_no.wav'}, headers={'accept': 'application/json'})
    #                     self.logs['TTS Plays: isp4_no.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     self.state=self.out_state
    #                 elif llm_output=='repeat':
    #                     audio_array=get_audio_bytes('../audios/isp3_no (2).wav')
    #                     self.logs['TTS Plays: isp3_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                     requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp3_yes.wav'}, headers={'accept': 'application/json'})
    #                     self.state=3
    #             elif self.state==4:
    #                 # if llm_output=='yes':
    #                 audio_array=get_audio_bytes('../audios/isp5 (2).wav')
    #                 self.logs['TTS Plays: isp5_yes.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #                 requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'tts pushes','event_detail': 'isp5.wav'}, headers={'accept': 'application/json'})
    #             logging.info('text converted to audio %s',self.state)
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'TTS pushed audio to audio_sender_queue','event_detail': ''}, headers={'accept': 'application/json'})   
    #             # logging.info()

    #             self.logs['TTSOutput'+str(uuid.uuid4())+'.wav']=datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    #             self.audio_sender_queue.put(audio_array)
    #             logging.info('pushed audio array to audio_sender_queue')


    # def llm(self):

    #     while self.run_threads:
            
    #         time.sleep(0.00001)
    #         if self.llm_queue and not self.llm_queue.empty():
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'llm_queue has new item','event_detail': ''}, headers={'accept': 'application/json'})   
                    
    #             text = self.llm_queue.get() # Get data from the queue

    #             try:
    #                 text_embedding =  get_embedding(text)
    #                 # logging.info(text_embedding)
    #             except:
    #                 logging.info('£'*100)
    #                 logging.info("Could not get text embedding")
    #                 requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'couldn\'t get text embedding','event_detail': ''}, headers={'accept': 'application/json'})   

    #             # out_state = self.state+1 # Out state increase by 1

    #             # logging.info("&"*100)
    #             # logging.info(np.array(text_embedding).shape)
    #             # logging.info(np.array(positive_embeds[0]).shape)
    #             # logging.info("&"*100)

    #             if self.state == 1:
    #                 similarity = find_similarity(text_embedding, positive_embeds[self.state-1], negative_embeds[self.state-1],repeat_embeds[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
                
    #             elif self.state == 2:
    #                 similarity =   find_similarity(text_embedding, positive_embeds[self.state-1], negative_embeds[self.state-1], repeat_embeds[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
                        
    #             elif self.state==3:
    #                 similarity =   find_similarity(text_embedding, positive_embeds[self.state-1], negative_embeds[self.state-1],repeat_embeds[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'

    #             elif self.state==4:
    #                 similarity =   find_similarity(text_embedding, positive_embeds[self.state-1], negative_embeds[self.state-1],repeat_embeds[0])
    #                 if similarity == 0:
    #                     response = 'yes'
    #                 elif similarity == 1:
    #                     response = 'repeat'
    #                 else :
    #                     response = 'no'
    #             else:
    #                 out_state = 4
    #                 response = 'no'

    #             logging.info('%s %s',response,self.state)
    #             self.logs['LLMOutput: '+ response]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #             requests.post(self.call_logs_url, params={'caller_id': self.caller_id,'event_type': 'LLMOutput','event_detail': response}, headers={'accept': 'application/json'})   
                    
    #             self.tts_queue.put(response)

    # # # Function to save audio_chunks to a file
    # def save_audio_to_file(audio_chunks, output_file):
    #     with wave.open(output_file, 'wb') as wf:
    #         # Parameters for WAV file
    #         num_channels = 1
    #         sample_width = 2
    #         frame_rate = 8000
    #         num_frames = sum(len(chunk) for chunk in audio_chunks) // sample_width
            
    #         wf.setnchannels(num_channels)
    #         wf.setsampwidth(sample_width)
    #         wf.setframerate(frame_rate)
    #         wf.setnframes(num_frames)
            
    #         # Write audio data to the file
    #         for chunk in audio_chunks:
    #             wf.writeframes(chunk)
