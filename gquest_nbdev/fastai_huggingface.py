# AUTOGENERATED! DO NOT EDIT! File to edit: fastai_v1_transformers-BWW.ipynb (unless otherwise specified).

__all__ = ['seed_all', 'MODEL_CLASSES', 'TransformersBaseTokenizer', 'Tokenizer_MultiColumn', 'TransformersVocab',
           'SortishSampler_Stateful', 'TokenizeProcessorDualBert', 'TabularDataBunch_Sample', 'TabularList_Sample',
           'ExactSampler', 'no_collate', 'TextClasDataBunch_Multi', 'TextList_Multi', 'MixedObjectDataBunch',
           'MixedObjectLists', 'MixedObjectList', 'LabelList_Multi', 'LabelLists_Multi', 'TabularModel_NoCat',
           'CustomTransformerModel', 'AvgSpearman', 'AvgSpearman2', 'AddExtraBunch', 'FlattenedLoss_BWW',
           'CrossEntropyFlat_BWW', 'model_unfreezing_and_training', 'get_preds_as_nparray']

# Cell
import numpy as np # linear algebra
import pandas as pd # data processing, CSV file I/O (e.g. pd.read_csv)
from pathlib import Path

import os

import torch
import torch.optim as optim

import random

# fastai
from fastai import *
from fastai.text import *
from fastai.callbacks import *

# classification metric
from scipy.stats import spearmanr

# transformers
from fastai.tabular import *

from transformers import PreTrainedModel, PreTrainedTokenizer, PretrainedConfig,RobertaModel
from transformers import RobertaForSequenceClassification, RobertaTokenizer, RobertaConfig,AlbertForSequenceClassification, AlbertTokenizer, AlbertConfig

# Cell
def seed_all(seed_value):
    random.seed(seed_value) # Python
    np.random.seed(seed_value) # cpu vars
    torch.manual_seed(seed_value) # cpu  vars

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed_value)
        torch.cuda.manual_seed_all(seed_value) # gpu vars
        torch.backends.cudnn.deterministic = True  #needed
        torch.backends.cudnn.benchmark = False

# Cell
MODEL_CLASSES = {
    'albert': (AlbertForSequenceClassification, AlbertTokenizer, AlbertConfig),
    'roberta': (RobertaModel, RobertaTokenizer,
                RobertaConfig(hidden_act="gelu_new",
                              hidden_dropout_prob=0.1,
                              attention_probs_dropout_prob=0.1,
                              #max_position_embeddings=1024,
                              layer_norm_eps=1e-12))
}

# Cell
class TransformersBaseTokenizer(BaseTokenizer):
    """Wrapper around PreTrainedTokenizer to be compatible with fast.ai"""
    def __init__(self, pretrained_tokenizer: PreTrainedTokenizer, model_type = 'roberta', **kwargs):
        self._pretrained_tokenizer = pretrained_tokenizer
        self.max_seq_len = pretrained_tokenizer.max_len
        self.model_type = model_type

    def __call__(self, *args, **kwargs):
        return self

    def tokenizer(self, t) -> List[List[str]]:


        all_columns_inputs=[]
        #pdb.set_trace()
        for column_i in range(len(t)):
            inputs = self._pretrained_tokenizer.encode_plus(t[column_i],add_special_tokens=True,
                                               max_length=self.max_seq_len,truncation_strategy='longest_first')
            input_ids =  inputs["input_ids"]
            input_masks = [1] * len(input_ids)
            input_segments = inputs["token_type_ids"]
            padding_length = self.max_seq_len - len(input_ids)
            padding_id = self._pretrained_tokenizer.pad_token_id
            input_ids = input_ids + ([padding_id] * padding_length)
            input_masks = input_masks + ([0] * padding_length)
            input_segments = input_segments + ([0] * padding_length)
            all_columns_inputs.append(np.array([input_ids, input_masks, input_segments]))


        return all_columns_inputs

# Cell
class Tokenizer_MultiColumn(Tokenizer):

    def _process_all_1(self, texts:Collection[str]) -> List[List[str]]:
        "Process a list of `texts` in one process."
        tok = self.tok_func(self.lang)
        if self.special_cases: tok.add_special_cases(self.special_cases)
        return [self.process_text(t, tok) for t in texts]

