# -*- coding: utf-8 -*-
"""New_Debiased_Classifier.ipynb

Automatically generated by Colaboratory.

"""

#Relevant Links
#1. https://towardsdatascience.com/bert-classifier-just-another-pytorch-model-881b3cf05784\
#reference code: https://github.com/choprashweta/Adversarial-Debiasing/

from google.colab import drive
drive.mount('/content/drive')

! pip install constant
!pip install bert-pytorch
!pip install pytorch-pretrained-bert pytorch-nlp
!pip install -U -q PyDrive

from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, recall_score, precision_score
from sklearn.metrics import confusion_matrix
from nltk.metrics import ConfusionMatrix
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_class_weight
from keras.layers import Input, Dense, Dropout
from keras.models import Model
import pandas as pd
import numpy as np
import os, sys
from google.colab import drive

sys.path.append(os.path.join(os.path.dirname(sys.path[0]), 'analysis'))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(sys.path[0])), 'configs' ))

import constant

import torch
import torchvision
import torchvision.transforms as transforms
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data
import numpy as np
import pandas as pd
from tqdm import tqdm
import os
import warnings
from pytorch_pretrained_bert import BertTokenizer, BertForSequenceClassification, BertAdam, BertModel
from pytorch_pretrained_bert import BertConfig
import nltk
from nltk.tokenize import sent_tokenize
nltk.download('punkt')

# specify GPU device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
n_gpu = torch.cuda.device_count()
torch.cuda.get_device_name(0)

#Data Reading
# Mount drive for data reading
# This will prompt for authorization.
#drive.mount('/content/drive')
path = "/content/drive/MyDrive/Racial Bias/"
torch.cuda.empty_cache()

!nvidia-smi

#Read full data path = "/content/drive/Shared drives/CIS 519 Project/Code/Dataset/"
df_train_total = pd.read_csv(path + 'train_data.csv')
df_val_total = pd.read_csv(path + 'test_data.csv')

df_train_total.head(10)

df_val_total.head(10)

# comments = pd.DataFrame(df.comment_text)
# #comments.to_csv(path + "only_comments.csv")
# comments_text = df.comment_text
# df_store = df.copy()
# comments_store = comments.copy()

df_train = df_train_total#.sample(5000)
df_val = df_val_total#.sample(5000)

df_train.groupby('race').count()

comments_train = df_train.sentence
comments_val = df_val.sentence

#Generate protected attribute - racial
def extract_aae_race(x):
  if x.race == 0:
      return 0
  else:
    return 1

#Generate unprotected attribute labels
def get_unprotected_class(list_of_protected):
  new = [1 if i == 0 else 0 for i in list_of_protected]
  return new

#Calculate metrics
def get_metrics(labels, preds):
  pred_flat = preds.flatten()
  labels_flat = labels.flatten()

  acc = accuracy_score(labels_flat, pred_flat)
  pre = precision_score(labels_flat, pred_flat, average="weighted", zero_division=1)
  rec = recall_score(labels_flat, pred_flat, average="weighted", zero_division=1)
  f1 = f1_score(labels_flat, pred_flat, average="weighted")

  return acc, pre, rec, f1

#Generate labels
original_labels_train = list(df_train.label)
identity_labels_train = list(df_train.apply(extract_aae_race, axis = 1))
original_labels_val = list(df_val.label)
identity_labels_val = list(df_val.apply(extract_aae_race, axis = 1))
unprotected_labels_train = get_unprotected_class(identity_labels_train)
unprotected_labels_val = get_unprotected_class(identity_labels_val)

print(len(comments_train), len(original_labels_train))
print(comments_train[:10])
print(original_labels_train[:10])
print(identity_labels_train[:10])

MAX_SEQUENCE_LENGTH = 128
SEED = 519
BATCH_SIZE = 32
BERT_MODEL_PATH = 'bert-base-uncased'
tokenizer = BertTokenizer.from_pretrained(BERT_MODEL_PATH, cache_dir=None,do_lower_case=True)

def convert_lines(example, max_seq_length,tokenizer):
    #max_seq_length -=2
    all_tokens = []
    longer = 0
    for text in tqdm(example):
        tokens_a = tokenizer.tokenize(text)
        if len(tokens_a)>max_seq_length:
            tokens_a = tokens_a[:max_seq_length]
            longer += 1
        one_token = tokenizer.convert_tokens_to_ids(["[CLS]"]+tokens_a+["[SEP]"])+[0] * (max_seq_length - len(tokens_a))
        all_tokens.append(one_token)
    print("Tokens longer than max_length: ", longer)
    return np.array(all_tokens)

