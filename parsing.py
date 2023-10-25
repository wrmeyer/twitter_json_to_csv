import os
import numpy
import pandas as pd
import json
from tqdm import tqdm

def parse_user_data(user_lines):
    global user_headers
    global user_bank
    for user in user_lines:
        user_bank[user["id"]] = {i: user[i] for i in (user_headers + ["public_metrics", "entities"]) if i in user.keys()}
        
        user_bank[user["id"]]["account_created_at"] = user["created_at"]
        
def parse_media_data(media_lines):
    global media_bank
    for media in media_lines:
        media_bank[media["media_key"]] = {i: media[i] for i in ["type", "url", "preview_image_url", "duration_ms", "height", "non_public_metrics", "organic_metrics", "promoted_metrics", "public_metrics", "width", "alt_text", "variants"] if i in media.keys()}
        
def parse_reference_data(reference_lines):
    global reference_bank
    for reference in reference_lines:
        entry = {}
        
        for metric in ["like_count", "retweet_count", "quote_count", "reply_count"]:
            entry["referenced_tweet_" + metric] = reference["public_metrics"][metric]
            
        if "entities" in reference.keys():
            for entity_type in ["hashtags", "urls", "mentions", "symbols", "polls"]:
                if entity_type in reference["entities"].keys():
                    entry["referenced_tweet_" + entity_type] = reference["entities"][entity_type]
                else:
                    entry["referenced_tweet_" + entity_type] = ""
        
        entry["referenced_tweet_text"] = reference["text"]
        entry["referenced_tweet_conversation_id"] = reference["conversation_id"]
        entry["referenced_tweet_created_at"] = reference["created_at"]
        try:
            entry["referenced_tweet_source"] = reference["source"]
        except:
            entry["referenced_tweet_source"] = ""
        entry["referenced_tweet_reply_settings"] = reference["reply_settings"]
        entry["referenced_tweet_lang"] = reference["lang"]
        entry["referenced_tweet_author_id"] = reference["author_id"]
        
        if "attachments" in reference.keys() and "media_keys" in reference["attachments"].keys():
            entry = manage_media(reference, entry, referenced_tweet = True)
        
        
        reference_bank[reference["id"]] = entry
        
        
def write_tweet_data(out_path, tweet_lines):
    global tweet_headers
    global user_headers
    global full_headers
    global user_bank
    
    
    tweet_lines_sorted = []
    for tweet in tweet_lines:
        tweet_line = {}
        
        #looping through dense headers and parsing
        for i in ["entities", "attachments", "referenced_tweets"]:
            
            if i in tweet.keys():
            
                #handline entities
                if i == "entities":
                    tweet_line = manage_entities(tweet, tweet_line)
                
                #handline media
                elif i == "attachments" and "media_keys" in tweet["attachments"].keys():
                    tweet_line = manage_media(tweet, tweet_line)
                    
                #add type of reference
                elif i == "referenced_tweets":
                    tweet_line = manage_reference_type(tweet, tweet_line)
                    
            else:
                tweet_line[i] = ""
                
        for header in tweet_headers:
            if header in tweet.keys():
                tweet_line[header] = tweet[header]
            else:
                tweet_line[header] = ""

        #Parsing public metrics
        metrics = tweet["public_metrics"]
        for metric in metrics.keys():
            tweet_line[metric] = metrics[metric]
            
        #parsing and attaching user data
        for header in user_bank[tweet["author_id"]].keys():
            if header == "public_metrics":
                account_metrics = user_bank[tweet["author_id"]]["public_metrics"]
                for metric in account_metrics.keys():
                    tweet_line[metric] = account_metrics[metric]
            elif header == "entities":
                tweet_line = manage_profile_eneities(tweet, tweet_line)
            else:
                tweet_line[header] = user_bank[tweet["author_id"]][header]
                
        #attach referenced_tweet_information
        if "tweet_type" in tweet_line.keys() and tweet_line["tweet_type"] in ["reply", "quote", "retweet"] and tweet_line["referenced_tweet_id"] in reference_bank.keys():
            referenced_tweet_info = reference_bank[tweet_line["referenced_tweet_id"]]
            for key in referenced_tweet_info.keys():
                tweet_line[key] = referenced_tweet_info[key]
        
        
        tweet_line = sort_tweet(tweet_line, full_headers)
        
        
        
        tweet_lines_sorted.append(tweet_line)
        
    pd.DataFrame(tweet_lines_sorted).applymap(str).to_csv(out_path, mode='a', index=False, header=False)
    
    
