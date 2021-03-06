# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

"""
Clone GenSen repo here: https://github.com/Maluuba/gensen.git
And follow instructions for loading the model used in batcher
"""

from __future__ import absolute_import, division, unicode_literals

import sys
import logging
# import GenSen package
from gensen import GenSen, GenSenSingle
import gensen
import numpy as np




# Set PATHs
PATH_TO_SENTEVAL = '../'
PATH_TO_DATA = '../data'
PATH_TO_VEC = 'fasttext/crawl-300d-2M.vec'

# import SentEval
sys.path.insert(0, PATH_TO_SENTEVAL)
import senteval
sys.path.insert(1,PATH_TO_SENTEVAL)
from AdversarialModels import WordNetSynonym
import io

def get_sentence(sentence):
    sent = ""
    for word in sentence:
        sent+=word+" "
    return sent


def create_dictionary(sentences, threshold=0):
    words = {}
    for s in sentences:
        for word in s:
            words[word] = words.get(word, 0) + 1

    if threshold > 0:
        newwords = {}
        for word in words:
            if words[word] >= threshold:
                newwords[word] = words[word]
        words = newwords
    words['<s>'] = 1e9 + 4
    words['</s>'] = 1e9 + 3
    words['<p>'] = 1e9 + 2

    sorted_words = sorted(words.items(), key=lambda x: -x[1])  # inverse sort
    id2word = []
    word2id = {}
    for i, (w, _) in enumerate(sorted_words):
        id2word.append(w)
        word2id[w] = i

    return id2word, word2id

# SentEval prepare and batcher
def prepare(params, samples):
    _, params.word2id = create_dictionary(samples)
    params.word_vec = get_wordvec(PATH_TO_VEC, params.word2id)
    params.wvec_dim = 300
    return

def get_wordvec(path_to_vec, word2id):
    word_vec = {}

    with io.open(path_to_vec, 'r', encoding='utf-8') as f:
        # if word2vec or fasttext file : skip first line "next(f)"
        for line in f:
            word, vec = line.split(' ', 1)
            if word in word2id:
                word_vec[word] = np.fromstring(vec, sep=' ')

    logging.info('Found {0} words with word vectors, out of \
        {1} words'.format(len(word_vec), len(word2id)))
    return word_vec

def batcher(params, batch):
    batch = [' '.join(sent) if sent != [] else '.' for sent in batch]
    _, reps_h_t = gensen_encoder.get_representation(
        batch, pool='last', return_numpy=True, tokenize=True
    )
    embeddings = reps_h_t
    return embeddings


def prepare_adversarial_samples(params, sentences, y_labels):

    new_sentences = []
    new_labels = []

    for sent, label in zip(sentences, y_labels):
        sent_adversaries = []
        sent_adv_labels = []
        new_sent = list(sent)
        sent_adversaries.append(new_sent)
        sent_adv_labels.append(label)

        new_sent = list(sent)
        sent_adversaries.append(new_sent)
        sent_adv_labels.append(label)

        # if sent == sentences[43]:
        #     print("orig sent vec", get_sentence(sent), " ,label:", label)
        #     print("mod sent vec", get_sentence(new_sent))


        for word, word_pos in zip(sent, range(len(sent))):
            # print "new word ", word, "-" *80
            if word in params.word_vec:
                # print word, "-" * 30
                # print params.word_vec[word][:20]
                new_sent = list(sent)
                # print "new sent vec ", "-" * 30
                # print new_sentvec[:20]
                word_syns = WordNetSynonym.get_word_synonym(word)

                # print word_syns
                for syn in word_syns:
                    if syn in params.word_vec:

                        if syn == word:
                            continue

                        # print syn, "-"*30
                        # print params.word_vec[syn][:20]
                        new_sent = list(sent)
                        new_sent[word_pos] = syn
                        sent_adversaries.append(new_sent)
                        sent_adv_labels.append(label)

                        # if sent == sentences[43]:
                        #     print("mod sent vec", get_sentence(new_sent))

                        # print "mod sent vec", "-" * 30
                        # print modified_vecs[len(modified_vecs)-1][:20], "\n"
        new_sentences.append(sent_adversaries)
        new_labels.append(sent_adv_labels)


    return new_sentences, new_labels