#Prepare data
input_train = convert_lines(comments_train.fillna("DUMMY_VALUE"), MAX_SEQUENCE_LENGTH, tokenizer)
original_labels_train = torch.tensor(original_labels_train)
aae_labels_train = torch.tensor(identity_labels_train)

input_val = convert_lines(comments_val.fillna("DUMMY_VALUE"), MAX_SEQUENCE_LENGTH, tokenizer)
original_labels_val = torch.tensor(original_labels_val)
aae_labels_val = torch.tensor(identity_labels_val)

print(torch.sum(original_labels_train).data)
print(torch.sum(aae_labels_train).data)

print(torch.sum(original_labels_val).data)
print(torch.sum(aae_labels_val).data)

#Data Loader
X_train = torch.utils.data.TensorDataset(torch.tensor(input_train, dtype=torch.long), original_labels_train, aae_labels_train)
train_loader = torch.utils.data.DataLoader(X_train, batch_size=32, shuffle=True)
#tk0 = tqdm(train_loader)

X_val = torch.utils.data.TensorDataset(torch.tensor(input_val, dtype=torch.long), original_labels_val, aae_labels_val)
val_loader = torch.utils.data.DataLoader(X_val, batch_size=32, shuffle=True)
#vk0 = tqdm(val_loader)

#FAIRNESS METRICS FUNCTION

def get_fairness_metrics(actual_labels, y_pred, protected_labels, non_protected_labels, thres):

  def get_toxicity_rates(y_pred, protected_labels, non_protected_labels, thres):
    protected_ops = y_pred[protected_labels == 1]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[non_protected_labels == 1]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return np.round(protected_prob, 2), np.round(non_protected_prob, 2)

  def get_true_positive_rates(actual_labels, y_pred, protected_labels, non_protected_labels, thres):

    protected_ops = y_pred[np.bitwise_and(protected_labels == 1, actual_labels == 1)]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[np.bitwise_and(non_protected_labels == 1, actual_labels == 1)]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return np.round(protected_prob, 2), np.round(non_protected_prob, 2)


  def get_false_positive_rates(actual_labels, y_pred, protected_labels, non_protected_labels, thres):

    protected_ops = y_pred[np.bitwise_and(protected_labels == 1, actual_labels ==0)]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[np.bitwise_and(non_protected_labels == 1, actual_labels == 0)]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return np.round(protected_prob, 2), np.round(non_protected_prob, 2)

  def demographic_parity(y_pred, protected_labels, non_protected_labels, thres):

    protected_ops = y_pred[protected_labels == 1]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[non_protected_labels == 1]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return abs(protected_prob - non_protected_prob) #later take absolute diff - but we want to show females predicted more toxic than male

  # | P_female(C = 1| Y = 1) - P_male(C = 1 | Y = 1) | < thres
  def true_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres):

    protected_ops = y_pred[np.bitwise_and(protected_labels == 1, actual_labels == 1)]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[np.bitwise_and(non_protected_labels == 1, actual_labels == 1)]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return abs(protected_prob - non_protected_prob) #later take absolute diff - but we want to show females predicted more toxic than male

  # | P_female(C = 1| Y = 0) - P_male(C = 1 | Y = 0) | < thres
  def false_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres):

    protected_ops = y_pred[np.bitwise_and(protected_labels == 1, actual_labels ==0)]
    protected_prob = sum(protected_ops)/len(protected_ops)

    non_protected_ops = y_pred[np.bitwise_and(non_protected_labels == 1, actual_labels == 0)]
    non_protected_prob = sum(non_protected_ops)/len(non_protected_ops)

    return abs(protected_prob - non_protected_prob) #later take absolute diff - but we want to show females predicted more toxic than male


  # Satisfy both true positive parity and false positive parity
  def equalized_odds(actual_labels, y_pred, protected_labels, non_protected_labels, thres):
    return true_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres) + false_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres)

  female_tox_rate, nf_tox_rate = get_toxicity_rates(y_pred, protected_labels, non_protected_labels, thres)
  female_tp_rate, nf_tp_rate = get_true_positive_rates(actual_labels, y_pred, protected_labels, non_protected_labels, thres)
  female_fp_rate, nf_fp_rate = get_false_positive_rates(actual_labels, y_pred, protected_labels, non_protected_labels, thres)
  demo_parity = demographic_parity(y_pred, protected_labels, non_protected_labels, thres)
  tp_parity = true_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres)
  fp_parity = false_positive_parity(actual_labels, y_pred, protected_labels, non_protected_labels, thres)
  equ_odds = equalized_odds(actual_labels, y_pred, protected_labels, non_protected_labels, thres)

  return female_tox_rate, nf_tox_rate, female_tp_rate, nf_tp_rate, female_fp_rate, nf_fp_rate, demo_parity, tp_parity, fp_parity, equ_odds

