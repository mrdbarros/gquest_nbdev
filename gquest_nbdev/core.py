# AUTOGENERATED! DO NOT EDIT! File to edit: dev/00_core.ipynb (unless otherwise specified).

__all__ = ['color', 'init_notebook_mode(connected', 'eng_stopwords', 'train_data', 'test_data', 'sample_submission',
           'testeFunc']

# Cell
import nltk
nltk.download('stopwords')

# Cell
import pandas as pd # package for high-performance, easy-to-use data structures and data analysis
import numpy as np # fundamental package for scientific computing with Python
import matplotlib
import matplotlib.pyplot as plt # for plotting
import seaborn as sns # for making plots with seaborn
color = sns.color_palette()
import plotly.offline as py
py.init_notebook_mode(connected=True)
from plotly.offline import init_notebook_mode, iplot
init_notebook_mode(connected=True)
import plotly.graph_objs as go
import plotly.offline as offline
offline.init_notebook_mode()
#import cufflinks and offline mode
import cufflinks as cf
cf.go_offline()

# Venn diagram
from matplotlib_venn import venn2
import re
from nltk.probability import FreqDist
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string
eng_stopwords = stopwords.words('english')
import gc

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD

# Cell
import os
print(os.listdir("../data/gquest_data/"))


# Cell
print('Reading data...')
train_data = pd.read_csv('../data/gquest_data/train.csv')
test_data = pd.read_csv('../data/gquest_data/test.csv')
sample_submission = pd.read_csv('../data/gquest_data/sample_submission.csv')
print('Reading data completed')

# Cell
print('Size of train_data', train_data.shape)
print('Size of test_data', test_data.shape)
print('Size of sample_submission', sample_submission.shape)
test_eq(train_data.shape,(6079,41))
test_eq(test_data.shape,(476,11))
test_eq(sample_submission.shape,(476,31))

# Cell
def testeFunc(message):
    "doc string test"
    return(f'The test message is: {message}')