# Cell
class TransformersVocab(Vocab):
    def __init__(self, tokenizer: PreTrainedTokenizer):
        super(TransformersVocab, self).__init__(itos = [])
        self.tokenizer = tokenizer

    def numericalize(self, t:Collection[List[str]]) -> List[List[int]]:
        "Convert a list of tokens `t` to their ids."
        return t
        #return self.tokenizer.encode(t)

    def textify(self, nums:Collection[List[int]], sep=' ') -> List[List[str]]:
        "Convert a list of `nums` to their tokens."
        ret = []
        for i in range(len(nums)):
            ret.append(self.tokenizer.decode(np.array(nums[i]).tolist()[0]))
        return ret

    def __getstate__(self):
        return {'itos':self.itos, 'tokenizer':self.tokenizer}

    def __setstate__(self, state:dict):
        self.itos = state['itos']
        self.tokenizer = state['tokenizer']
        self.stoi = collections.defaultdict(int,{v:k for k,v in enumerate(self.itos)})
        self.current_idxs=[]

# Cell
class SortishSampler_Stateful(SortishSampler):
    def __iter__(self):
        idxs = np.random.permutation(len(self.data_source))
        sz = self.bs * 50
        ck_idx = [idxs[i:i + sz] for i in range(0, len(idxs), sz)]
        sort_idx = np.concatenate([sorted(s, key=self.key, reverse=True) for s in ck_idx])
        sz = self.bs
        ck_idx = [sort_idx[i:i + sz] for i in range(0, len(sort_idx), sz)]
        max_ck = np.argmax([self.key(ck[0]) for ck in ck_idx])  # find the chunk with the largest key,
        ck_idx[0], ck_idx[max_ck] = ck_idx[max_ck], ck_idx[0]  # then make sure it goes first.
        sort_idx = np.concatenate(np.random.permutation(ck_idx[1:])) if len(ck_idx) > 1 else np.array([], dtype=np.int)
        sort_idx = np.concatenate((ck_idx[0], sort_idx))
        self.current_idxs=sort_idx
        return iter(sort_idx)

# Cell
def _multicolumn_texts(texts:Collection[str]):

    df = pd.DataFrame({i:texts[:,i] for i in range(texts.shape[1])})

    return df.iloc[:,range(texts.shape[1])].values

# Cell
class TokenizeProcessorDualBert(TokenizeProcessor):
    "`PreProcessor` that tokenizes the texts in `ds`."
    def __init__(self, ds:ItemList=None, tokenizer:Tokenizer=None, chunksize:int=10000,
                 mark_fields:bool=False, include_bos:bool=True, include_eos:bool=False):
        self.tokenizer,self.chunksize,self.mark_fields = ifnone(tokenizer, Tokenizer()),chunksize,mark_fields
        self.include_bos, self.include_eos = include_bos, include_eos

    def process_one(self, item):
        return self.tokenizer._process_all_1(_multicolumn_texts([item]))[0]

    def process(self, ds):
        ds.items = _multicolumn_texts(ds.items)
        tokens = []
        #pdb.set_trace()
        for i in progress_bar(range(0,len(ds),self.chunksize), leave=False):
            tokens += self.tokenizer.process_all(ds.items[i:i+self.chunksize])

        ds.items = tokens

# Cell
class TabularDataBunch_Sample(TabularDataBunch):
    @classmethod
    def create(cls, train_ds: Dataset, valid_ds: Dataset, test_ds: Optional[Dataset] = None, path: PathOrStr = '.',
               bs: int = 64,
               val_bs: int = None, num_workers: int = defaults.cpus, dl_tfms: Optional[Collection[Callable]] = None,
               device: torch.device = None, collate_fn: Callable = data_collate, no_check: bool = False,
               sampler=None,**dl_kwargs) -> 'DataBunch':
        "Create a `DataBunch` from `train_ds`, `valid_ds` and maybe `test_ds` with a batch size of `bs`. Passes `**dl_kwargs` to `DataLoader()`"
        datasets = cls._init_ds(train_ds, valid_ds, test_ds)
        val_bs = ifnone(val_bs, bs)

        dls = [DataLoader(d, b, shuffle=False, drop_last=s, num_workers=num_workers, **dl_kwargs,sampler=ExactSampler(d.x)
                          ) for d, b, s in
               zip(datasets, (bs, val_bs, val_bs, val_bs), (True, False, False, False)) if d is not None]
        return cls(*dls, path=path, device=device, dl_tfms=dl_tfms, collate_fn=collate_fn, no_check=no_check)