"""
FairClassifier - BERT + equipped with adversarial network - PyTorch Implementation
"""
config = BertConfig(vocab_size_or_config_json_file=32000, hidden_size=768,
        num_hidden_layers=12, num_attention_heads=12, intermediate_size=3072, 
        hidden_dropout_prob=0.1)

class Classifier(nn.Module):
    def __init__(self, toxicity_labels = 3):
        super(Classifier, self).__init__()
        
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        self.c1 = nn.Linear(config.hidden_size, 324)
        #self.c2 = nn.Linear(config.intermediate_size, 324)
        self.c3 = nn.Linear(324, toxicity_labels)

        nn.init.xavier_normal_(self.c1.weight)

    def forward(self, input_ids, token_type_ids=None, attention_mask=None, labels=None):

        
        #BERT
        _, pooled_output = self.bert(input_ids, token_type_ids, attention_mask, output_all_encoded_layers=False)
        pooled_output = self.dropout(pooled_output)

        # Classifier
        classifier_prev_output = F.relu(self.c1(pooled_output))
        #classifier_prev_output = F.relu(self.c2(classifier))
        classifier_output = self.c3(classifier_prev_output)

        return classifier_output, classifier_prev_output

class Adversary(nn.Module):
    def __init__(self, identity_labels = 2):
        super(Adversary, self).__init__()

        self.a1 = nn.Linear(324,120)
        self.a2 = nn.Linear(120, identity_labels)

        nn.init.xavier_normal_(self.a1.weight)

    def forward(self, input_ids):


        #Adversary
        adversary = F.relu(self.a1(input_ids))
        adversary_output = self.a2(adversary)

        return adversary_output

def conduct_validation(net, data_loader, adv = False):

    eval_loss, eval_accuracy, eval_precision, eval_recall, eval_f1 = 0, 0, 0, 0, 0
    nb_eval_steps = 0
    
    predictions_net = np.empty((0,))
    truths = np.empty((0,))
    identities = np.empty((0,))
    correct_net = 0
    total = 0

    net.eval()
    with torch.no_grad(): # IMPORTANT: we don't want to do back prop during validation/testing!
      for index, data in enumerate(data_loader):

        text, toxic_truth, female_truth = data

        text = text.to(device)
        toxic_truth = toxic_truth.to(device)
        female_truth = female_truth.to(device)

        if adv:
          net_outputs, net_prev_outputs = net(text)
        else:
          net_outputs = net(text)
        _, net_predicted = torch.max(net_outputs.data, 1)

        batch_size = toxic_truth.size(0)
        total += batch_size
        correct_net_batch = (net_predicted == toxic_truth).sum().item()
        correct_net += correct_net_batch

        
        predictions_net = np.concatenate((predictions_net, net_predicted.cpu().numpy()))
        truths = np.concatenate((truths, toxic_truth.cpu().numpy()))
        identities = np.concatenate((identities, female_truth.cpu().numpy()))

        pred = net_predicted.detach().cpu().numpy()
        label_ids = toxic_truth.to('cpu').numpy()

        tmp_eval_accuracy, tmp_eval_precision, temp_eval_recall, tmp_eval_f1 = get_metrics(label_ids, pred)

        eval_accuracy += tmp_eval_accuracy
        eval_precision += tmp_eval_precision
        eval_recall += temp_eval_recall
        eval_f1 += tmp_eval_f1
        nb_eval_steps += 1

    f1_score = eval_f1/nb_eval_steps
    prec_score = eval_precision/nb_eval_steps
    recall_score = eval_recall/nb_eval_steps
    acc_score = eval_accuracy/nb_eval_steps

    print("F1 Score: ", f1_score)
    print("Precision Score: ", prec_score)
    print("Recall Score: ", recall_score)
    print("Acc Score: ", acc_score, "\n\n")

    net.train()
    
    return (predictions_net, truths, identities, acc_score)

