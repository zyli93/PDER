"""
    Data Loader

    the class of loading data

    author: Zeyu Li <zyli@cs.ucla.edu> or <zeyuli@g.ucla.edu>

"""

import numpy as np
import os, sys

import gensim

data_index = 0

class DataLoader():
    def __init__(self, dataset):
        print("Initializing data_loader ...", end=" ")
        self.dataset = dataset
        self.mpfile = os.getcwd() + "/metapath/"+ self.dataset +".txt"
        self.datadir = os.getcwd() + "/data/parsed/" + self.dataset + "/"

        data = self.__read_data()
        self.train_data = data
        self.count = self.__count_dataset(data)
        self.sample_table = self.__init_sample_table()
        self.w2vmodel = self.__load_word2vec()  # **Time Consuming!**
        self.qid2sen = self.__load_questions()

        self.uid2ind, self.ind2uid = {}, {}
        self.user_count = self.__create_uid_index()

        self.process = True  # TODO: process manufacturing

        print("Done!")

    def __read_data(self):
        """
        Read metapath dataset,
            load the dataset into data

        Return:
            data  -  the metapath dataset
        """
        with open(self.mpfile, "r") as fin:
            lines = fin.readlines()
            data = [line.strip().split(" ") for line in lines]
            return data

    def __count_dataset(self, data):
        """
        Read dataset and count the frequency

        Args:
            data  -  the list of meta-pathes.
        Returns:
            count  - the sorted list of
        """
        count_dict = {}
        for path in data:
            for entity in path:
                count_dict[entity] = count_dict.get(entity, 0) + 1

        # keys: entity id, values: count
        count = list(zip(count_dict.keys(), count_dict.values()))
        count.sort(key=lambda x:x[1], reverse=True)
        return count

    def __init_sample_table(self):
        """
        Create sample tables by P()^(3/4)

        Return:
            (sample_table)  -  the created sample table
        """
        count = [ele[1] for ele in self.count]
        pow_freq = np.array(count) ** 0.75
        ratio = pow_freq / sum(pow_freq)
        table_size = 1e8 # TODO: what is this???
        count = np.round(ratio * table_size)
        sample_table = []

        for i in range(len(self.count)):
            sample_table += [self.count[i][0]] * count[i]
        return np.array(sample_table)

    def generate_batch(self, window_size, batch_size, neg_ratio):
        """
        Get batch from the meta paths for the training of skip-gram
            model.

        Args:
            window_size  -  the size of sliding window. In following case,
                            the window size is 2. "_ _ [ ] _ _"
            batch_size   -  how many meta-paths compose a batch
            neg_ratio    -  the ratio of negative samples w.r.t.
                            the positive samples
        Return:
            upos         -  the u vector positions (1D Tensor)
            vpos         -  the v vector positions (1D Tensor)
            npos         -  the negative samples positions (2D Tensor)
        """
        data = self.train_data
        global data_index
        pairs_list = []

        batch = batch_size if batch_size + data_index < len(data) \
            else len(data) - data_index

        for i in range(batch):
            pairs = self.__slide_through(data_index, window_size)
            if data_index + 1 < len(data):
                data_index += 1
            else:  # Meet the end of the dataset
                self.process = False
                break
            pairs_list += pairs

        u, v = zip(*pairs_list)
        upos = self.__separate_entity(u)
        vpos = self.__separate_entity(v)

        npairs_in_batch = len(pairs_list)
        neg_samples = np.random.choice(self.sample_table,
                                       size=(npairs_in_batch * 2 * window_size,
                                             npairs_in_batch * neg_ratio))
        # TODO: check the size of neg_samples
        npos = self.__separate_entity(neg_samples)
        return upos, vpos, npos

    def __separate_entity(self, items):
        """
        Change a list from "A_1 Q_2 R_1 Q_2" to three vectors
            A: 1 0 0 0
            Q: 0 2 0 2
            R: 0 0 1 0

        Args:
            items  -  the list of items

        Return:
            three dimensional matrix representing above matrix
        """
        D = {"A":0, "Q":1, "R":2}
        sep = np.zeros(shape=(3, len(items)))
        for index, item in enumerate(items):
            split = item.split("_")
            ent_type, ent_id = D[split[0]], int(split[1])
            sep[ent_type][index] = ent_id
        return sep

    def __slide_through(self, ind, window_size):
        """
        Sliding through one span, generate all pairs in it

        Args:
            ind  -  the index of the label entity
            window_size  -  the window_size of context
        Return:
            the pair list
        """
        meta_path = self.train_data[ind]
        pairs = []
        for pos, token in enumerate(meta_path):
            lcontext, rcontext = [], []
            lcontext = meta_path[pos - window_size: pos] \
                if pos - window_size >= 0 \
                else meta_path[:pos]

            if pos + 1 < len(meta_path):
                rcontext = meta_path[pos + 1 : pos + window_size] \
                    if pos + window_size < len(meta_path) \
                    else meta_path[pos + 1 :]

            context_pairs = [[token, context]
                             for context in lcontext + rcontext]
            pairs += context_pairs
        return pairs

    def qid2vecs(self, qid):
        """
        Given Qid, return the concatenated word vectors

        Args:
            qid  -  the qid

        Return:
            qvec  -  the vector of the question, numpy.ndarray
        """
        question = self.qid2sen[qid]
        qvecs = self.w2vmodel[question.strip().split(" ")]
        # l, qvec = self.sen2vecs(sentence=question)
        return qvecs

    def sen2vecs(self, sentence):
        """
        ** [NOT in USE] **
        Convert sentence to concatenate of word-vectors

        Arg:
            sentence  -  str, the sentence to convert

        Return:
            (np.array)  -  the array contains the word vectors
        """
        sentence = sentence.split(" ")
        vectors = [self.w2vmodel[w] for w in sentence]
        return len(sentence), np.array(vectors)

    def __load_word2vec(self):
        """
        Loading word2vec model, return the model

        Return:
            model  -  dictionary, ("word", [word-vector]),
                      loaded word2vec model
        """
        PATH = os.getcwd() + "/word2vec_model/" +\
                "GoogleNews-vectors-negative300.bin"
        model = gensim.models.KeyedVectors.load_word2vec_format(
            fname=PATH, binary=True)
        return model

    def __load_questions(self):
        """
        Load question from dataset, "title" + "content",
            construct the qid2sen dictionary

        Return:
            qid2sen  -  the qid:question dictionary
        """

        qcfile = self.datadir + "Q_content_nsw.txt"
        qtfile = self.datadir + "Q_title_nsw.txt"

        qid2sen = {}

        with open(qtfile, "r") as fin_t:
            lines = fin_t.readlines()
            for line in lines:
                id, title = line.split(" ", 1)
                qid2sen[id] = title.strip()

        with open(qcfile, "r") as fin_c:
            lines = fin_c.readlines()
            for line in lines:
                id, content = line.split(" ", 1)
                qid2sen[id] += " " + content.strip()

        return qid2sen

    def __create_uid_index(self):
        """
        Create a uid-index map and index-uid map

        Return:
            uid2ind  -  User id to Index dictionary
            ind2uid  -  Index to User id dictionary
            len(lines)  -  How many users are there in the network
        """
        uid_file = self.datadir + "part_users.txt"
        self.uid2ind[0] = 0
        self.ind2uid[0] = 0
        with open(uid_file, "r") as fin:
            lines = fin.readlines()
            for ind, line in enumerate(lines):
                uid = int(line.strip())
                self.uid2ind[uid] = ind
                self.ind2uid[ind] = uid
            return len(lines)

    def single_uid2index(self, uid):
        return self.uid2ind[uid]

    def single_index2uid(self, index):
        return self.ind2uid[index]

    def uid2index(self, vec):
        """
        User ID representation to user Index representation

        Args:
            vec  -  the np.array to work with
        Return:
            the transformed numpy array
        """
        vfunc = np.vectorize(lambda x:self.uid2ind[x])
        return vfunc(vec)

    def index2uid(self, vec):
        """
        User Index representation to user ID representation

        Args:
            vec  -  the np.array to work with
        Return:
            the transformed numpy array
        """
        vfunc = np.vectorize(lambda x:self.ind2uid[x])
        return vfunc(vec)


if __name__ == "__main__":
    test = DataLoader(dataset="3dprinting")
    test.__load_word2vec()

