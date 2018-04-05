"""
    Random walk generator

    Author:
        Zeyu Li <zyli@cs.ucla.edu> or <zeyuli@ucla.edu>

    Description:
        Generating random walks on our Uq, Ua, and Q network using NetworkX.


"""

import os, sys
import networkx as nx
import random


class MetaPathGenerator:
    """MetaPathGenerator

    Args:
        dataset     - the dataset to work on
        length      - the length of random walks to be generated
        num_walks   - the number of random walks start from each node
    """

    def __init__(self, dataset, length=100, num_walks=10000):
        self._walk_length = length
        self._num_walks = num_walks
        self._dataset = dataset
        self.G = nx.Graph()

        self.initialize()

    def initialize(self):
        """ Initialize Graph

        Initialize graph with Uq-Q pairs and Q-Ua pairs.
        We use following Uppercase letter

        Args:
            QR_file - Input file containing Q-R pairs
            QA_file - Input file containing Q-A pairs

        """

        DATA_DIR = os.getcwd() + "/data/parsed/" + self._dataset + "/"
        QR_file = DATA_DIR + "Q_R.txt"
        QA_file = DATA_DIR + "Q_A.txt"
        G = self.G
        # Read in Uq-Q pairs
        with open(QR_file, "r") as fin:
            lines = fin.readlines()
            RQ_edge_list = []
            for line in lines:
                unit = line.strip().split()
                RQ_edge_list.append(["Q_" + unit[0],
                                     "R_" + unit[1]])
            G.add_edges_from(RQ_edge_list)
        with open(QA_file, "r") as fin:
            lines = fin.readlines()
            QA_edge_list = []
            for line in lines:
                unit = line.strip().split()
                QA_edge_list.append(["Q_" + unit[0],
                                     "A_" + unit[1]])
            G.add_edges_from(QA_edge_list)

    def get_nodelist(self, type=None):
        """ Get specific type or all nodes of nodelist in the graph

        Args:
            type - The entity type of the entity.
                   If set as `None`, then all types of nodes would be returned.

        Return:
            nodelist - the list of node with `type`
        """
        G = self.G

        if not G.number_of_edges() or not G.number_of_nodes():
            sys.exit("Graph should be initialized before get_nodelist()!")

        if not type:
            return list(G.nodes)
        return [node for node in list(G.nodes)
                if node[0] == type]

    def generate_metapaths(self, patterns, alpha):
        """ Generate Random Walk

        Generating random walk from the Tripartite graph
        A candidate pattern pool is:
            "A-Q-R-Q-A": specifies 2 A's answered a question proposed by a same R
            "A-Q-A": speficies 2 A' answered a same question

        Args:
            meta_pattern - the pattern that guides the walk generation
            alpha - probability of restart

        Return:
            walks - a set of generated random walks
        """
        G = self.G
        num_walks, walk_len = self._num_walks, self._walk_length
        rand = random.Random(0)

        print("Generating Meta-paths ...")

        if not G.number_of_edges() or not G.number_of_nodes():
            sys.exit("Graph should be initialized before generate_walks()!")

        walks = []

        for meta_pattern in patterns:  # Generate by patterns
            print("\tNow generating meta-paths from pattern: \"{}\" ..."
                  .format(meta_pattern))
            start_entity_type = meta_pattern[0]
            start_node_list = self.get_nodelist(start_entity_type)
            for cnt in range(num_walks):  # Iterate the node set for cnt times
                rand.shuffle(start_node_list)
                for start_node in start_node_list:
                    walks.append(
                        self.__meta_path_walk(
                            start=start_node,
                            alpha=alpha,
                            pattern=meta_pattern))

        print("Done!")
        return walks

    def __meta_path_walk(self, start=None, alpha=0.0,pattern=None):
        """Single Walk Generator

        Generating a single random walk that follows a meta path of `pattern`

        Args:
            rand - an random object to generate random numbers
            start - starting node
            alpha - probability of restarts
            pattern - (string) the pattern according to which to generate walks
            walk_len - (int) the length of the generated walk

        Return:
            walk - the single walk generated

        """
        def type_of(node_id):
            return node_id[0]


        rand = random.Random()
        # Checking pattern is correctly initialized
        if not pattern:
            sys.exit("Pattern is not specified when generating meta-path walk")

        G = self.G
        n, pat_ind = 1, 1

        walk = [start]

        cur_node = start

        # Generating meta-paths
        while len(walk) <= self._walk_length or pat_ind != len(pattern):

            # Updating the pattern index
            pat_ind = pat_ind if pat_ind != len(pattern) else 1

            # Decide whether to restart
            if rand.random() >= alpha:
                # Find all possible next neighbors
                possible_next_node = [neighbor
                                      for neighbor in G.neighbors(cur_node)
                                      if type_of(neighbor) == pattern[pat_ind]]
                # Random choose next node
                next_node = rand.choice(possible_next_node)
            else:
                next_node = walk[0]

            walk.append(next_node)
            cur_node = next_node
            pat_ind += 1

        return " ".join(walk)

    def write_metapaths(self, walks):
        """Write Metapaths to files

        Args:
            walks - The walks generated by `generate_walks`
        """

        print("Writing Generated Meta-paths to files ...", end=" ")

        DATA_DIR = os.getcwd() + "/metapath/"
        OUTPUT = DATA_DIR + self._dataset + ".txt"
        if not os.path.exists(DATA_DIR):
            os.mkdir(DATA_DIR)
        with open(OUTPUT, "w") as fout:
            for walk in walks:
                print("{}".format(walk), file=fout)

        print("Done!")

if __name__ == "__main__":
    gw = MetaPathGenerator(length=15, num_walks=2, dataset="3dprinting")
    walks = gw.generate_metapaths(patterns=["AQRQA", "AQA"], alpha=0)
    gw.write_metapaths(walks)




