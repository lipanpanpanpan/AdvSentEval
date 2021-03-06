# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

"""
Validation and classification
(train)            :  inner-kfold classifier
(train, test)      :  kfold classifier
(train, dev, test) :  split classifier

"""
from __future__ import absolute_import, division, unicode_literals

import logging
import numpy as np
from senteval.tools.classifier import MLP

import sklearn
import pickle
assert(sklearn.__version__ >= "0.18.0"), \
    "need to update sklearn to version >= 0.18.0"
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold


def get_classif_name(classifier_config, usepytorch, ):
    if not usepytorch:
        modelname = 'sklearn-LogReg'
    else:
        nhid = classifier_config['nhid']
        optim = 'adam' if 'optim' not in classifier_config else classifier_config['optim']
        bs = 64 if 'batch_size' not in classifier_config else classifier_config['batch_size']
        modelname = 'pytorch-MLP-nhid%s-%s-bs%s' % (nhid, optim, bs)
    return modelname

def get_sentence(sentence):
    sent = ""
    for word in sentence:
        sent+=word+" "
    return sent

# def model_file_name(params, classifier_config, task_name):
#
#     model_name =

# Pytorch version
class InnerKFoldClassifier(object):
    """
    (train) split classifier : InnerKfold.
    """
    def __init__(self, X, y, config):
        self.X = X
        self.y = y
        self.featdim = X.shape[1]
        self.nclasses = config['nclasses']
        self.seed = config['seed']
        self.devresults = []
        self.testresults = []
        self.usepytorch = config['usepytorch']
        self.classifier_config = config['classifier']
        self.modelname = get_classif_name(self.classifier_config, self.usepytorch)

        self.k = 5 if 'kfold' not in config else config['kfold']

    def run(self):
        logging.info('Training {0} with (inner) {1}-fold cross-validation'
                     .format(self.modelname, self.k))

        regs = [10**t for t in range(-5, -1)] if self.usepytorch else \
               [2**t for t in range(-2, 4, 1)]
        skf = StratifiedKFold(n_splits=self.k, shuffle=True, random_state=1111)
        innerskf = StratifiedKFold(n_splits=self.k, shuffle=True,
                                   random_state=1111)
        count = 0
        for train_idx, test_idx in skf.split(self.X, self.y):
            count += 1
            X_train, X_test = self.X[train_idx], self.X[test_idx]
            y_train, y_test = self.y[train_idx], self.y[test_idx]
            scores = []
            for reg in regs:
                regscores = []
                for inner_train_idx, inner_test_idx in innerskf.split(X_train, y_train):
                    X_in_train, X_in_test = X_train[inner_train_idx], X_train[inner_test_idx]
                    y_in_train, y_in_test = y_train[inner_train_idx], y_train[inner_test_idx]
                    if self.usepytorch:
                        clf = MLP(self.classifier_config, inputdim=self.featdim,
                                  nclasses=self.nclasses, l2reg=reg,
                                  seed=self.seed)
                        clf.fit(X_in_train, y_in_train,
                                validation_data=(X_in_test, y_in_test))
                    else:
                        clf = LogisticRegression(C=reg, random_state=self.seed)
                        clf.fit(X_in_train, y_in_train)
                    regscores.append(clf.score(X_in_test, y_in_test))
                scores.append(round(100*np.mean(regscores), 2))
            optreg = regs[np.argmax(scores)]
            logging.info('Best param found at split {0}: l2reg = {1} \
                with score {2}'.format(count, optreg, np.max(scores)))
            self.devresults.append(np.max(scores))

            if self.usepytorch:
                clf = MLP(self.classifier_config, inputdim=self.featdim,
                          nclasses=self.nclasses, l2reg=optreg,
                          seed=self.seed)

                clf.fit(X_train, y_train, validation_split=0.05)
            else:
                clf = LogisticRegression(C=optreg, random_state=self.seed)
                clf.fit(X_train, y_train)

            self.testresults.append(round(100*clf.score(X_test, y_test), 2))

        devaccuracy = round(np.mean(self.devresults), 2)
        testaccuracy = round(np.mean(self.testresults), 2)
        return devaccuracy, testaccuracy