# Cell
class TabularList_Sample(TabularList):
    _bunch=TabularDataBunch_Sample

# Cell
class ExactSampler(Sampler):

    def __init__(self, data_source:NPArrayList):
        self.data_source = data_source
        self._exact_idxs=list(range(len(data_source)))

    def __len__(self) -> int: return len(self.data_source)

    @property
    def exact_idxs(self):
        return self._exact_idxs

    @exact_idxs.setter
    def exact_idxs(self,value):
        self._exact_idxs=value

    def __iter__(self):
        ret = iter(self._exact_idxs)
        return ret

# Cell
def no_collate(samples:BatchSamples) -> Tuple[LongTensor, LongTensor]:
    "Function that collect samples and adds padding. Flips token order if needed"
    samples = to_data(samples)
    res=tensor(np.array([s[0] for s in samples]))

    return res, tensor(np.array([s[1] for s in samples]))

# Cell
class TextClasDataBunch_Multi(TextDataBunch):
    "Create a `TextDataBunch` suitable for training an RNN classifier."
    @classmethod
    def create(cls, train_ds, valid_ds, test_ds=None, path:PathOrStr='.', bs:int=32, val_bs:int=None, pad_idx=1,
               pad_first=True, device:torch.device=None, no_check:bool=False, backwards:bool=False,
               dl_tfms:Optional[Collection[Callable]]=None, **dl_kwargs) -> DataBunch:
        "Function that transform the `datasets` in a `DataBunch` for classification. Passes `**dl_kwargs` on to `DataLoader()`"
        datasets = cls._init_ds(train_ds, valid_ds, test_ds)
        val_bs = ifnone(val_bs, bs)
        collate_fn = partial(no_collate)
        train_sampler = SortishSampler_Stateful(datasets[0].x, key=lambda t: len(datasets[0][t][0].data), bs=bs)
        train_dl = DataLoader(datasets[0], batch_size=bs, sampler=train_sampler, drop_last=True, **dl_kwargs)
        dataloaders = [train_dl]
        for ds in datasets[1:]:
            lengths = [len(t) for t in ds.x.items]
            sampler = SortSampler(ds.x, key=lengths.__getitem__)
            dataloaders.append(DataLoader(ds, batch_size=val_bs, sampler=sampler, **dl_kwargs))
        return cls(*dataloaders, path=path, device=device, dl_tfms=dl_tfms, collate_fn=collate_fn, no_check=no_check)

# Cell
class TextList_Multi(TextList):
    _bunch=TextClasDataBunch_Multi

# Cell
class MixedObjectDataBunch(DataBunch):
    pass

