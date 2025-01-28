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

def generate_response_embeddings():

        positive_responses_1 = ["Yes ", "Yes, Yep", "Yes, I am David ", "Yes I'm David", "Yep", "Yeah, I'm David", "Yeah I'm David Speaking","Yeah, tell me","Yes, this is David"]
        negative_responses_1 = ["No",  "Nope", "No, I'm Suraj", "Nah", "No I'm not David", "I am not David", "Not David","No, this isn't David","Sorry I'm not John Doe"]
        
        positive_responses_2 = ["Yes, I do.","yeah im okay with it","Yes","Sure", "Yes Please", "Okay"," Yeah, we can talk","Yes I have a moment","You can say","Yes tell me","it's appropriate","yep"]
        negative_responses_2 = ["I am not sure about it","No thank you","No, I dont think so. ","not the right time","I'm driving right now","im in a meeting","call me later","not today","its not the right time","not right now","not","I'm in middle of something", "Busy right now","busy","No", "No I don't have time", "nope", "not okay", "later", "nop","I don't have a moment","Don't say"]
        
        positive_responses_3 = ["Oh, I didnt know that.","I might reconsider then.","I like the offer","i want to renew"]
        negative_responses_3 = ["I'll think about it, but no promises.","call me later","No, Im still not interested.","no","im busy right now","busy","i have no money","i bought another subscription","No", "No I want","No I don\'t want more details","i'll talk later", "nope", "not okay", "later", "nop","no thank you"]
        
        positive_responses_4 = ["thank you","Sure", "Yes Please", "Okay", "Yes as soon as possible","yes thank you"]
        negative_responses_4 = ["call me later","Send me next day","not today", "No", "No I don't have time", "nope", "not okay", "later", "nop"]
        
        positive_responses = [positive_responses_1, positive_responses_2, positive_responses_3, positive_responses_4]
        negative_responses = [negative_responses_1, negative_responses_2, negative_responses_3, negative_responses_4]
    
    
        repeat_responses = [["could you speak louder","i can't hear you","repeat","repeat please","can you speak alittle louder?", "pardon?", "can you repeat?", "could you repeat?"]]

        positive_file_path = 'Model/positive_embeddings.npy'
        negative_file_path = 'Model/negative_embeddings.npy'
        repeat_file_path = "Model/repeat_embeddings.npy"
        
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


def top5avg(similarity_list):
    sorted_numbers = sorted(similarity_list, reverse=True)
    top_5 = sorted_numbers[:5]
    return sum(top_5) / len(top_5)

def find_similarity(input_embedding, positive_embeddings, negative_embeddings, repeat_embeddings, threshold=0.5):

    # Calculate cosine similarity between input string and responses

    positive_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in positive_embeddings]
    negative_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in negative_embeddings]
    repeat_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in repeat_embeddings]
    
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

positive_embeds, negative_embeds, repeat_embeds = generate_response_embeddings()


def generate_response_embeddings_ne():

        positive_responses_1 = ["हो म बिज्ञान अधिकारी बोल्दै छु ", "हजुर हो ", "हजुर बोल्दै छु ", "के कुरा को लागि हो", "हजुर भन्नुस म सुनिरहेको छु", "ओभाओ भन्नुस् न", "हजार भनोस् न के काम पर्‍यो","हजार भनोस् न"]
        negative_responses_1 = ["हैन",  "हैन नि", "म त अर्कै मान्छे हो", "मेरो नाम त रमेश हो", "रंग नम्बर पर्यो", "रङ नम्बर पर्‍यो", "होइन"]
        
        positive_responses_2 = ["मिल्छ","मिल्छ मिल्छ","हजुर भन्नुस न", "अहिले मिल्छ", "हजुर मिल छ"]
        negative_responses_2 = [ "अहिले त मिल्दैन", "मिल्दैन", "भोलि मात्रै मिल्छ", "एकै छिन पछि मात्रै मिल्छ", "अहिले मिल्दैन", "हजुर मिल दैन"]
        
        positive_responses_3 = ["हुन्छ", "हुन्छ, समय मिलाएर जान पर्ला", "धन्यवाद, म जान्छु", "म छिट्टै जान्छु"]
        negative_responses_3 = [
                                    "हुँदैन", 
                                    "अलि छिटो गर्न मिल्दैन?", 
                                    "मलाई हतार छ, अलि चाँडो मिल्छ कि?", 
                                    "म सँग अहिले डकुमेन्टहरू केही पनि छैन",
                                    "अलि समय पछि जाँदा पनि हुन्छ?"
                                ]
        
        positive_responses_4 = [
                                    "बुझे",
                                    "राम्ररी बुझे",
                                    "बुझे नि, धन्यवाद"
                                ]
        negative_responses_4 = [
                                    "बुझिन",  # This is a more colloquial or conversational form for "I didn't understand".
                                    "बुझिएन"  # This is a more formal or proper form for "It wasn't understood".
                                ]
        
        positive_responses = [positive_responses_1, positive_responses_2, positive_responses_3, positive_responses_4]
        negative_responses = [negative_responses_1, negative_responses_2, negative_responses_3, negative_responses_4]
    
    
        repeat_responses = [["could you speak louder","i can't hear you","repeat","repeat please","can you speak alittle louder?", "pardon?", "can you repeat?", "could you repeat?","मैले बुझिन", "मलाई फेरी भनि दिनुस न", "हजुरले के भन्नु भएको मैले बुझिन", "हजुर के भन्नु भाको?"]]

        positive_file_path = 'Model/positive_embeddings.npy'
        negative_file_path = 'Model/negative_embeddings.npy'
        repeat_file_path = "Model/repeat_embeddings.npy"
        
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

def find_similarity_ne(input_embedding, positive_embeddings, negative_embeddings, repeat_embeddings, threshold=0.5):

    # Calculate cosine similarity between input string and responses

    positive_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in positive_embeddings]
    negative_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in negative_embeddings]
    repeat_similarity_scores = [cosine_similarity(input_embedding, embedding)[0][0] for embedding in repeat_embeddings]
    
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

positive_embeds_ne, negative_embeds_ne, repeat_embeds_ne = generate_response_embeddings_ne()
