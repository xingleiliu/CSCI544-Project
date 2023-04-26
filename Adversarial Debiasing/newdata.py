# -*- coding: utf-8 -*-
"""newdata.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1v39gIm3Jquc_WtoIZHJV_4MtIoYpFod2
"""

from google.colab import drive
drive.mount('/content/drive')

import pandas as pd

# Load the dataset into a pandas dataframe.
data_path = 'https://raw.githubusercontent.com/t-davidson/hate-speech-and-offensive-language/master/data/labeled_data.csv'
df = pd.read_csv(data_path)

# Report the number of sentences.
print('Number of sentences: {:,}\n'.format(df.shape[0]))

# Display 10 random rows from the data.
df.sample(10)

# preprocessing
import numpy as np
import csv
import re,string
import nltk
import spacy
import en_core_web_sm

nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')

from string import digits
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
nlp = en_core_web_sm.load()

def load_timestopword():

    f_stop = open('/content/drive/MyDrive/Racial Bias/Time.csv',encoding='utf-8')
    tsw = [line.strip() for line in f_stop]
    f_stop.close()
    return tsw

time_stop_words = load_timestopword()

def load_Estop():

    f_stop = open('/content/drive/MyDrive/Racial Bias/Estop.csv',encoding='utf-8')
    Estop = [line.strip() for line in f_stop]
    f_stop.close()
    return Estop

Estop = load_Estop()

def convert(text): # convert sentence into a list of words & clean up
    #pattern1 = r'[^a-zA-Z\s]'  # only alphabetic words and space - no number or special characters
    #temp = re.sub(pattern1,' ', lst)
    pattern2 = r'\b\w{1,2}\b'  # remove words with less than 3 characters (e.g. am, pm, at)
    # tried with {1,3} characters, but that removes words like leg, 3 characters also removes
    # words like iv
    text = re.sub(pattern2, ' ', text)
    return text

    
    return str(text)

def removeNumbers(text):
    numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    
    for num in numbers:
        text = str(text).replace(str(num), " ")
    
    return str(text)
  
# This function is essentially the same as convert, just with whitespace handling
def remove_short_terms(text):
    pattern2 = r'\b\w{1,2}\b'  # remove words with less than 3 characters (e.g. am, pm, at)
    out_text = re.sub(pattern2, ' ', text)
    out_text = str(out_text.lstrip(' '))
    out_text = str(out_text.rstrip(' '))
    return str(re.sub(r'\s\s+', r' ', str(out_text)))

def remove_pun(text):
    punctuation_string = string.punctuation
    for i in punctuation_string:
        text = text.replace(i, ' ')
    return text

def remove_proper_nouns(text):
    text_words = str(text).split()
    tagged_text = pos_tag(text_words)

    proper_nouns = [word for word,pos in tagged_text if pos == 'NNP']

    if len(proper_nouns) > 0:
        words_without_proper_nouns = [word for word in text_words if not word in proper_nouns] #remove proper nouns (names)
    
        filtered_sentence = (" ").join(words_without_proper_nouns)
        return(filtered_sentence)

    else:
        return str(text)

def remove_sw_word(text):
    text_words = str(text).split()
    words_without_sw = [word for word in text_words if not word in time_stop_words]
    words_without_sw = [word for word in words_without_sw if not word in Estop]
    filtered_sentence = (" ").join(words_without_sw)
    return(filtered_sentence)

for i in range(len(df)):
    print(i)
    text = df.loc[i, 'tweet']
    text = text.lower()
    text = remove_pun(text)
    text = removeNumbers(text)
    text = remove_proper_nouns(text)
    text = remove_sw_word(text)
    text = remove_short_terms(text)
    text = convert(text)
    doc = nlp(text)
    text_ = []
    for token in doc:
        text_.append(token.lemma_)
    final_text = (' '.join(text_)).lower()
    df.loc[i, 'sentence'] = final_text
    print(final_text)

df.to_csv('/content/drive/MyDrive/clean_data17.csv')



# remove rows with missing values
df = df.dropna()

df

## needs some refactoring...
c=df['class']
df.rename(columns={'class' : 'category'}, 
                    inplace=True)
a=df['sentence']
b=df['category'].map({0: 'hate_speech', 1: 'offensive_language',2: 'neither'})

df= pd.concat([a,b,c], axis=1)
df.rename(columns={'class' : 'label'}, 
                    inplace=True)
df

path = '/content/drive/My Drive/Racial Bias/'

# African-American, Hispanic, Asian, and White topics
aae = np.genfromtxt(path+'aae.txt', delimiter=',')
df['race'] = aae.argmax(axis=1)

df

df.groupby('label').count()

df.groupby('race').count()