class KFoldClassifier(object):
    """
    (train, test) split classifier : cross-validation on train.
    """
    def __init__(self, train, test, config, test_dataX = None, test_dataY = None):
        self.train = train
        self.test = test
        self.featdim = self.train['X'].shape[1]
        self.nclasses = config['nclasses']
        self.seed = config['seed']
        self.usepytorch = config['usepytorch']
        self.classifier_config = config['classifier']
        self.modelname = get_classif_name(self.classifier_config, self.usepytorch)

        self.k = 5 if 'kfold' not in config else config['kfold']
        self.config = config
        self.test_dataX = test_dataX if test_dataX is not None else None
        self.test_dataY = test_dataY if test_dataY is not None else None


    def run(self, params):
        # cross-validation
        logging.info('Training {0} with {1}-fold cross-validation'
                     .format(self.modelname, self.k))
        regs = [10**t for t in range(-5, -1)] if self.usepytorch else \
               [2**t for t in range(-1, 6, 1)]
        skf = StratifiedKFold(n_splits=self.k, shuffle=True,
                              random_state=self.seed)
        scores = []
        filename = 'models/finalized_model_' + params.model_name + '_' + params.task_name + '_.sav'
        devaccuracy = 0

        # for reg in regs:
        #     scanscores = []
        #     for train_idx, test_idx in skf.split(self.train['X'],
        #                                          self.train['y']):
        #         # Split data
        #         X_train, y_train = self.train['X'][train_idx], self.train['y'][train_idx]
        #
        #         X_test, y_test = self.train['X'][test_idx], self.train['y'][test_idx]
        #
        #         # Train classifier
        #         if self.usepytorch:
        #             clf = MLP(self.classifier_config, inputdim=self.featdim,
        #                       nclasses=self.nclasses, l2reg=reg,
        #                       seed=self.seed)
        #             clf.fit(X_train, y_train, validation_data=(X_test, y_test))
        #         else:
        #             clf = LogisticRegression(C=reg, random_state=self.seed)
        #             clf.fit(X_train, y_train)
        #         score = clf.score(X_test, y_test)
        #         scanscores.append(score)
        #     # Append mean score
        #     scores.append(round(100*np.mean(scanscores), 2))
        #
        # # evaluation
        # logging.info([('reg:' + str(regs[idx]), scores[idx])
        #               for idx in range(len(scores))])
        # optreg = regs[np.argmax(scores)]
        # devaccuracy = np.max(scores)
        # logging.info('Cross-validation : best param found is reg = {0} \
        #     with score {1}'.format(optreg, devaccuracy))
        #
        # logging.info('Evaluating...')
        # if self.usepytorch:
        #     clf = MLP(self.classifier_config, inputdim=self.featdim,
        #               nclasses=self.nclasses, l2reg=optreg,
        #               seed=self.seed)
        #     clf.fit(self.train['X'], self.train['y'], validation_split=0.05)
        # else:
        #     clf = LogisticRegression(C=optreg, random_state=self.seed)
        #     clf.fit(self.train['X'], self.train['y'])
        #
        # pickle.dump(clf, open(filename, 'wb'))

        orig_test_x = self.test['X']
        orig_test_y = self.test['y']


        total_adversaries = []
        uneq_adversaries = []
        wrong_adversaries = []
        adv_results = dict()
        orig_predictions = []
        clf = pickle.load(open(filename, 'rb'))


        testaccuracy = clf.score(self.test['X'], self.test['y'])
        testaccuracy = round(100*testaccuracy, 2)
        yhat = clf.predict(self.test['X'])

        wrong_first = 0
        test_preds = clf.predict(self.test['X'])
        for test_pred, i in zip(test_preds, range(len(test_preds))):
            if test_pred != self.test['y'][i]:
                wrong_first += 1
        print("test wrong cases:", wrong_first)


        #
        #
        allowed_error = 0.00001
        change_due_to_randomness = 0
        wrong_first = 0
        label_diff_count = 0
        if self.config['adversarial_sample_generator'] is not None:
            batcher = self.config['batcher'] if self.config['batcher'] is not None else None
            adv_embed_x, adv_embed_y, adv_sentences = self.config['adversarial_sample_generator'](self.test['X'],self.test['y'], batcher = batcher)

            adv_preds = []
            for i in range(len(adv_embed_x)):
                orig_pred = clf.predict(self.test['X'][i].reshape(1, -1))
                # print("orig test vector shape ", self.test['X'].shape, "embedding vector shape " , len(adv_embed_x), len(adv_embed_x[0]))
                orig_predictions.append(orig_pred)
                sample_preds = np.vstack(clf.predict(adv_embed_x[i]))

                adv_preds.append(sample_preds)
                wrong_count = 0
                change_count = 0

                if i == 10:
                    print(get_sentence(adv_sentences[i][0]))
                    print("orig predcitions", adv_embed_y[i])
                    # print("new predictions", sample_preds)
                    print("orig embeddings", self.test['X'][i])
                    print("new embeddings", adv_embed_x[i][0])


                if sample_preds[0] != sample_preds[1]:
                    change_due_to_randomness += 1
                    print("predictions are not equal for the sentence %d" % (i))
                # orig_pred = sample_preds[0]

                if sample_preds[0] != adv_embed_y[i][0]:
                    wrong_first += 1
                    # print("predictions are wrong for the sentence %d"%(i))

                if self.test['y'][i] != adv_embed_y[i][0]:
                    label_diff_count += 1

                equal = True
                no_of_dim_diff = 0
                for j in range(len(adv_embed_x[i][0])):
                    if abs(adv_embed_x[i][0][j] - adv_embed_x[i][1][j]) >= allowed_error:
                        equal = False
                        no_of_dim_diff += 1

                # if equal == False:
                #     print("\nembeddings are not equal for the sentence %d, no of dims different %d" % (i, no_of_dim_diff))
                #     print("orig embeddings", self.test['X'][i])
                #     print("new embeddings\n", adv_embed_x[i][0])

                indexes_to_print = {4, 12, 15, 17, 18, 26, 36, 43, 48, 52, 56, 59, 63, 67, 69, 72, 76, 79, 83, 88}
                success_attack = False
                wrong_indexes = []
                for sample_pred, ind in zip(sample_preds, range(len(sample_preds))):

                    if sample_pred != adv_embed_y[i][0]:
                        # print("")
                        wrong_count += 1
                    if sample_pred != sample_preds[0]:
                        success_attack = True
                        wrong_indexes.append(ind)
                        change_count += 1

                if success_attack and self.test_dataX is not None and self.test_dataY is not None:
                    if i in indexes_to_print:
                        print(self.get_sentence(adv_sentences[i][0]), sample_preds[0], len(adv_embed_x[i]))
                        print(self.get_sentence(adv_sentences[i][1]), sample_preds[1], len(adv_sentences[i]))
                        for wrong_index in wrong_indexes:
                            print(self.get_sentence(adv_sentences[i][wrong_index]), sample_preds[wrong_index])

                    # if i%10 == 0:

                uneq_adversaries.append(change_count)
                wrong_adversaries.append(wrong_count)
                total_adversaries.append(len(sample_preds))
                # print sample_preds, adv_embed_y[i]
                if i % 100 == 0:
                    print("%d sentences evaluated" % i)

            print("wring first count:%d" % (wrong_first))
            print("change due to randomness count:%d" % (change_due_to_randomness))
            print("non equal count:%d" % (np.count_nonzero(uneq_adversaries)))
            print("wrong count:%d" % (np.count_nonzero(wrong_adversaries)))
            print("total count:%d" % (len(adv_embed_x)))
            # print uneq_adversaries[:-10], total_adversaries[:-10]
            print("adversaries size:%d" % (np.sum(total_adversaries)))

            adv_results['total_adversaries'] = total_adversaries
            adv_results['wrong_adversaries'] = wrong_adversaries
            adv_results['uneq_adversaries'] = uneq_adversaries
            adv_results['model'] = clf
            adv_results['test_x'] = self.test['X']
            adv_results['test_y'] = self.test['y']
            adv_results['adv_test_x'] = adv_embed_x
            adv_results['adv_test_y'] = adv_embed_y
            adv_results['adv_preds'] = adv_preds
            adv_results['orig_predictions'] = orig_predictions
        else:
            print("No adversarial attacks specified")

        return devaccuracy, testaccuracy, yhat