# Cell
class MixedObjectLists(ItemLists):
    def __init__(self, path,train: ItemList, valid: ItemList):
        self.path, self.train, self.valid, self.test = path, train, valid, None


    def __repr__(self)->str:
        return f'{self.__class__.__name__};\n\nTrain: {self.train};\n\nValid: {self.valid};\n\nTest: {self.test}'

    def __getattr__(self, k):
        ft = getattr(self.train[0], k)
        if not isinstance(ft, Callable): return ft
        fv = getattr(self.valid[0], k)
        assert isinstance(fv, Callable)
        def _inner(*args, **kwargs):
            self.train = ft(*args, from_item_lists=True, **kwargs)
            assert isinstance(self.train, LabelList)
            kwargs['label_cls'] = self.train.y.__class__
            self.valid = fv(*args, from_item_lists=True, **kwargs)
            self.__class__ = LabelLists_Multi
            self.process()
            return self
        return _inner

    def __setstate__(self,data:Any): self.__dict__.update(data)

    def _label_from_list(self, labels:Iterator, label_cls:Callable=None, from_item_lists:bool=False, **kwargs)->'LabelList':
        "Label `self.items` with `labels`."
        if not from_item_lists:
            raise Exception("Your data isn't split, if you don't want a validation set, please use `split_none`.")
        labels = array(labels, dtype=object)
        label_cls = self.get_label_cls(labels, label_cls=label_cls, **kwargs)
        y = label_cls(labels, path=self.path, **kwargs)
        res = self._label_list(x=self.parent, y=y)
        return res

    def label_from_df(self, *args, **kwargs):
        "Label `self.items` from the values in `cols` in `self.inner_df`."


        for i,o in enumerate(self.train):
            ft = getattr(self.train[i], 'label_from_df')
            fv = getattr(self.valid[i], 'label_from_df')
            self.train[i]=ft(*args, from_item_lists=True, **kwargs)

            kwargs['label_cls'] = self.train[i].y.__class__
            self.valid[i] = fv(*args, from_item_lists=True, **kwargs)

        self.train_y = self.train[0].y
        self.valid_y = self.valid[0].y
        self.__class__ = LabelLists_Multi
        self.process()
        return self

# Cell
class MixedObjectList(ItemList):

    def __init__(self, item_lists):
        self.item_lists = item_lists
        self._label_list, self._split = LabelList_Multi, MixedObjectLists
        self.n = len(item_lists[0])
        self.path = Path('.')
        for i,o in enumerate(self.item_lists):
            item_lists[i].parent_data_group=weakref.ref(self)


    @classmethod
    def from_df(cls, df_list:List[DataFrame], cols_list=None,item_type_list=None, processors=None, **kwargs)->'MixedObjectList':
        res=[]

        for i,df in enumerate(df_list):
            if item_type_list[i] is TabularList_Sample:
                res.append(item_type_list[i].from_df(df, cat_names=cols_list[i], **kwargs))
            else:
                res.append(item_type_list[i].from_df(df, cols=cols_list[i], processor=processors[i], **kwargs))
        return cls(res)

    def split_by_idxs(self, train_idx, valid_idx):
        "Split the data between `train_idx` and `valid_idx`."
        train=[]
        valid=[]
        for i,o in enumerate(self.item_lists):
            self.item_lists[i]=self.item_lists[i].split_by_list(self.item_lists[i][train_idx], self.item_lists[i][valid_idx])
            self.item_lists[i].train.parent_data_group = weakref.ref(self)
            self.item_lists[i].valid.parent_data_group = weakref.ref(self)
            train.append(self.item_lists[i].train)
            valid.append(self.item_lists[i].valid)

        return self._split(self.path, train, valid)

    def split_subsets(self, train_size:float, valid_size:float, seed=None) -> 'MixedObjectLists':
        "Split the items into train set with size `train_size * n` and valid set with size `valid_size * n`."
        assert 0 < train_size < 1
        assert 0 < valid_size < 1
        assert train_size + valid_size <= 1.
        if seed is not None: np.random.seed(seed)
        n = self.n
        rand_idx = np.random.permutation(range(n))
        train_cut, valid_cut = int(train_size * n), int(valid_size * n)
        return self.split_by_idxs(rand_idx[:train_cut], rand_idx[-valid_cut:])

# Cell
class LabelList_Multi(LabelList):
    def __init__(self,parent_data_group,*args,**kwargs):
        self.parent_data_group=parent_data_group
        super().__init__(*args,**kwargs)

