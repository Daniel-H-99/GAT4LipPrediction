import torch
import numpy as np 
import scipy.sparse as sp 
import pickle as pkl

def load_data(dataset="face"):
    
    print("loading {} dataset ... ". format(dataset))

    path="./data/"+dataset+"/" 

    if dataset == 'cora':
        idx_features_labels = np.genfromtxt("{}{}.content".format(path,dataset), dtype=np.dtype(str))
        features = sp.csr_matrix(idx_features_labels[:,1:-1], dtype=np.float32)
        labels = encode_onehot(idx_features_labels[:,-1])

        idx = np.array(idx_features_labels[:,0],dtype=np.int32)
        idx_map = {j: i for i,j in enumerate(idx)}
        edges_unordered = np.genfromtxt("{}{}.cites".format(path,dataset), dtype=np.int32)
        edges = np.array(list(map(idx_map.get, edges_unordered.flatten())), dtype=np.int32).reshape(edges_unordered.shape)
        adj = sp.coo_matrix((np.ones(edges.shape[0]), (edges[:,0], edges[:,1])), shape=(labels.shape[0], labels.shape[0]), dtype=np.float32)

    elif dataset == 'face':
        with open(path + 'nodes.pickle', 'rb') as f:
            idx_features_labels = pkl.load(f)
        with open(path + 'edges.pickle', 'rb') as f:
            edges = pkl.load(f)
        with open(path + 'train_indice.pickle', 'rb') as f:
            idx_train = torch.LongTensor(pkl.load(f))
        with open(path + 'eval_indice.pickle', 'rb') as f:
            idx_eval = torch.LongTensor(pkl.load(f))
        with open(path + 'test_indice.pickle', 'rb') as f:
            idx_test = torch.LongTensor(pkl.load(f))
        num_nodes = idx_features_labels.shape[0]
        features =  torch.FloatTensor(normalize_features(idx_features_labels[:, 1:-20]))
        labels = torch.FloatTensor(idx_features_labels[:, -20:])
        idx = idx_features_labels[:, 0]
        adj = np.zeros((num_nodes, num_nodes))
        adj[np.tile(np.array(range(num_nodes))[:, np.newaxis], (1, 4)).reshape(-1), edges.reshape(-1)] = 1
        adj = torch.FloatTensor(adj)
        return  adj, features, labels, idx_train, idx_eval, idx_test
    elif dataset == 'citeseer':
        # TODO step 3.
        pass
    
    adj = adj + adj.T.multiply(adj.T>adj) - adj.multiply(adj.T>adj)
    features = normalize_features(features)
    adj = normalize_adj(adj+sp.eye(adj.shape[0]))

    idx_train = range(140)
    idx_val = range(200,500)
    idx_test = range(500,1500)

    adj = torch.FloatTensor(np.array(adj.todense()))
    features = torch.FloatTensor(np.array(features.todense()))
    labels = torch.LongTensor(np.where(labels)[1])

    idx_train = torch.LongTensor(idx_train)
    idx_val = torch.LongTensor(idx_val)
    idx_test = torch.LongTensor(idx_test)

    return adj, features, labels, idx_train, idx_val, idx_test 

      

def accuracy(output, labels):
    preds = output.max(1)[1].type_as(labels)
    correct = preds.eq(labels).double()
    correct = correct.sum()

    return correct / len(labels)

def normalize_adj(mx): # A_hat = DAD
    rowsum = np.array(mx.sum(1))
    r_inv_sqrt = np.power(rowsum, -0.5).flatten()
    r_inv_sqrt[np.isinf(r_inv_sqrt)] = 0.
    r_mat_inv_sqrt = sp.diags(r_inv_sqrt)
    mx_to =  mx.dot(r_mat_inv_sqrt).transpose().dot(r_mat_inv_sqrt)
    return mx_to

def normalize_features(mx):
    rowsum = np.array(mx.sum(1))
    r_inv = np.power(rowsum, -1).flatten()
    r_inv[np.isinf(r_inv)] = 0.
    r_mat_inv = sp.diags(r_inv)
    mx_to =  r_mat_inv.dot(mx) 
    return mx_to 

def encode_onehot(labels):
    classes = set(labels)
    classes_dict = {c: np.identity(len(classes))[i,:] for i, c in enumerate(classes)}
    labels_onehot = np.array(list(map(classes_dict.get, labels)), dtype=np.int32)
    return labels_onehot 

import random
import torch
import os
import numpy as np
import copy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# data manager for recording, saving, and plotting
class AverageMeter(object):
    def __init__(self, args, name='noname', save_all=False, surfix='.', x_label=None):
        self.args = args
        self.name = name
        self.save_all = save_all
        self.surfix = surfix
        self.path = os.path.join(args.path, args.result_dir, args.name, surfix)
        self.x_label = x_label
        self.reset()
    def reset(self):
        self.max = - 100000000
        self.min = 100000000
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0
        if self.save_all:
            self.data = []
        self.listeners = []
    def load_array(self, data):
        self.max = max(data)
        self.min = min(data)
        self.val = data[-1]
        self.sum = sum(data)
        self.count = len(data)
        if self.save_all:
            self.data.extend(data)
    def update(self, val, weight=1):
        prev = copy.copy(self)
        self.val = val
        self.sum += val * weight
        self.count += weight
        self.avg = self.sum / self.count
        if self.save_all:
            self.data.append(val)
        is_max, is_min = False, False
        if val > self.max:
            self.max = val
            is_max = True
        if val < self.min:
            self.min = val
            is_min = True
        new = copy.copy(self)
        for listener in self.listeners:
            listener.notify(prev, new)
            del prev, new
        return (is_max, is_min)
    def save(self):
        with open(os.path.join(self.path, "{}.txt".format(self.name)), "w") as file:
            file.write("max: {0:.4f}\nmin: {1:.4f}".format(self.max, self.min))
        if self.save_all:
            np.savetxt(os.path.join(self.path, "{}.csv".format(self.name)), self.data, delimiter=',')
    def plot(self, scatter=True):
        assert self.save_all
        plot_1D(self.args, self.data, scatter=scatter, surfix=self.surfix, name=self.name, x_label=self.x_label, y_label=self.name)
    def plot_over(self, rhs, scatter=True, x_label=True, y_label=True, title=None, save=True):
        assert self.save_all and rhs.save_all
        plot_2D(self.args, self.data, rhs.data, scatter=scatter, surfix=self.surfix, name=self.name, x_label=self.x_label, y_label=self.name)
    def attach_combo_listener(self, f, threshold=1):
        listener = ComboListener(f, threshold)
        self.listeners.append(listener)
        return listener

