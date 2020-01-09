# AUTOGENERATED! DO NOT EDIT! File to edit: 01_decoder.ipynb (unless otherwise specified).

__all__ = ['train_data', 'test_data', 'sample_submission']

# Cell
import pandas as pd # package for high-performance, easy-to-use data structures and data analysis
import numpy as np # fundamental package for scientific computing with Python
import matplotlib
import matplotlib.pyplot as plt # for plotting

import re

import string
import gc

from fastai2.basics import *
from fastai2.text.all import *
from fastai2.callback.all import *
import pickle
import os

# Cell
print('Reading data...')
train_data = pd.read_csv(data_path/'train/train.csv')
test_data = pd.read_csv(data_path/'test/test.csv')
sample_submission = pd.read_csv(str(data_path/'sample_submission.csv'))
print('Reading data completed')