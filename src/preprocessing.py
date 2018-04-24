#!/home/zeyu/anaconda3/bin/python3.6

"""
    Preprocessing

    Author:
        Zeyu Li <zyli@cs.ucla.edu> or <zeyuli@ucla.edu>

    Description:
        Take in the Very raw data and produce a ready-to-use version
"""

import sys, os
import re
import logging
import numpy as np
from lxml import etree
from bs4 import BeautifulSoup

import nltk
nltk.data.path.append("/workspace/nltk_data")
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

import string

try:
    import ujson as json
except:
    import json

part_user = set()
    # Users participated in Asking and Answering

count_Q, count_A = {}, {}
good_Q, good_A = [], []

def clean_html(x):
    return BeautifulSoup(x, 'lxml').get_text()


def clean_str(string):
    """Clean up the string

    Cleaning strings of content or title
    Original taken from [https://github.com/yoonkim/CNN_sentence/blob/master/process_data.py]

    Args:
        string - the string to clean

    Return:
        _ - the cleaned string
    """
    string = re.sub(r"[^A-Za-z0-9(),!?\'\`]", " ", string)
    string = re.sub(r"\'s", " \'s", string)
    string = re.sub(r"\'ve", " \'ve", string)
    string = re.sub(r"n\'t", " n\'t", string)
    string = re.sub(r"\'re", " \'re", string)
    string = re.sub(r"\'d", " \'d", string)
    string = re.sub(r"\'ll", " \'ll", string)
    string = re.sub(r",", " , ", string)
    string = re.sub(r"!", " ! ", string)
    string = re.sub(r"\(", " \( ", string)
    string = re.sub(r"\)", " \) ", string)
    string = re.sub(r"\?", " \? ", string)
    string = re.sub(r"\s{2,}", " ", string)
    return string.strip().lower()


def clean_str2(s):
    """Clean up the string

    * New version, removing all punctuations

    Cleaning strings of content or title
    Original taken from [https://github.com/yoonkim/CNN_sentence/blob/master/process_data.py]

    Args:
        string - the string to clean

    Return:
        _ - the cleaned string
    """
    ss = s
    translator = str.maketrans("", "", string.punctuation)
    ss = re.sub(r"[^A-Za-z0-9(),!?\'\`]", " ", ss)
    ss = re.sub(r"\'s", "s", ss)
    ss = re.sub(r"\'ve", "ve", ss)
    ss = re.sub(r"n\'t", "nt", ss)
    ss = re.sub(r"\'re", "re", ss)
    ss = re.sub(r"\'d", "d", ss)
    ss = re.sub(r"\'ll", "ll", ss)
    ss = re.sub(r"\s{2,}", " ", ss)
    ss = ss.translate(translator)
    return ss.strip().lower()


def remove_stopwords(string, stopword_set):
    """Removing Stopwords

    Args:
        string - the input string to remove stopwords
        stopword_set - the set of stopwords

    Return:
        _ - the string that has all the stopwords removed
    """
    word_tokens = word_tokenize(string)
    filtered_string = [word for word in word_tokens
                       if word not in stopword_set]
    return " ".join(filtered_string)


def split_post(raw_dir, data_dir):
    """ Split the post

    Split post to question and answer,
    keep all information, output to file

    Args:
        raw_dir - raw data directory
        data_dir - parsed data directory
    """
    with open(data_dir + "Posts_Q.json", "w") as fout_q, \
            open(data_dir + "Posts_A.json", "w") as fout_a:
        parser = etree.iterparse(raw_dir + 'Posts.xml',
                                 events=('end',), tag='row')
        for event, elem in parser:

            attr = dict(elem.attrib)
            attr['Body'] = clean_html(attr['Body'])

            # Output to separate files
            if attr['PostTypeId'] == '1':
                fout_q.write(json.dumps(attr) + "\n")
            elif attr['PostTypeId'] == '2':
                fout_a.write(json.dumps(attr) + "\n")
    return