# select n random samples for the specified category
train_df_0 = df.query('label == 0').sample(1000)
train_df_1 = df.query('label == 1').sample(3000)
train_df_2 = df.query('label == 2').sample(3000)

train= pd.concat([train_df_0,train_df_1,train_df_2])

train

train.to_csv('/content/drive/MyDrive/train_data.csv')

test = df[~df.isin(train)].dropna()

# print the resulting DataFrame
print(test)

import pandas as pd
# Load the FDCL18 dataset into a pandas dataframe.
data_path = '/content/drive/My Drive/Racial Bias/fdcl18.csv'
df = pd.read_csv(data_path, error_bad_lines=False)
# Report the number of sentences.
print('Number of sentences: {:,}\n'.format(df.shape[0]))

# Display 10 random rows from the data.
df.sample(10)

df

for i in range(len(df)):
  if df.loc[i, 'type'] == 'hateful':
    df.loc[i, 'label'] = 0
  elif df.loc[i, 'type'] == 'abusive':
    df.loc[i, 'label'] = 1
  elif df.loc[i, 'type'] == 'spam':
    df.loc[i, 'label'] = 2
  elif df.loc[i, 'type'] == 'normal':
    df.loc[i, 'label'] = 3

df.groupby('label').count()

# preprocessing
import numpy as np
import csv
import re,string
import nltk
import spacy
import en_core_web_sm

nltk.download('averaged_perceptron_tagger')
nltk.download('stopwords')

from string import digits
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
nlp = en_core_web_sm.load()


def load_timestopword():

    f_stop = open('/content/drive/MyDrive/Racial Bias/Time.csv',encoding='utf-8')
    tsw = [line.strip() for line in f_stop]
    f_stop.close()
    return tsw

time_stop_words = load_timestopword()

def load_Estop():

    f_stop = open('/content/drive/MyDrive/Racial Bias/Estop.csv',encoding='utf-8')
    Estop = [line.strip() for line in f_stop]
    f_stop.close()
    return Estop

Estop = load_Estop()

def convert(text): # convert sentence into a list of words & clean up
    #pattern1 = r'[^a-zA-Z\s]'  # only alphabetic words and space - no number or special characters
    #temp = re.sub(pattern1,' ', lst)
    pattern2 = r'\b\w{1,2}\b'  # remove words with less than 3 characters (e.g. am, pm, at)
    # tried with {1,3} characters, but that removes words like leg, 3 characters also removes
    # words like iv
    text = re.sub(pattern2, ' ', text)
    return text

    
    return str(text)

def removeNumbers(text):
    numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    
    for num in numbers:
        text = str(text).replace(str(num), " ")
    
    return str(text)
  
# This function is essentially the same as convert, just with whitespace handling
def remove_short_terms(text):
    pattern2 = r'\b\w{1,2}\b'  # remove words with less than 3 characters (e.g. am, pm, at)
    out_text = re.sub(pattern2, ' ', text)
    out_text = str(out_text.lstrip(' '))
    out_text = str(out_text.rstrip(' '))
    return str(re.sub(r'\s\s+', r' ', str(out_text)))

def remove_pun(text):
    punctuation_string = string.punctuation
    for i in punctuation_string:
        text = text.replace(i, ' ')
    return text

def remove_proper_nouns(text):
    text_words = str(text).split()
    tagged_text = pos_tag(text_words)

    proper_nouns = [word for word,pos in tagged_text if pos == 'NNP']

    if len(proper_nouns) > 0:
        words_without_proper_nouns = [word for word in text_words if not word in proper_nouns] #remove proper nouns (names)
    
        filtered_sentence = (" ").join(words_without_proper_nouns)
        return(filtered_sentence)

    else:
        return str(text)

def remove_sw_word(text):
    text_words = str(text).split()
    words_without_sw = [word for word in text_words if not word in time_stop_words]
    words_without_sw = [word for word in words_without_sw if not word in Estop]
    filtered_sentence = (" ").join(words_without_sw)
    return(filtered_sentence)

for i in range(len(df)):
    print(i)
    text = df.loc[i, 'tweet']
    text = text.lower()
    text = remove_pun(text)
    text = removeNumbers(text)
    text = remove_proper_nouns(text)
    text = remove_sw_word(text)
    text = remove_short_terms(text)
    text = convert(text)
    doc = nlp(text)
    text_ = []
    for token in doc:
        text_.append(token.lemma_)
    final_text = (' '.join(text_)).lower()
    df.loc[i, 'sentence'] = final_text
    print(final_text)

# remove rows with missing values
df = df.dropna()

df

df.to_csv('/content/drive/MyDrive/clean_fdcl18.csv')