def manage_reference_type(tweet_json, tweet_line):
    reference_info = tweet_json["referenced_tweets"][0]
    tweet_type = reference_info["type"]
    
    if tweet_type == "replied_to":
        tweet_line["tweet_type"] = "reply"
    elif tweet_type == "quoted":
        tweet_line["tweet_type"] = "quote"
    else:
        tweet_line["tweet_type"] = "retweet"

    tweet_line["referenced_tweet_id"] = reference_info["id"]
    
    return(tweet_line)
    
def manage_entities(tweet_json, tweet_line):
    global entity_types
    
    tweet_entities = tweet_json["entities"].keys()
    
    possible_entities = ["hashtags", "urls", "mentions", "symbols", "polls"]
    for entity_type in possible_entities:
        if entity_type in tweet_entities:
            tweet_line[entity_type] = tweet_json["entities"][entity_type]
        else:
            tweet_line[entity_type] = ""
    
    return(tweet_line)

def manage_profile_eneities(tweet_json, tweet_line):
    global user_bank
    user_id = tweet_json["author_id"]
    user_data = user_bank[user_id]
    
    if 'entities' in user_data.keys() and 'description' in user_data["entities"].keys():
        
        description_entities = user_data["entities"]["description"]
    else:
        description_entities = {}
    
    possible_entities = ["hashtags", "urls", "mentions"]
    for entity_type in possible_entities:
        if entity_type in description_entities.keys():
            tweet_line["description_" + entity_type] = description_entities[entity_type]
        else:
            tweet_line["description_" + entity_type] = ""
    
    return(tweet_line)
    
    
def manage_media(tweet_json, tweet_line, referenced_tweet = False): 
    m = 1
    for key in tweet_json["attachments"]["media_keys"]:
        if key in media_bank.keys():
            media_info = media_bank[key]
            tag = "media_" + str(m) + "_"
            tweet_line[tag + "media_key"] = key

            media_headers = ["type", "url", "preview_image_url", "duration_ms", "height", "non_public_metrics", "organic_metrics", "promoted_metrics", "public_metrics", "width", "alt_text", "variants"]
            for header in media_headers:

                #combine url and preview_image_url
                if header == "preview_image_url" and header in media_info.keys():
                    tweet_line[tag + "url"] = media_info[header]
                elif header == "public_metrics" and header in media_info.keys() and "view_count" in media_info[header].keys():
                    tweet_line[tag+"view_count"] = media_info[header]["view_count"]
                elif header in media_info.keys():
                    tweet_line[tag + header] = media_info[header]           

            m += 1    
        
    if referenced_tweet:
        referenced_tweet_line = {}
        for key in tweet_line.keys():
            if "referenced_tweet_" not in key:
                referenced_tweet_line["referenced_tweet_" + key] = tweet_line[key]
            else:
                referenced_tweet_line["key"] = tweet_line[key]
        
        return(referenced_tweet_line)
        
    else:
        return(tweet_line)

def fill_empty_fields(headers, target):
    empty_fields = [header for header in headers if header not in target.keys()]
    for header in empty_fields:
        if header == "tweet_type":
            target[header] = "original"
        else:
            target[header] = ""
    return(target)


def sort_tweet(tweet_line, full_headers):
    tweet_line = fill_empty_fields(full_headers, tweet_line)
    line_sorted = {}
    for header in full_headers:
        line_sorted[header] = tweet_line[header]
        
    return(line_sorted)

directory = str(os.getcwd()) #directory containing parsing script, 