def adversarialFunc(params, batch_sentences, batch_labels, embeddings = None):
    # sentvec = np.multiply(sentvec, params.wvec_dim)


    adv_batch_sentences, adv_labels = prepare_adversarial_samples(params, batch_sentences, batch_labels)

    print("adv samples size %d",len(adv_batch_sentences))

    total_count = sum(len(x) for x in adv_batch_sentences)
    print("sum of sentences called %d, batch_size %d" %(total_count, params.batch_size))

    adv_embeddings = []

    for sent_adversaries, i in zip(adv_batch_sentences, range(len(adv_batch_sentences))):

        sentences = [' '.join(sent) if sent != [] else '.' for sent in sent_adversaries]
        _, reps_h_t = gensen_encoder.get_representation(
            sentences, pool='last', return_numpy=True, tokenize=True
        )
        sent_adv_embeddings = reps_h_t

        # sent_adv_embeddings = params.infersent.encode_without_shuffle(sentences, bsize=params.batch_size, tokenize=False)
        adv_embeddings.append(sent_adv_embeddings)

        if i%10 == 0:
            print("%d sentences done"%(i))
            # print("Adv embeddings shape: %s, adv_labels shape", len(sent_adv_embeddings), dim(adv_labels[i]))

    print("Adv embeddings shape: %s, adv_labels shape %s" %(len(adv_embeddings), len(adv_labels)))

    for i in range(0,len(adv_embeddings),10):
        print("Adv embeddings shape: %s, adv_labels shape", len(adv_embeddings[i]), len(adv_labels[i]))
    return adv_embeddings, adv_labels, adv_batch_sentences




# Load GenSen model
gensen_1 = GenSenSingle(
    model_folder='../data/models',
    filename_prefix='nli_large_bothskip',
    pretrained_emb='fasttext/glove.840B.300d.h5'
)
gensen_2 = GenSenSingle(
    model_folder='../data/models',
    filename_prefix='nli_large_bothskip_parse',
    pretrained_emb='fasttext/glove.840B.300d.h5'
)
gensen_encoder = GenSen(gensen_1, gensen_2)



# reps_h, reps_h_t = gensen_encoder.get_representation(
#     sentences, pool='last', return_numpy=True, tokenize=True
# )

# Set params for SentEval
params_senteval = {'task_path': PATH_TO_DATA, 'usepytorch': True, 'kfold': 5, 'model_name': 'gensen','batch_size': 128}
params_senteval['classifier'] = {'nhid': 0, 'optim': 'rmsprop', 'batch_size': 128,
                                 'tenacity': 3, 'epoch_size': 2, 'cudaEfficient' : True}
params_senteval['gensen'] = gensen_encoder


# Set up logger
logging.basicConfig(format='%(asctime)s : %(message)s', level=logging.DEBUG, adversarialFunc=adversarialFunc)

if __name__ == "__main__":
    se = senteval.engine.SE(params_senteval, batcher, prepare, adversarialFunc=adversarialFunc)
    # transfer_tasks = ['STS12', 'STS13', 'STS14', 'STS15', 'STS16',
                      # 'MR', 'CR', 'MPQA', 'SUBJ', 'SST2', 'SST5', 'TREC', 'MRPC',
                      # 'SICKEntailment', 'SICKRelatedness', 'STSBenchmark',
                      # 'Length', 'WordContent', 'Depth', 'TopConstituents',
                      # 'BigramShift', 'Tense', 'SubjNumber', 'ObjNumber',
                      # 'OddManOut', 'CoordinationInversion']
    transfer_tasks = ['STSBenchmark']
    results = se.eval(transfer_tasks)
    # print(results)