# Cell
class LabelLists_Multi(LabelLists):
    _bunch = MixedObjectDataBunch
    def get_processors(self):
        "Read the default class processors if none have been set."
        procs_x,procs_y = [listify(self.train[i].x._processor) for i in range_of(self.train)],listify(self.train[0].y._processor)

        xp = [ifnone(self.train[i].x.processor, [p(ds=self.train[i].x) for p in procs_x[i]]) for i in range_of(self.train)]
        yp = ifnone(self.train_y.processor, [p(ds=self.train_y) for p in procs_y])
        return xp,yp


    def process(self):
        "Process the inner datasets."
        xp, yp = self.get_processors()
        for ds, n in zip(self.lists, ['train', 'valid', 'test']):
            for i,o in enumerate(ds):
                o.process(xp[i], yp, name=n)
        # progress_bar clear the outputs so in some case warnings issued during processing disappear.
        for ds in self.lists:
            for i,o in enumerate(ds):
                if getattr(o, 'warn', False): warn(o.warn)
        return self

    def databunch(self, path:PathOrStr=None, bs:int=64, val_bs:int=None, num_workers:int=defaults.cpus,
                  dl_tfms:Optional[Collection[Callable]]=None, device:torch.device=None, collate_fn:Callable=data_collate,
                  no_check:bool=False,tab_sampler=None, **kwargs)->'DataBunch':
        "Create an `DataBunch` from self, `path` will override `self.path`, `kwargs` are passed to `DataBunch.create`."
        path = Path(ifnone(path, self.path))
        databunchs=[]

        for i,o in enumerate(self.train):
            if self.test is None:
                test_index = None
            else:
                test_index=self.test[i]

            data = o._bunch.create(self.train[i], self.valid[i], test_ds=test_index, path=path, bs=bs, val_bs=val_bs,
                                    num_workers=num_workers, dl_tfms=dl_tfms, device=device, collate_fn=collate_fn,
                                   no_check=no_check, **kwargs)

            if getattr(self, 'normalize', False):#In case a normalization was serialized
                norm = self.normalize
                data.normalize((norm['mean'], norm['std']), do_x=norm['do_x'], do_y=norm['do_y'])
            data.label_list = self
            databunchs.append(data)
        databunchs[0].secondary_bunch=databunchs[1]
        return databunchs[0]

# Cell
class TabularModel_NoCat(Module):
    "Basic model for tabular data."
    def __init__(self, emb_szs:ListSizes, n_cont:int, out_sz:int, layers:Collection[int], ps:Collection[float]=None,
                 emb_drop:float=0., y_range:OptRange=None, use_bn:bool=True, bn_final:bool=False):
        ps = ifnone(ps, [0]*len(layers))
        ps = listify(ps, layers)

        self.emb_drop = nn.Dropout(emb_drop)
        self.bn_cont = nn.BatchNorm1d(n_cont)

        self.embeds = nn.ModuleList([embedding(ni, nf) for ni, nf in emb_szs])
        n_emb = sum(e.embedding_dim for e in self.embeds)


        self.n_emb,self.n_cont,self.y_range = n_emb,n_cont,y_range
        sizes = self.get_sizes(layers, out_sz)
        actns = [nn.ReLU(inplace=True) for _ in range(len(sizes)-2)] + [None]
        layers = []
        for i,(n_in,n_out,dp,act) in enumerate(zip(sizes[:-1],sizes[1:],[0.]+ps,actns)):
            layers += bn_drop_lin(n_in, n_out, bn=use_bn and i!=0, p=dp, actn=act)
        if bn_final: layers.append(nn.BatchNorm1d(sizes[-1]))
        self.layers = nn.Sequential(*layers)

    def get_sizes(self, layers, out_sz):
        return [self.n_emb + self.n_cont] + layers + [out_sz]

    def forward(self, x_cat:Tensor, x_cont:Tensor) -> Tensor:
        if self.n_emb != 0:
            x = [e(x_cat[:,i]) for i,e in enumerate(self.embeds)]
            x = torch.cat(x, 1)
            x = self.emb_drop(x)
        if self.n_cont != 0:
            #x_cont = self.bn_cont(x_cont)
            x = torch.cat([x, x_cont], 1) if self.n_emb != 0 else x_cont
        x = self.layers(x)
        if self.y_range is not None:
            x = (self.y_range[1]-self.y_range[0]) * torch.sigmoid(x) + self.y_range[0]
        return x