def process_QA(parsed_dir, data_dir, threshold, prop_test):
    """Process QA

    Extract attributes used in this project
    Get rid of the text information,
    only record the question-user - answer-user relation

    Args:
        data_dir - the dir where primitive data is stored
    """
    POST_Q = "Posts_Q.json"
    POST_A = "Posts_A.json"
    OUTPUT = "QAU_Map_all.json"
    OUTPUT_TEST = "test.txt"
    OUTPUT_TRAIN = "QAU_Map.json"
    OUTPUT_TEST_QA = "test_q_alist.txt"

    # Get logger to log exceptions
    logger = logging.getLogger(__name__)

    if not os.path.exists(data_dir + POST_Q):
        raise IOError("file {} does NOT exist".format(data_dir + POST_Q))

    if not os.path.exists(data_dir + POST_A):
        raise IOError("file {} does NOT exist".format(data_dir + POST_A))

    qa_map = {}

    # Process question information
    with open(data_dir + POST_Q, 'r') as fin_q:
        for line in fin_q:
            data = json.loads(line)
            try:
                qid, owner_id = data.get('Id', None), data.get('OwnerUserId', None)
                acc_id = data.get('AcceptedAnswerId', None)
                # Add to qa_map only when all three attributes are not None
                if qid and owner_id:
                    qa_map[qid] = {
                        'QuestionId': qid,
                        'QuestionOwnerId': owner_id,
                        'AcceptedAnswerId': acc_id,
                        'AnswerOwnerList': []
                    }
                    # count how many questions an users asked
                    count_Q[owner_id] = count_Q.get(owner_id, 0) + 1
            except:
                logger.error("Error at process_QA 1: "+ str(data))
                continue

    # Process answer information
    with open(data_dir + POST_A, 'r') as fin_a:
        for line in fin_a:
            data = json.loads(line)
            try:
                aid, owner_id = data.get('Id', None), data.get('OwnerUserId', None)
                par_id = data.get('ParentId', None)
                entry = qa_map.get(par_id, None)
                if aid and owner_id and par_id and entry:
                    entry['AnswerOwnerList'].append((aid, owner_id))
                    # count the how many questions an answerer responded
                    count_A[owner_id] = count_A.get(owner_id, 0) + 1
                else:
                    logger.error("Answer {} belongs to unknown Question {} at Process QA"
                                 .format(aid, par_id))
            except IndexError as e:
                logger.error(e)
                logger.info("Error at process_QA 2: " + str(data))
                continue

    # Sort qid list, write to file by order of qid
    qid_list = sorted(list(qa_map.keys()),
                      key=lambda x: qa_map[x]['QuestionId'])

    total = len(qid_list)
    sample_table = set()

    #  Splitting the train and test at here!
    for qid in qa_map.keys():
        acc_ans_id = qa_map[qid]['AcceptedAnswerId']
        rid = qa_map[qid]['QuestionOwnerId']
        if not acc_ans_id:
            continue
        for ans_id, aid in qa_map[qid]['AnswerOwnerList']:
            if ans_id == acc_ans_id \
                    and count_Q[rid] >= threshold \
                    and count_A[aid] >= threshold:
                sample_table.add(qid)
            break

    print("\t\tFirst print all QAU map")
    with open(data_dir + OUTPUT, 'w') as fout:
        for q in qa_map.keys():
            fout.write(json.dumps(qa_map[q]) + "\n")

    print("\t\tLength of sample table {}".format(len(sample_table)), end=" ")
    print("Sampling {} from it.".format(int(total * prop_test)))
    test = np.random.choice(list(sample_table), size=int(total * prop_test),
                            replace=False)

    print("\t\tWriting the sampled test set to disk")
    with open(parsed_dir + OUTPUT_TEST, "w") as fout_test, \
        open(parsed_dir + OUTPUT_TEST_QA, "w") as fout_alist:
        for qid in test:
            rid = qa_map[qid]['QuestionOwnerId']
            accid = qa_map[qid]['AcceptedAnswerId']
            alist = qa_map[qid]['AnswerOwnerList']
            for answerid, answer_owner_id in alist:
                print("{} {}".format(qid, answer_owner_id), file=fout_alist)
                if answerid == accid:
                    print("{} {} {}".format(rid, qid, answer_owner_id), 
                          file=fout_test)

    # if qid is a test instance or qid doesn't have an answer
    for qid in qid_list:
        if qid in test or not len(qa_map[qid]['AnswerOwnerList']):
            del qa_map[qid]

    # Write QA pair to file
    print("\t\tFinally write the train QAU to disk")
    with open(data_dir + OUTPUT_TRAIN, 'w') as fout:
        for q in qa_map.keys():
            fout.write(json.dumps(qa_map[q]) + "\n")


def extract_question_user(data_dir, parsed_dir):
    """Extract Question User pairs and output to file.

    Extract "Q" and "R"

    Format:
        <Qid> <Rid>
    E.g.
        101 40
        145 351

    Args:
        data_dir - data directory
        parsed_dir - parsed file directory
    """
    INPUT = "QAU_Map.json"
    OUTPUT = "Q_R.txt"

    if not os.path.exists(data_dir + INPUT):
        IOError("Can NOT find {}".format(data_dir + INPUT))

    with open(data_dir + INPUT, "r") as fin:
        with open(parsed_dir + OUTPUT, "w") as fout:
            for line in fin:
                data = json.loads(line)
                qid = data['QuestionId']
                owner_id = data['QuestionOwnerId']
                part_user.add(int(owner_id))  # Adding participated questioners
                print("{} {}".format(str(qid), str(owner_id)), file=fout)