def pretrain_classifier(clf, optimizer_clf, train_loader, loss_criterion, epochs):

  pretrain_classifier_loss = 0
  steps = 0

  for epoch in range(epochs):

    print("Epoch: ", epoch + 1)
    epoch_loss = 0
    epoch_batches = 0

    for i, data in enumerate(train_loader): # starting from the 0th batch
        # get the inputs and labels
        inputs, toxicity_true, female_true = data
        inputs = inputs.to(device)
        # toxicity_true = torch.sparse.torch.eye(2).index_select(dim=0, index=toxicity_true) 
        # female_true = torch.sparse.torch.eye(2).index_select(dim=0, index=female_true) 
        toxicity_true = toxicity_true.to(device)
        female_true = female_true.to(device)

        optimizer_clf.zero_grad()

        classifier_output, _ = clf(inputs)
        classifier_loss = loss_criterion(classifier_output, toxicity_true) # compute loss
        classifier_loss.backward() # back prop
        optimizer_clf.step()
        pretrain_classifier_loss += classifier_loss.item()
        epoch_loss += classifier_loss.item()
        epoch_batches += 1
        steps += 1

    print("Average Pretrain Classifier epoch loss: ", epoch_loss/epoch_batches)
  print("Average Pretrain Classifier batch loss: ", pretrain_classifier_loss/steps)

  return clf


def pretrain_adversary(adv, clf, optimizer_adv, train_loader, loss_criterion, epochs):
  
  pretrain_adversary_loss = 0
  steps = 0

  for epoch in range(epochs):

    print("Epoch: ", epoch + 1)
    epoch_loss = 0
    epoch_batches = 0
    for i, data in enumerate(train_loader): # starting from the 0th batch
        # get the inputs and labels
        inputs, toxicity_true, female_true = data
        inputs = inputs.to(device)
        # toxicity_true = torch.sparse.torch.eye(2).index_select(dim=0, index=toxicity_true) 
        # female_true = torch.sparse.torch.eye(2).index_select(dim=0, index=female_true) 
        toxicity_true = toxicity_true.to(device)
        female_true = female_true.to(device)

        optimizer_adv.zero_grad()

        _, classifier_prev_output = clf(inputs)
        adversary_output = adv(classifier_prev_output)
        adversary_loss = loss_criterion(adversary_output, female_true) # compute loss
        adversary_loss.backward() # back prop
        optimizer_adv.step()
        pretrain_adversary_loss += adversary_loss.item()
        epoch_loss += adversary_loss.item()
        epoch_batches += 1
        steps += 1

    print("Average Pretrain Adversary epoch loss: ", epoch_loss/epoch_batches)
  print("Average Pretrain Adversary batch loss: ", pretrain_adversary_loss/steps)

  return adv


def train_adversary(adv, clf, optimizer_adv, train_loader, loss_criterion, epochs=1):
  
  adv_loss = 0
  steps = 0

  for epoch in range(epochs):
    for i, data in enumerate(train_loader): # starting from the 0th batch
        # get the inputs and labels
        inputs, toxicity_true, female_true = data
        inputs = inputs.to(device)
        # toxicity_true = torch.sparse.torch.eye(2).index_select(dim=0, index=toxicity_true) 
        # female_true = torch.sparse.torch.eye(2).index_select(dim=0, index=female_true) 
        toxicity_true = toxicity_true.to(device)
        female_true = female_true.to(device)

        optimizer_adv.zero_grad()

        classifier_output, classifier_prev_output = clf(inputs)
        adversary_output = adv(classifier_prev_output)
        adversary_loss = loss_criterion(adversary_output, female_true) # compute loss
        adversary_loss.backward() # back prop
        optimizer_adv.step()
        adv_loss += adversary_loss.item()
        steps += 1
  
  print("Average Adversary batch loss: ", adv_loss/steps)

  return adv

def train_classifier(clf, optimizer_clf, adv, train_loader, loss_criterion, lbda):

  for i, data in enumerate(train_loader): # starting from the 0th batch
      # get the inputs and labels
      inputs, toxicity_true, female_true = data
      inputs = inputs.to(device)
      # toxicity_true = torch.sparse.torch.eye(2).index_select(dim=0, index=toxicity_true) 
      # female_true = torch.sparse.torch.eye(2).index_select(dim=0, index=female_true) 
      toxicity_true = toxicity_true.to(device)
      female_true = female_true.to(device)

      # Toxic classifier part

      optimizer_clf.zero_grad()

      classifier_output, classifier_prev_output = clf(inputs)
      adversary_output = adv(classifier_prev_output)
      adversary_loss = loss_criterion(adversary_output, female_true)
      classifier_loss = loss_criterion(classifier_output, toxicity_true) # compute loss
      total_classifier_loss = classifier_loss - lbda * adversary_loss
      total_classifier_loss.backward() # back prop
      
      optimizer_clf.step()

      print("Adversary Mini-Batch loss: ", adversary_loss.item())
      print("Classifier Mini-Batch loss: ", classifier_loss.item())
      print("Total Mini-Batch loss: ", total_classifier_loss.item())

      break

  return clf