# Cell
class CustomTransformerModel(nn.Module):
    def __init__(self, transformer_model_q: PreTrainedModel, transformer_model_a: PreTrainedModel,emb_sizes=None):
        super(CustomTransformerModel,self).__init__()
        self.transformer_q = transformer_model_q
        self.transformer_a = transformer_model_a
        self.classifier = TabularModel_NoCat(emb_sizes,1536, 30,[400],ps=[0.1],use_bn=False)
        self.dropout = torch.nn.Dropout(0.1)

    def forward(self, input_text,input_categorical):
        #pdb.set_trace()

        q_id=input_text[:,0,0,:]
        q_mask=input_text[:,0,1,:]
        q_atn=input_text[:,0,2,:]

        a_id=input_text[:,1,0,:]
        a_mask=input_text[:,1,1,:]
        a_atn=input_text[:,1,2,:]

        logits_q = torch.mean(self.transformer_q(q_id,
                                attention_mask = q_mask, token_type_ids=q_atn)[0] ,dim=1)
        logits_a = torch.mean(self.transformer_a(a_id,
                                attention_mask = a_mask, token_type_ids=a_atn)[0],dim=1)

        output=self.dropout(torch.cat((logits_q, logits_a), dim=1))
        logits=self.classifier(input_categorical[0][0],output)
        #logits = self.classifier(None, output)
        return logits

# Cell
class AvgSpearman(Callback):

    def __init__(self, labels,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.labels=labels

    def on_epoch_begin(self, **kwargs):
        self.preds = np.empty( shape=(0, 200) )
        self.target = np.empty( shape=(0,30) )

    def on_batch_end(self, last_output, last_target, **kwargs):
        self.preds = np.append(self.preds,last_output.cpu(),axis=0)
        self.target = np.append(self.target,last_target.cpu(),axis=0)

    def on_epoch_end(self, last_metrics, **kwargs):
        pos = 0
        spearsum=0.0
        for i in range(self.target.shape[1]):
            column_distinct_size = len(self.labels[i])
            #pdb.set_trace()
            processed_target = self.target[:,i]
            processed_pred = self.preds[:,i]
            #processed_pred = torch.matmul(F.softmax(torch.tensor(self.preds[:,pos:(pos+column_distinct_size)]),1),torch.tensor(self.labels[i]))
            spearsum+=spearmanr(processed_pred,processed_target).correlation
        res = spearsum/self.target.shape[1]
        return add_metrics(last_metrics, res)

# Cell
class AvgSpearman2(Callback):

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)

    def on_epoch_begin(self, **kwargs):
        self.preds = np.empty( shape=(0, 30) )
        self.target = np.empty( shape=(0,30) )

    def on_batch_end(self, last_output, last_target, **kwargs):
        self.preds = np.append(self.preds,last_output.cpu(),axis=0)
        self.target = np.append(self.target,last_target.cpu(),axis=0)

    def on_epoch_end(self, last_metrics, **kwargs):
        pos = 0
        spearsum=0.0
        for i in range(self.target.shape[1]):
            #pdb.set_trace()
            processed_target = self.target[:,i]
            processed_pred = self.preds[:,i]
            #processed_pred = torch.matmul(F.softmax(torch.tensor(self.preds[:,pos:(pos+column_distinct_size)]),1),torch.tensor(self.labels[i]))
            spearnew=spearmanr(processed_pred,processed_target).correlation
            spearsum +=spearnew

        res = spearsum/self.target.shape[1]
        return add_metrics(last_metrics, res)

# Cell
class AddExtraBunch(LearnerCallback):
    def on_epoch_begin(self,**kwargs):
        self.first_batch=True
        self.first_batch_valid=True


    def on_batch_begin(self, last_input, last_target, train, **kwargs):


        "Applies mixup to `last_input` and `last_target` if `train`."
        if train:
            if self.first_batch:
                self.learn.data.secondary_bunch.train_dl.sampler.exact_idxs=self.learn.data.train_dl.sampler.current_idxs
                self.secondary_train_iter = iter(self.learn.data.secondary_bunch.train_dl)

            categorical_input = next(self.secondary_train_iter)
            self.first_batch = False
        else:
            if self.first_batch_valid:
                self.learn.data.secondary_bunch.valid_dl.sampler.exact_idxs = self.learn.data.valid_dl.sampler.current_idxs
                self.secondary_valid_iter = iter(self.learn.data.secondary_bunch.valid_dl)
            categorical_input = next(self.secondary_valid_iter)
            self.first_batch_valid=False
        new_input,new_target=(last_input,categorical_input),last_target
        return {'last_input': new_input, 'last_target': new_target}