class Listener(object):
    def __init__(self):
        self.value = None
    def listen(self):
        return self.value

class ComboListener(Listener):
    def __init__(self, f, threshold):
        super(ComboListener, self).__init__()
        self.f = f
        self.threshold = threshold
        self.cnt = 0
        self.value = False
    def notify(self, prev, new):
        if self.f(prev, new):
            self.cnt += 1
        else:
            self.cnt = 0
        if self.cnt >= self.threshold:
            self.value = True
    
    
# convert idice of words to real words
def seq2sen(batch, vocab):
    sen_list = []

    for seq in batch:
        seq_strip = seq[:seq.index(1)+1]
        sen = ' '.join([vocab.itow(token) for token in seq_strip[1:-1]])
        sen_list.append(sen)

    return sen_list

# shuffle source and target lists in paired manner
def shuffle_list(src, tgt):
    index = list(range(len(src)))
    random.shuffle(index)

    shuffle_src = []
    shuffle_tgt = []

    for i in index:
        shuffle_src.append(src[i])
        shuffle_tgt.append(tgt[i])

    return shuffle_src, shuffle_tgt

# simple metric whether each predicted words match to original ones
def val_check(pred, ans):
    # pred, ans: (batch x length)
    batch, length = pred.shape
    num_correct = (pred == ans).sum()
    total = batch * length
    
    return num_correct, total

# save data, such as model, optimizer
def save(args, surfix, data):
    torch.save(data, os.path.join(args.path, args.ckpt_dir, args.name, "{}.pt".format(surfix)))

# load data, such as model, optimizer
def load(args, surfix, map_location='cpu'):
    return torch.load(os.path.join(args.path, args.ckpt_dir, "{}.pt".format(surfix)), map_location=map_location)

# draw 1D plot
def plot_1D(args, x, scatter=True, surfix='.', name='noname', x_label=None, y_label=None):
    if scatter:
        plot = plt.scatter(range(1, 1+ len(x)), x)
    else:
        plot = plt.plot(range(1, 1 + len(x)), x)
    if x_label is not None:
        plt.xlabel(x_label)
    if y_label is not None:
        plt.ylabel(y_label)
    plt.savefig(os.path.join(args.path, args.result_dir, args.name, surfix, "{}.jpg".format(name)))
    plt.close(plt.gcf())
    
# draw 2D plot
def plot_2D(args, x, y, scatter=True, surfix='.', name='noname', x_label=None, y_label=None):
    assert len(x) == len(y)
    if scatter:
        plot = plt.scatter(x, y)
    else:
        plot = plt.plot(x, y)
    if x_label is not None:
        plt.xlabel(x_label)
    if y_label is not None:
        plt.ylabel(y_label)
    plt.savefig(os.path.join(args.path, args.result_dir, args.name, surfix, "{}.jpg".format(name)))
    plt.close(plt.gcf())
    
    
import torch
import os
import numpy as np
import math
import yaml
import torch.nn.init as init
import time
#import librosa
import cv2

def drawLips(keypoints, new_img, c = (255, 255, 255), th = 1):

# 	keypoints = np.int(keypoints)
	keypoints = keypoints.astype(int)
# 	print(keypoints)
	for i in range(48, 59):
		cv2.line(new_img, tuple(keypoints[i]), tuple(keypoints[i+1]), color=c, thickness=th)
	cv2.line(new_img, tuple(keypoints[48]), tuple(keypoints[59]), color=c, thickness=th)
	cv2.line(new_img, tuple(keypoints[48]), tuple(keypoints[60]), color=c, thickness=th)
	cv2.line(new_img, tuple(keypoints[54]), tuple(keypoints[64]), color=c, thickness=th)
	cv2.line(new_img, tuple(keypoints[67]), tuple(keypoints[60]), color=c, thickness=th)
	for i in range(60, 67):
		cv2.line(new_img, tuple(keypoints[i]), tuple(keypoints[i+1]), color=c, thickness=th)
	return new_img

def getOriginalKeypoints(kp_features_mouth, N, tilt, mean):
	kp_dn = N * kp_features_mouth
	x, y = kp_dn[:20], kp_dn[20:]
	c, s = np.cos(tilt), np.sin(tilt)
	x_dash, y_dash = x*c + y*s, -x*s + y*c
	kp_tilt = np.hstack((x_dash.reshape((-1,1)), y_dash.reshape((-1, 1))))
	kp = kp_tilt + mean
	kp = kp.astype('int')
#     print(kp)
	return kp
    