class SplitClassifier(object):
    """
    (train, valid, test) split classifier.
    """
    def __init__(self, X, y, config, test_dataX = None, test_dataY = None):
        self.X = X
        self.y = y
        self.nclasses = config['nclasses']

        self.featdim = self.X['test'].shape[1]
        self.seed = config['seed']
        self.usepytorch = config['usepytorch']
        self.classifier_config = config['classifier']
        self.cudaEfficient = False if 'cudaEfficient' not in config else \
            config['cudaEfficient']
        self.modelname = get_classif_name(self.classifier_config, self.usepytorch)
        self.noreg = False if 'noreg' not in config else config['noreg']
        self.config = config
        self.test_dataX = test_dataX if test_dataX is not None else None
        self.test_dataY = test_dataY if test_dataY is not None else None

    def get_sentence(self, sentence):
        sent = ""
        for word in sentence:
            sent+=word+" "
        return sent


    def run(self, params):

        # if self.config['adversarial_sample_generator'] is not  None :
        #     adv_embed_x, adv_embed_y = self.config['adversarial_sample_generator'](self.X['test'], self.y['test'])
        # else:
        #     print("No adversarial attacks specified")

        filename = 'models/finalized_model_' + params.model_name + '_' + params.task_name + '_.sav'
        devaccuracy = 0

        # logging.info('Training {0} with standard validation..'
        #              .format(self.modelname))
        # regs = [10**t for t in range(-5, -1)] if self.usepytorch else \
        #        [2**t for t in range(-2, 4, 1)]
        # if self.noreg:
        #     regs = [1e-9 if self.usepytorch else 1e9]
        # scores = []
        # for reg in regs:
        #     if self.usepytorch:
        #         clf = MLP(self.classifier_config, inputdim=self.featdim,
        #                   nclasses=self.nclasses, l2reg=reg,
        #                   seed=self.seed, cudaEfficient=self.cudaEfficient)
        #
        #         # TODO: Find a hack for reducing nb epoches in SNLI
        #         clf.fit(self.X['train'], self.y['train'],
        #                 validation_data=(self.X['valid'], self.y['valid']))
        #     else:
        #         clf = LogisticRegression(C=reg, random_state=self.seed)
        #         clf.fit(self.X['train'], self.y['train'])
        #     scores.append(round(100*clf.score(self.X['valid'],
        #                         self.y['valid']), 2))
        # logging.info([('reg:'+str(regs[idx]), scores[idx])
        #               for idx in range(len(scores))])
        # optreg = regs[np.argmax(scores)]
        # devaccuracy = np.max(scores)
        # logging.info('Validation : best param found is reg = {0} with score \
        #     {1}'.format(optreg, devaccuracy))
        # clf = LogisticRegression(C=optreg, random_state=self.seed)
        # logging.info('Evaluating...')
        # if self.usepytorch:
        #     clf = MLP(self.classifier_config, inputdim=self.featdim,
        #               nclasses=self.nclasses, l2reg=optreg,
        #               seed=self.seed, cudaEfficient=self.cudaEfficient)
        #
        #     # TODO: Find a hack for reducing nb epoches in SNLI
        #     clf.fit(self.X['train'], self.y['train'],
        #             validation_data=(self.X['valid'], self.y['valid']))
        # else:
        #     clf = LogisticRegression(C=optreg, random_state=self.seed)
        #     clf.fit(self.X['train'], self.y['train'])
        #
        #
        # pickle.dump(clf, open(filename, 'wb'))


        orig_test_x = self.X['test']
        orig_test_y = self.y['test']
        total_adversaries = []
        uneq_adversaries = []
        wrong_adversaries = []
        adv_results = dict()
        orig_predictions = []
        logging.info("Loading model from file")
        clf = pickle.load(open(filename, 'rb'))
        logging.info("Loaded model from file")

        testaccuracy = clf.score(self.X['test'], self.y['test'])
        testaccuracy = round(100*testaccuracy, 2)
        print('devacc: ' + str(devaccuracy) + ' acc: ' + str(testaccuracy) +
                ' ndev: ' + str(len(self.X['train'])) +
                ' ntest: ' + str(len(self.X['test'])))
        #
        wrong_first = 0
        test_preds = clf.predict(self.X['test'])
        for test_pred, i in zip(test_preds, range(len(test_preds))):
            if test_pred != self.y['test'][i]:
                wrong_first += 1
        print("test wrong cases:", wrong_first)


        allowed_error = 0.00001
        change_due_to_randomness = 0
        wrong_first = 0
        label_diff_count = 0
        if self.config['adversarial_sample_generator'] is not  None :
            adv_embed_x, adv_embed_y, adv_sentences = self.config['adversarial_sample_generator'](self.X['test'], self.y['test'])
            adv_preds = []
            for i in range(len(adv_embed_x)):
                orig_pred = clf.predict(self.X['test'][i].reshape(1, -1))
                orig_predictions.append(orig_pred)
                sample_preds = clf.predict(adv_embed_x[i])
                adv_preds.append(sample_preds)
                wrong_count =0
                change_count = 0

                if i == 10:
                    print(self.get_sentence(adv_sentences[i][0]))
                    print("orig predcitions", adv_embed_y[i])
                    print("new predictions", sample_preds)
                    print("orig embeddings", self.X['test'][i])
                    print("new embeddings", adv_embed_x[i][0])


                if sample_preds[0] != sample_preds[1]:
                    change_due_to_randomness += 1
                    print("predictions are not equal for the sentence %d"%(i))
                # orig_pred = sample_preds[0]

                if sample_preds[0] != adv_embed_y[i][0]:
                    wrong_first += 1
                    
                if self.y['test'][i] != adv_embed_y[i][0]:
                    label_diff_count += 1
                    # print("predictions are wrong for the sentence %d"%(i))

                equal = True
                no_of_dim_diff = 0
                for j in range(len(adv_embed_x[i][0])):
                    if abs(adv_embed_x[i][0][j] - adv_embed_x[i][1][j]) >= allowed_error:
                        equal = False
                        no_of_dim_diff += 1

                # if equal == False:
                #     print("\nembeddings are not equal for the sentence %d, no of dims different %d" % (i, no_of_dim_diff))
                #     print("orig embeddings", self.X['test'][i])
                #     print("new embeddings\n", adv_embed_x[i][0])

                indexes_to_print = {4,12,15,17,18,26,36,43,48,52,56,59,63,67,69,72,76,79,83,88}
                success_attack = False
                wrong_indexes = []
                for sample_pred, ind in zip(sample_preds, range(len(sample_preds))):


                    if sample_pred !=adv_embed_y[i][0]:
                        # print("")
                        wrong_count+= 1
                    if sample_pred !=sample_preds[0]:
                        success_attack = True
                        wrong_indexes.append(ind)
                        change_count+=1

                if success_attack and self.test_dataX is not None and self.test_dataY is not None:
                    if i in indexes_to_print:
                        print( self.get_sentence(adv_sentences[i][0]), sample_preds[0], len(adv_embed_x[i]))
                        print( self.get_sentence(adv_sentences[i][1]), sample_preds[1], len(adv_sentences[i]))
                        for wrong_index in wrong_indexes:
                            print( self.get_sentence(adv_sentences[i][wrong_index]), sample_preds[wrong_index])


                    # if i%10 == 0:





                uneq_adversaries.append(change_count)
                wrong_adversaries.append(wrong_count)
                total_adversaries.append(len(sample_preds))
                # print sample_preds, adv_embed_y[i]
                if i % 100 == 0:
                    print("%d sentences evaluated"%i)

            print("label diff count:%d" % (label_diff_count))
            print("wring first count:%d" % (wrong_first))
            print("change due to randomness count:%d" % (change_due_to_randomness))
            print("non equal count:%d"%(np.count_nonzero(uneq_adversaries)))
            print("wrong count:%d"%(np.count_nonzero(wrong_adversaries)))
            print("total count:%d" % (len(adv_embed_x)))
            # print uneq_adversaries[:-10], total_adversaries[:-10]
            print("adversaries size:%d" %(np.sum(total_adversaries)))

            adv_results['total_adversaries'] = total_adversaries
            adv_results['wrong_adversaries'] = wrong_adversaries
            adv_results['uneq_adversaries'] = uneq_adversaries
            adv_results['model'] = clf
            adv_results['test_x'] = self.X['test']
            adv_results['test_y'] = self.y['test']
            adv_results['adv_test_x'] = adv_embed_x
            adv_results['adv_test_y'] = adv_embed_y
            adv_results['adv_preds'] = adv_preds
            adv_results['orig_predictions'] = orig_predictions
        else:
            print("No adversarial attacks specified")



        return devaccuracy, testaccuracy, adv_results
