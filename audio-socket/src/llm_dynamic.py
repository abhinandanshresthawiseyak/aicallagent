from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import requests
import os

def get_embedding(text):
    url = "http://192.168.88.40:8026/embed"
    payload = {"inputs": text}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=payload, headers=headers)
    return  response.json()

def top5avg(similarity_list):
    sorted_numbers = sorted(similarity_list, reverse=True)
    top_5 = sorted_numbers[:5]
    return sum(top_5) / len(top_5)

def generate_response_embeddings_dynamic(llm_states):

        positive_responses = [v['positive'] for k, v in llm_states.items() if k != 'repeat']
        negative_responses = [v['negative'] for k, v in llm_states.items() if k != 'repeat']

        repeat_responses = llm_states['repeat']

        positive_file_path = 'Model/positive_embeddings_dynamic.npy'
        negative_file_path = 'Model/negative_embeddings_dynamic.npy'
        repeat_file_path = "Model/repeat_embeddings_dynamic.npy"
        
        if os.path.exists(repeat_file_path):
            loaded_embeds = np.load(repeat_file_path)
            repeat_embeds = loaded_embeds.tolist()
        else:
            repeat_embeds = [[get_embedding(item) for item in group] for group in repeat_responses]
            # np.save(negative_file_path, np.array(negative_embeds))
        
        if os.path.exists(positive_file_path):
            loaded_embeds = np.load(positive_file_path)
            positive_embeds = loaded_embeds.tolist()
        else:
            positive_embeds = [[get_embedding(item) for item in group] for group in positive_responses]
            # np.save(positive_file_path, np.array(positive_embeds))
            
        if os.path.exists(negative_file_path):
            loaded_embeds = np.load(negative_file_path)
            negative_embeds = loaded_embeds.tolist()
        else:
            negative_embeds = [[get_embedding(item) for item in group] for group in negative_responses]
            # np.save(negative_file_path, np.array(negative_embeds))
            
        return positive_embeds, negative_embeds, repeat_embeds

def find_similarity_dynamic(input_embedding, positive_embeddings_dynamic, negative_embeddings_dynamic, repeat_embeddings_dynamic, threshold=0.5):

    # Calculate cosine similarity between input string and responses

    positive_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in positive_embeddings_dynamic]
    negative_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in negative_embeddings_dynamic]
    repeat_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in repeat_embeddings_dynamic]
    
    top5avg_positive_similarity = top5avg(positive_similarity_scores)
    top5avg_negative_similarity = top5avg(negative_similarity_scores)
    top5avg_repeat_similarity = top5avg(repeat_similarity_scores)

    print(f"top5avg_positive_similarity:{top5avg_positive_similarity}, top5avg_negative_similarity:{top5avg_negative_similarity}, top5avg_repeat_similarity:{top5avg_repeat_similarity}")

    # Check which category has higher similarity
    if (top5avg_positive_similarity >= top5avg_negative_similarity) and (top5avg_positive_similarity >= top5avg_repeat_similarity):
        return 0
    elif (top5avg_repeat_similarity >= top5avg_positive_similarity) and (top5avg_repeat_similarity >= top5avg_negative_similarity):
        return 1
    else:
        return 2


# positive_embeds_ne, negative_embeds_ne, repeat_embeds_ne = generate_response_embeddings_ne()