#main
user_headers = ["account_created_at", 'description', 'verified', 'profile_image_url', 'name', 'description_hashtags', 'description_mentions', 'description_urls', 'followers_count', 'following_count', 'tweet_count','listed_count','location', 'protected', 'username']
tweet_headers = ["author_id", "id", "text", "edit_history_tweet_ids", "context_annotations", "conversation_id", "created_at", "edit_controls", "in_reply_to_user_id", "lang", "non_public_metrics", "organic_metrics", "possibly_sensitive", "promoted_metrics", "reply_settings", "source", "withheld"]
metrics_headers = ["like_count", "quote_count", "retweet_count", "reply_count"]
entity_types = ["hashtags", "urls", "mentions", "symbols", "polls"]
reference_headers = ["referenced_tweet_text", "referenced_tweet_hashtags", "referenced_tweet_urls", "referenced_tweet_mentions", "referenced_tweet_symbols", "referenced_tweet_polls", "referenced_tweet_like_count", "referenced_tweet_quote_count", "referenced_tweet_retweet_count", "referenced_tweet_reply_count", "referenced_tweet_conversation_id", "referenced_tweet_created_at", "referenced_tweet_source", "referenced_tweet_reply_settings", "referenced_tweet_lang", "referenced_tweet_author_id"]
media_headers = ["media_1_media_key", "media_1_type", "media_1_url", "media_1_duration_ms", "media_1_non_public_metrics", "media_1_organic_metrics", "media_1_view_count", "media_1_promoted_metrics", "media_1_height", "media_1_width", "media_1_alt_text", "media_1_variants",
                 "media_2_media_key", "media_2_type", "media_2_url", "media_2_duration_ms", "media_2_non_public_metrics", "media_2_organic_metrics", "media_2_view_count", "media_2_promoted_metrics", "media_2_height", "media_2_width", "media_2_alt_text", "media_2_variants",
                 "media_3_media_key", "media_3_type", "media_3_url", "media_3_duration_ms", "media_3_non_public_metrics", "media_3_organic_metrics", "media_3_view_count", "media_3_promoted_metrics", "media_3_height", "media_3_width", "media_3_alt_text", "media_3_variants",
                 "media_4_media_key", "media_4_type", "media_4_url", "media_4_duration_ms", "media_4_non_public_metrics", "media_4_organic_metrics", "media_4_view_count", "media_4_promoted_metrics", "media_4_height", "media_4_width", "media_4_alt_text", "media_4_variants"]
reference_media_headers = ["referenced_tweet_" + key for key in media_headers]

full_headers = (user_headers + tweet_headers + ["tweet_type"] + entity_types + metrics_headers + ["referenced_tweet_id"] + media_headers + reference_headers + reference_media_headers)

json_files = []
for path, subdirs, files in os.walk(directory + "/raw_json"):
    for name in files:
        if ".json" in name:
            json_files.append(path + "/" + name)

output_files = []
for path, subdirs, files in os.walk(directory + "/parsed_csv"):
    for name in files:
        output_files.append(path + "/" + name)
            
        
# json_files = os.listdir(directory + "/TwitterAPI_2.0")
# json_files = [file for file in json_files if ".json" in file]
x = 0
failed_files = []

for file in tqdm(json_files):
    
    #create user and media bank to read from when writing to csv
    user_bank = {}
    media_bank = {}
    reference_bank = {}
    
    json_path = (file)
    
    #path for final csv
    out_path = json_path.replace(".json", ".csv").split("/")[-1]
    out_path = (directory + "/parsed_csv/" + out_path)

    #rename and write column names to csv
    pd.DataFrame(columns = full_headers).rename(columns={"username": "twitter_handle", "id": "tweet_id", "url": "profile_url", "created_at": "tweet_created_at", "hashtags": "tweet_hashtags", "urls": "in_tweet_urls"}).to_csv(out_path, index=False)


    if out_path not in output_files:
    
        try:
            with open(json_path, "r", encoding = 'utf-8') as f:
                headers = []
                for line in f:
                    data = json.loads(str(line))
                    if "includes" in data.keys():
                        
                        if "users" in data["includes"].keys():
                            #parse user data
                            parse_user_data(data["includes"]["users"])

                        #parse media data
                        if "media" in data["includes"].keys():
                            parse_media_data(data["includes"]["media"])

                        if "tweets" in data["includes"].keys():
                            #parse reference tweet data
                            parse_reference_data(data["includes"]["tweets"])
                        
                        #rewrite tweet json objects into csv line format
                        write_tweet_data(out_path, data["data"]) 
        except:
            with open(json_path, "r", encoding = 'utf-16') as f:
                headers = []
                for line in f:
                    data = json.loads(str(line))
                    if "includes" in data.keys():
                                
                        if "users" in data["includes"].keys():
                            #parse user data
                            parse_user_data(data["includes"]["users"])

                        #parse media data
                        if "media" in data["includes"].keys():
                            parse_media_data(data["includes"]["media"])

                        if "tweets" in data["includes"].keys():
                            #parse reference tweet data
                            parse_reference_data(data["includes"]["tweets"])
                        
                        #rewrite tweet json objects into csv line format
                        write_tweet_data(out_path, data["data"])