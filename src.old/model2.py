"""
            irint("check point 1, epoch", epoch)

    Model file

    author: Zeyu Li <zeyuli@ucla.ed> or <zyli@cs.ucla.edu>

    Implemented model
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable

from collections import OrderedDict


class NeRank(nn.Module):
    """
    Model class

    Heterogeneous Entity Embedding Based Recommendation
    """
    def __init__(self, embedding_dim, vocab_size, lstm_layers,
                 cnn_channel, lambda_):
        super(NeRank, self).__init__()
        self.emb_dim = embedding_dim
        self.lstm_layers = lstm_layers
        self.lambda_=lambda_

        self.ru_embeddings = nn.Embedding(vocab_size,
                                          embedding_dim,
                                          sparse=False)
        self.rv_embeddings = nn.Embedding(vocab_size,
                                          embedding_dim,
                                          sparse=False)
        self.au_embeddings = nn.Embedding(vocab_size,
                                          embedding_dim,
                                          sparse=False)
        self.av_embeddings = nn.Embedding(vocab_size,
                                          embedding_dim,
                                          sparse=False)
        self.init_emb()

        self.ubirnn = nn.LSTM(input_size=300, hidden_size=embedding_dim,
                              num_layers=self.lstm_layers, batch_first=True,
                              bidirectional=False)
        self.vbirnn = nn.LSTM(input_size=300, hidden_size=embedding_dim,
                              num_layers=self.lstm_layers, batch_first=True,
                              bidirectional=False)

        self.out_channel = cnn_channel
        self.convnet1 = nn.Sequential(OrderedDict([
            ('conv1', nn.Conv2d(1, self.out_channel, kernel_size=(1, embedding_dim))),
            ('relu1', nn.ReLU()),
            ('pool1', nn.MaxPool2d(kernel_size=(3, 1)))
        ]))

        self.convnet2 = nn.Sequential(OrderedDict([
            ('conv2', nn.Conv2d(1, self.out_channel, kernel_size=(2, embedding_dim))),
            ('relu2', nn.ReLU()),
            ('pool2', nn.MaxPool2d(kernel_size=(2, 1)))
        ]))

        self.convnet3 = nn.Sequential(OrderedDict([
            ('conv3', nn.Conv2d(1, self.out_channel, kernel_size=(3, embedding_dim))),
            ('relu3', nn.ReLU())
        ]))

        self.fc1 = nn.Linear(self.out_channel, 1)
        self.fc2 = nn.Linear(self.out_channel, 1)
        self.fc3 = nn.Linear(self.out_channel, 1)

    def init_emb(self):
        """Initialize R and A embeddings"""
        initrange = 0.5 / self.emb_dim
        self.ru_embeddings.weight.data.uniform_(-initrange, initrange)
        self.ru_embeddings.weight.data[0].zero_()
        self.rv_embeddings.weight.data.uniform_(-0, 0)
        self.au_embeddings.weight.data.uniform_(-initrange, initrange)
        self.ru_embeddings.weight.data[0].zero_()
        self.av_embeddings.weight.data.uniform_(-0, 0)

    def init_hc(self, batch_size):
        h = Variable(
                torch.zeros(self.lstm_layers, batch_size, self.emb_dim))
        c = Variable(
                torch.zeros(self.lstm_layers, batch_size, self.emb_dim))
        if torch.cuda.is_available():
            (h, c) = (h.cuda(), c.cuda())
        return h, c

    def forward(self, rpos, apos, qinfo, rank, dl, test_data, train=True):
        if train:
            embed_ru = self.ru_embeddings(rpos[0])
            embed_au = self.au_embeddings(apos[0])

            embed_rv = self.rv_embeddings(rpos[1])
            embed_av = self.av_embeddings(apos[1])

            neg_embed_rv = self.rv_embeddings(rpos[2])
            neg_embed_av = self.av_embeddings(apos[2])

            quinput, qvinput, qninput = qinfo[:3]
            qulen, qvlen, qnlen = qinfo[3:]

            u_output, _ = self.ubirnn(quinput, self.init_hc(quinput.size(0)))
            v_output, _ = self.vbirnn(qvinput, self.init_hc(quinput.size(0)))
            n_output, _ = self.vbirnn(qninput, self.init_hc(qninput.size(0)))

            u_pad = Variable(torch.zeros(u_output.size(0), 1, u_output.size(2)))
            v_pad = Variable(torch.zeros(v_output.size(0), 1, v_output.size(2)))
            n_pad = Variable(torch.zeros(n_output.size(0), 1, n_output.size(2)))

            if torch.cuda.is_available():
                u_pad = u_pad.cuda()
                v_pad = v_pad.cuda()
                n_pad = n_pad.cuda()

            u_output = torch.cat((u_pad, u_output), 1)
            v_output = torch.cat((v_pad, v_output), 1)
            n_output = torch.cat((n_pad, n_output), 1)

            qulen = qulen.unsqueeze(1).expand(-1, self.emb_dim).unsqueeze(1)
            qvlen = qvlen.unsqueeze(1).expand(-1, self.emb_dim).unsqueeze(1)
            qnlen = qnlen.unsqueeze(1).expand(-1, self.emb_dim).unsqueeze(1)

            embed_qu = u_output.gather(1, qulen.detach())
            embed_qv = v_output.gather(1, qvlen.detach())
            neg_embed_qv = n_output.gather(1, qnlen.detach())

            # TODO: check correctness

            embed_u = embed_ru + embed_au + embed_qu.squeeze()
            embed_v = embed_rv + embed_av + embed_qv.squeeze()

            score = torch.mul(embed_u, embed_v)
            score = torch.sum(score)

            log_target = F.logsigmoid(score).squeeze()

            neg_embed_v = neg_embed_av + neg_embed_rv + neg_embed_qv.squeeze()
            neg_embed_v = neg_embed_v.view(quinput.size(0), -1, self.emb_dim)

            """
            Some notes around here.
            * unsqueeze(): add 1 dim in certain position
            * squeeze():   remove all 1 dims. E.g. (4x1x2x4x1) -> (4x2x4)
            * Explain the dimension:
                bmm: batch matrix-matrix product.
                    batch1 - b x n x m
                    quinput.size(0) - b x m x p
                    return - b x n x p
                Here:
                    neg_embed_v - 2*batch_size*window_size x count x emb_dim
                    embed_u     - 2*batch_size*window_size x emb_dim
                    embed_u.unsqueeze(2)
                                - 2*batch_size*window_size x emb_dim x 1
                    bmm(.,.)    - 2*batch_size*window_size x count x 1
                    bmm(.,.).squeeze()
                                - 2*batch_size*window_size x count
            * Input & Output of nn.Embeddings:
                In : LongTensor(N,M)
                Out: (N, W, embedding_dim)
            """

            neg_score = torch.bmm(neg_embed_v, embed_u.unsqueeze(2)).squeeze()
            neg_score = torch.sum(neg_score)
            sum_log_sampled = F.logsigmoid(-1 * neg_score).squeeze()

            ne_loss = - (log_target + sum_log_sampled)

            """
                === Ranking ===
            """

            emb_rank_r = self.ru_embeddings(rank[0])
            emb_rank_a = self.au_embeddings(rank[1])
            emb_rank_acc = self.au_embeddings(rank[2])
            rank_q, rank_q_len = rank[3], rank[4]

            rank_q_output, _ = self.ubirnn(rank_q, self.init_hc(rank_q.size(0)))
            rank_q_pad = Variable(torch.zeros(
                rank_q_output.size(0), 1, rank_q_output.size(2))).cuda()
            rank_q_output = torch.cat((rank_q_pad, rank_q_output), 1)
            rank_q_len = rank_q_len.unsqueeze(1).expand(-1, self.emb_dim).unsqueeze(1)
            emb_rank_q = rank_q_output.gather(1, rank_q_len.detach())

            low_rank_mat = torch.stack(
                    [emb_rank_r, emb_rank_q.squeeze(), emb_rank_a], dim=1)
            low_rank_mat = low_rank_mat.unsqueeze(1)
            high_rank_mat = torch.stack(
                    [emb_rank_r, emb_rank_q.squeeze(), emb_rank_acc], dim=1)
            high_rank_mat = high_rank_mat.unsqueeze(1)

            low_score = self.fc1(self.convnet1(low_rank_mat).view(-1, self.out_channel)) \
                      + self.fc2(self.convnet2(low_rank_mat).view(-1, self.out_channel)) \
                      + self.fc3(self.convnet3(low_rank_mat).view(-1, self.out_channel))

            high_score = self.fc1(self.convnet1(high_rank_mat).view(-1, self.out_channel)) \
                       + self.fc2(self.convnet2(high_rank_mat).view(-1, self.out_channel)) \
                       + self.fc3(self.convnet3(high_rank_mat).view(-1, self.out_channel))

            rank_loss = torch.sum(low_score - high_score)

            # loss = F.sigmoid(ne_loss) + self.lambda_ * F.sigmoid(rank_loss)
            loss = ne_loss + self.lambda_ * rank_loss
            return loss
        else:
            # test_a, _r, _q all variables
            test_a, test_r, test_q, test_q_len = test_data
            a_size = test_a.size(0)

            emb_rank_a = self.au_embeddings(test_a)
            emb_rank_r = self.ru_embeddings(test_r)

            test_q_output, _ = self.ubirnn(test_q.unsqueeze(0), self.init_hc(1))

            ind = Variable(torch.LongTensor([test_q_len])).cuda()
            test_q_target_output = torch.index_select(test_q_output.squeeze(), 0, ind)

            emb_rank_q = test_q_target_output.squeeze()\
                .repeat(a_size).view(a_size, self.emb_dim)

            emb_rank_mat = torch.stack([emb_rank_r, emb_rank_q, emb_rank_a], dim=1)
            emb_rank_mat = emb_rank_mat.unsqueeze(1)
            score = self.fc1(self.convnet1(emb_rank_mat).view(-1, self.out_channel)) \
                    + self.fc2(self.convnet2(emb_rank_mat).view(-1, self.out_channel)) \
                    + self.fc3(self.convnet3(emb_rank_mat).view(-1, self.out_channel))

            ret_score = score.data.squeeze().tolist()
            return ret_score