import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'

def fpr(cm):
  FP = cm.sum(axis=0) - np.diag(cm)  
  FN = cm.sum(axis=1) - np.diag(cm)
  TP = np.diag(cm)
  TN = cm.sum() - (FP + FN + TP)
  FPR = FP/(FP+TN)
  return FPR

#NEW IMPLEMENTATION WITH PRETRAINING

# Training Process

lambda_params = [3]

lbda_train_accs = []
lbda_valid_accs = []
protected_toxicity_rates = []
unprotected_toxicity_rates = []
protected_tp_rates = []
unprotected_tp_rates = []
protected_fp_rates = []
unprotected_fp_rates = []
demo_parity_scores = []
tp_parity_scores = []
fp_parity_scores = []
equ_odds_scores = []

for lbda in lambda_params:

  #DEFINING MODELS

  clf = Classifier(toxicity_labels = 3) # instantiate the nn
  adv = Adversary(identity_labels = 2)

  loss_criterion = torch.nn.CrossEntropyLoss()

  # Defining optimizers
  optimizer_adv = optim.Adam(adv.parameters(), lr=0.001)

  lrlast = .001
  lrmain = .00001
  optimizer_clf = optim.Adam(
      [
          {"params":clf.bert.parameters(),"lr": lrmain},
          {"params":clf.c1.parameters(), "lr": lrlast},
          #{"params":clf.c2.parameters(), "lr": lrlast},
      {"params":clf.c3.parameters(), "lr": lrlast}    
    ])

  clf.to(device)
  adv.to(device)

  #PRETRAIN CLASSIFIER

  for param in adv.parameters():
    param.requires_grad = False

  clf = pretrain_classifier(clf, optimizer_clf, train_loader, loss_criterion, 3)

  for param in adv.parameters():
    param.requires_grad = True

  #PRETRAIN ADVERSARY

  for param in clf.parameters():
    param.requires_grad = False

  adv = pretrain_adversary(adv, clf, optimizer_adv, train_loader, loss_criterion, 3)

  for param in clf.parameters():
    param.requires_grad = True

  print('Lambda: ' + str(lbda))

  train_accs = []
  valid_accs = []
  iterations = 10

  for iteration in range(iterations):  # loop over the dataset multiple times
      print("Iteration: ", iteration)

      #TRAIN ADVERSARY FOR 1 EPOCH

      for param in clf.parameters():
        param.requires_grad = False

      adv = train_adversary(adv, clf, optimizer_adv, train_loader, loss_criterion, epochs=1)

      for param in clf.parameters():
        param.requires_grad = True

      #TRAIN CLASSIFIER FOR 1 SAMPLE MINI BATCH

      for param in adv.parameters():
        param.requires_grad = False

      clf = train_classifier(clf, optimizer_clf, adv, train_loader, loss_criterion, lbda)

      for param in adv.parameters():
        param.requires_grad = True

      if (iteration + 1) % 2 == 0:
        
        print('Training metrics:')
        y_pred, actual_labels, protected_labels, acc_score = conduct_validation(clf, train_loader, adv=True)
        train_accs.append(acc_score)

        print("\n")
        print("Fairness Metrics on Train:")
        non_protected_labels = np.asarray(get_unprotected_class(protected_labels))
        thres = 0.5
        female_tox_rate, nf_tox_rate, female_tp_rate, nf_tp_rate, female_fp_rate, nf_fp_rate, demo_parity, tp_parity, fp_parity, equ_odds =\
        get_fairness_metrics(actual_labels, y_pred, protected_labels, non_protected_labels, thres)

        print("offensive Prediction Rates: ", "AAE -", female_tox_rate, "Non-AAE - ", nf_tox_rate)
        print("True Positive Prediction Rates: ", "AAE -", female_tp_rate, "Non-AAE - ", nf_tp_rate)
        print("False Positive Prediction Rates: ", "AAE -", female_fp_rate, "Non-AAE - ", nf_fp_rate)
        #print("Demographic Parity: ", demo_parity)
        print("True Positive Parity: ", tp_parity)
        print("False Positive Parity: ", fp_parity)
        print("Equalized Odds: ", equ_odds)
        print("\n")
        
        FairClassifier_result = df_train.copy()
        #bert_result['data_type'] = bert_result['data_type'].values
        FairClassifier_result['pred'] = y_pred
        FairClassifier_result = FairClassifier_result.loc[:, ['label', 'pred', 'race']]
        aae_group = FairClassifier_result.loc[FairClassifier_result['race'] == 0]
        other_group = FairClassifier_result.loc[FairClassifier_result['race'] != 0]
        
        print("BERT Bias Evaluation: ")
        print('\tHate Speech' + ' Offensive' + '  Neither')
        aae_cm = confusion_matrix(aae_group['label'], aae_group['pred'])
        print("AAE" + '\t' + str(fpr(aae_cm)))
        other_cm = confusion_matrix(other_group['label'], other_group['pred'])
        print("Non-AAE" + '\t' + str(fpr(other_cm)))
        print("\n\n")

        print('Validation metrics:')
        y_pred, actual_labels, protected_labels, acc_score = conduct_validation(clf, val_loader, adv=True)
        valid_accs.append(acc_score)
        
        print("\n")
        print("Fairness Metrics on Validation:")
        non_protected_labels = np.asarray(get_unprotected_class(protected_labels))
        thres = 0.5
        female_tox_rate, nf_tox_rate, female_tp_rate, nf_tp_rate, female_fp_rate, nf_fp_rate, demo_parity, tp_parity, fp_parity, equ_odds =\
        get_fairness_metrics(actual_labels, y_pred, protected_labels, non_protected_labels, thres)

        print("offensive Prediction Rates: ", "AAE -", female_tox_rate, "Non-AAE - ", nf_tox_rate)
        print("True Positive Prediction Rates: ", "AAE -", female_tp_rate, "Non-AAE - ", nf_tp_rate)
        print("False Positive Prediction Rates: ", "AAE -", female_fp_rate, "Non-AAE - ", nf_fp_rate)
        #print("Demographic Parity: ", demo_parity)
        print("True Positive Parity: ", tp_parity)
        print("False Positive Parity: ", fp_parity)
        print("Equalized Odds: ", equ_odds)
        print("\n")

        cm = ConfusionMatrix(actual_labels, y_pred)
        class_rep = classification_report (actual_labels, y_pred)
        print(cm)
        print(class_rep)
        print("\n")

        FairClassifier_result = df_val.copy()
        #bert_result['data_type'] = bert_result['data_type'].values
        FairClassifier_result['pred'] = y_pred
        FairClassifier_result = FairClassifier_result.loc[:, ['label', 'pred', 'race']]
        aae_group = FairClassifier_result.loc[FairClassifier_result['race'] == 0]
        other_group = FairClassifier_result.loc[FairClassifier_result['race'] != 0]
        
        print("BERT Bias Evaluation: ")
        print('\tHate Speech' + ' Offensive' + '  Neither')
        aae_cm = confusion_matrix(aae_group['label'], aae_group['pred'])
        print("AAE" + '\t' + str(fpr(aae_cm)))
        other_cm = confusion_matrix(other_group['label'], other_group['pred'])
        print("Non-AAE" + '\t' + str(fpr(other_cm)))
        print("\n")


        print("\n\n\n__________________")

        if iteration == iterations -1:
          protected_toxicity_rates.append(female_tox_rate)
          unprotected_toxicity_rates.append(nf_tox_rate)
          protected_tp_rates.append(female_tp_rate)
          unprotected_tp_rates.append(nf_tp_rate)
          protected_fp_rates.append(female_fp_rate)
          unprotected_fp_rates.append(nf_fp_rate)
          demo_parity_scores.append(demo_parity)
          tp_parity_scores.append(tp_parity)
          fp_parity_scores.append(fp_parity)
          equ_odds_scores.append(equ_odds)

  lbda_train_accs.append(train_accs)  
  lbda_valid_accs.append(valid_accs)

  # del clf
  # del adv

  # torch.cuda.empty_cache()

print('Finished Training')

torch.save(clf.state_dict(), path + "SC_Classifier_Final_AllData")
torch.save(adv.state_dict(), path + "SC_Adversary_Final_AllData")

del adv
del clf
torch.cuda.empty_cache()