def extract_question_answer_user(data_dir, parsed_dir):
    """Extract Question, Answer User pairs and output to file.

    (1) Extract "Q" - "A"
        The list of AnswerOwnerList contains <aid>-<owner_id> pairs

        Format:
            <Qid> <Aid>
        E.g.
            100 1011
            21 490
    (2) Extract "Q" - Accepted answer

        Format:
            <Qid> <Acc_Ans_id>

    Args:
        data_dir - data directory
        parsed_dir - parsed file directory
    """
    INPUT = "QAU_Map.json"
    OUTPUT = "Q_A.txt"
    OUTPUT_ACCEPT = "Q_ACC.txt"

    if not os.path.exists(data_dir + INPUT):
        IOError("Can NOT find {}".format(data_dir + INPUT))

    with open(data_dir + INPUT, "r") as fin, \
            open(parsed_dir + OUTPUT_ACCEPT, "w") as fout_acc, \
            open(parsed_dir + OUTPUT, "w") as fout:
        for line in fin:
            data = json.loads(line)
            qid = data['QuestionId']
            au_list = data['AnswerOwnerList']
            acid = data['AcceptedAnswerId']
            for aid, ans_owner_id in au_list:
                part_user.add(int(ans_owner_id))
                print("{} {}".format(str(qid), str(ans_owner_id)),
                      file=fout)
            print("{} {}".format(str(qid), str(acid)),
                  file=fout_acc)


def extract_question_content(data_dir, parsed_dir):
    """Extract questions, content pairs from question file

    Question content pair format:
        <qid> <content>
    We extract both with and without stop-word version
        which is signified by "_nsw"

    Args:
        data_dir - data directory
        parsed_dir - parsed file directory
    """
    INPUT = "Posts_Q.json"
    OUTPUT_T = "Q_title.txt"  # Question title
    OUTPUT_T_NSW = "Q_title_nsw.txt"  # Question title, no stop word
    OUTPUT_C = "Q_content.txt"  # Question content
    OUTPUT_C_NSW = "Q_content_nsw.txt"  # Question content, no stop word

    logger = logging.getLogger(__name__)

    if not os.path.exists(data_dir + INPUT):
        IOError("Can NOT locate {}".format(data_dir + INPUT))

    sw_set = set(stopwords.words('english'))  # Create the stop word set


    # We will try both with or without stopwords to
    # check out the performance.
    with open(data_dir + INPUT, "r") as fin, \
            open(parsed_dir + OUTPUT_T, "w") as fout_t, \
            open(parsed_dir + OUTPUT_T_NSW, "w") as fout_t_nsw, \
            open(parsed_dir + OUTPUT_C, "w") as fout_c, \
            open(parsed_dir + OUTPUT_C_NSW, "w") as fout_c_nsw:
        for line in fin:
            data = json.loads(line)
            try:
                qid = data.get('Id')
                title = data.get('Title')
                content = data.get('Body')

                content, title = clean_str2(content), clean_str2(title)
                content_nsw = remove_stopwords(content, sw_set)
                title_nsw = remove_stopwords(title, sw_set)

                print("{} {}".format(qid, content_nsw),
                      file=fout_c_nsw)  # Without stopword
                print("{} {}".format(qid, content),
                      file=fout_c)  # With stopword
                print("{} {}".format(qid, title_nsw),
                      file=fout_t_nsw)  # Without stopword
                print("{} {}".format(qid, title),
                      file=fout_t)  # With stopword
            except:
                logger.info("Error at Extracting question content and title: "
                            + str(data))
                continue


def extract_answer_score(data_dir, parsed_dir):
    """Extract the answers vote, a.k.a. Scores.

    This information might be useful when
        the accepted answer is not selected.

    Args:
        data_dir - Input data dir
        parsed_dir - Output data dir
    """
    INPUT = "Posts_A.json"
    OUTPUT = "A_score.txt"

    logger = logging.getLogger(__name__)

    if not os.path.exists(data_dir + INPUT):
        IOError("Cannot find file{}".format(data_dir + INPUT))

    with open(data_dir + INPUT, "r") as fin, \
        open(parsed_dir + OUTPUT, "w") as fout:
        for line in fin:
            data = json.loads(line)
            try:
                aid = data.get('Id')
                score = data.get('Score')
                print("{} {}".format(aid, score), file=fout)
            except:
                logging.info("Error at Extracting answer score: "
                             + str(data))
                continue