# Cell
import pdb
class FlattenedLoss_BWW(FlattenedLoss):
    def __init__(self,unique_sorted_values,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.unique_sorted_values=unique_sorted_values
        self.total_entropy=torch.tensor(0.0).cuda()


    def __call__(self, input:Tensor, target:Tensor, **kwargs)->Rank0Tensor:

        input = input.transpose(self.axis,-1).contiguous()
        target = target.transpose(self.axis,-1).contiguous()
        if self.floatify: target = target.float()
        input = input.view(-1,input.shape[-1]) if self.is_2d else input.view(-1)
        self.total_entropy=0.0
        pos = 0

        for i in range(len(self.unique_sorted_values)):
            labeled_target = torch.empty(target.shape[0], dtype=torch.long).cuda()
            for j in range(len(self.unique_sorted_values[i])):
                labeled_target[(target[:,i]== self.unique_sorted_values[i][j]).nonzero()] = j
                if j==0:
                    occurences = (target[:,i] == self.unique_sorted_values[i][j]).sum(dtype=torch.float).unsqueeze(dim=0)
                else:
                    occurences = torch.cat((occurences,(target[:,i] == self.unique_sorted_values[i][j]).sum(dtype=torch.float).unsqueeze(dim=0)),axis=0)
            new_weights=torch.where(occurences>0.,1/occurences,torch.zeros(occurences.shape).cuda())
            new_weights = new_weights / new_weights.sum()
            self.func.weight = new_weights
            #pdb.set_trace()
            self.total_entropy+=self.func.__call__(input[:,pos:(pos+len(self.unique_sorted_values[i]))],
                                              labeled_target, **kwargs)
            pos+=len(self.unique_sorted_values[i])
        return self.total_entropy/len(self.unique_sorted_values)

# Cell
def CrossEntropyFlat_BWW(unique_sorted_values,*args, axis:int=-1, **kwargs):
    "Same as `nn.CrossEntropyLoss`, but flattens input and target."
    return_loss=FlattenedLoss_BWW(unique_sorted_values,nn.CrossEntropyLoss, *args, axis=axis, **kwargs)
    return return_loss

# Cell
def model_unfreezing_and_training(num_groups,learning_rates,unfreeze_layers,epochs):
    for layer in range(0,num_groups):
        print(layer)
        if layer == num_groups-1:
            learner.unfreeze()
        else:
            learner.freeze_to(unfreeze_layers[layer])

        print('freezing to:',unfreeze_layers[layer],' - ',epochs[layer],'epochs')
        learner.fit_one_cycle(epochs[layer],
                              max_lr=slice(learning_rates[layer]*0.95**num_groups, learning_rates[layer]),
                              moms=(0.8, 0.9))

# Cell
def get_preds_as_nparray(ds_type,unique_sorted_values,databunch)  -> np.ndarray:
    """
    the get_preds method does not yield the elements in order by default
    we borrow the code from the RNNLearner to resort the elements into their correct order
    """
    preds = learner.get_preds(ds_type)[0].detach().cpu().numpy()
    pos =0
    processed_pred=torch.empty(preds.shape[0],30)
    for j in range(len(unique_sorted_values)):
        column_distinct_size = len(unique_sorted_values[j])
        #processed_pred = self.labels[torch.argmax(torch.tensor(self.preds),1)]
        processed_pred[:,j] = torch.matmul(F.softmax(torch.tensor(preds[:,pos:(pos+column_distinct_size)]),1),
                                        torch.tensor(unique_sorted_values[j],dtype=torch.float))
        pos+=column_distinct_size
    processed_pred=processed_pred.numpy()
    sampler = [i for i in databunch.dl(ds_type).sampler]
    reverse_sampler = np.argsort(sampler)
    return processed_pred[reverse_sampler, :]