def extract_question_best_answerer(data_dir, parsed_dir):
    """Extract the question-best-answerer relation

    Args:
        data_dir  - as usual
        parsed_dir  -  as usual
    """
    INPUT_A = "Posts_A.json"
    INPUT_MAP = "QAU_Map.json"
    OUTPUT = "Q_ACC_A.txt"

    if not os.path.exists(data_dir + INPUT_A):
        IOError("Cannot find file {}".format(data_dir + INPUT_A))
    if not os.path.exists(data_dir + INPUT_MAP):
        IOError("Cannot find file {}".format(data_dir + INPUT_MAP))

    accaid_uaid = {}  # Accepted answer id to Answering user id
    aid_score = {}  # Answer id to answer scores
    with open(data_dir + INPUT_A, "r") as fin_a, \
        open(data_dir + INPUT_MAP, "r") as fin_map, \
        open(parsed_dir + OUTPUT, "w") as fout:

        # build acc-a dict
        for line in fin_a:
            data = json.loads(line)
            try:
                aid = data.get("Id")
                score = data.get("Score")
                uaid = data.get("OwnerUserId")
                aid_score[aid] = score
                accaid_uaid[aid] = uaid
            except:
                logging.info(
                    "Error at Extracting question, best answer user: "
                    + str(data))

        for line in fin_map:
            data = json.loads(line)
            try:
                qid = data.get('QuestionId')
                if "AcceptedAnswerID" in data:  # If acc answer exists
                    acc_aid = data.get('AcceptedAnswerId')
                else:
                # If acc answer doesn't exist, choose highest score answer
                    ans = data.get('AnswerOwnerList')
                    ans = list(zip(*ans))[0]
                    scores = [aid_score[aid] for aid in ans]
                    max_ind = scores.index(max(scores))
                    acc_aid = ans[max_ind]
                uaccid = accaid_uaid[acc_aid]
                print("{} {}".format(qid, uaccid), file=fout)
            except:
                logging.info(
                    "Error at Extracting question, best answer user: "
                     + str(data))


def write_part_users(parsed_dir):
    OUTPUT = "part_users.txt"
    with open(parsed_dir + OUTPUT, "w") as fout:
        idlist = list(part_user)
        idlist.sort()
        for user_id in idlist:
            print("{}".format(user_id), file=fout)


def preprocess_(dataset, threshold, prop_test):
    DATASET = dataset
    RAW_DIR = os.getcwd() + "/raw/{}/".format(DATASET)
    DATA_DIR= os.getcwd() + "/data/{}/".format(DATASET)
    PARSED_DIR = os.getcwd() + "/data/parsed/{}/".format(DATASET)

    print("Preprocessing {} ...".format(dataset))

    if not os.path.exists(RAW_DIR):
        print("{} dir or path doesn't exist.\n"
              "Please download the raw data set into the /raw."
              .format(RAW_DIR), file=sys.stderr)
        sys.exit()

    if not os.path.exists(DATA_DIR):
        print("{} data dir not found.\n"
              " Creating a folder for that."
              .format(DATA_DIR))
        os.makedirs(DATA_DIR)

    if not os.path.exists(PARSED_DIR):
        print("{} dir or path NOT found.\n"
              "Creating a folder for that."
              .format(PARSED_DIR))
        os.makedirs(PARSED_DIR)

    if os.path.exists(DATA_DIR + "log.log"):
        os.remove(DATA_DIR + "log.log")

    # Setting up loggers
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    log_fh = logging.FileHandler(DATA_DIR + "log.log")
    log_fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_fh.setFormatter(formatter)
    logger.addHandler(log_fh)

    # Split contest to question and answer
    print("\tSpliting post")
    split_post(raw_dir=RAW_DIR, data_dir=DATA_DIR)

    # Extract question-user, answer-user, and question-answer information
    # Generate Question and Answer/User map
    print("\tProcessing QA")
    process_QA(data_dir=DATA_DIR, parsed_dir=PARSED_DIR,
               threshold=threshold, prop_test=prop_test)

    print("\tExtracting Q, R, A relations ...")
    extract_question_user(data_dir=DATA_DIR, parsed_dir=PARSED_DIR)

    extract_question_answer_user(data_dir=DATA_DIR, parsed_dir=PARSED_DIR)

    extract_question_content(data_dir=DATA_DIR, parsed_dir=PARSED_DIR)

    extract_answer_score(data_dir=DATA_DIR, parsed_dir=PARSED_DIR)

    extract_question_best_answerer(data_dir=DATA_DIR, parsed_dir=PARSED_DIR)

    write_part_users(parsed_dir=PARSED_DIR)

    print("Done!")


if __name__ == "__main__":
    if len(sys.argv) < 3 + 1:
        print("\t Usage: {} [name of dataset]"
              .format(sys.argv[0]), file=sys.stderr)
        sys.exit(0)
    threshold = int(sys.argv[2])
    prop_test = float(sys.argv[3])
    preprocess_(sys.argv[1], threshold, prop_test)
