import numpy as np
import networkx as nx
from scipy.sparse import csc_matrix, spmatrix

from mwpm._cpp_mwpm import (all_pairs_shortest_path, 
                            decode, 
                            UnweightedStabiliserGraph,
                            WeightedStabiliserGraph)


def check_two_checks_per_qubit(H):
    if np.count_nonzero(H.indptr[1:]-H.indptr[0:-1]-2) != 0:
        raise ValueError("Parity check matrix does not have two "
                            "non-zero entries per column")


def syndrome_graph_from_check_matrix(H):
    H = csc_matrix(H)
    check_two_checks_per_qubit(H)
    H.sort_indices()
    G = nx.Graph()
    for i in range(len(H.indices)//2):
        G.add_edge(H.indices[2*i], H.indices[2*i+1], qubit_id=i)
    return G


def raise_error_for_edge_attribute(u, v, attr0, attr):
    raise ValueError(f"Edge ({u},{v}) has attributes {tuple(attr.keys())} but expected "
                     f"same attributes as first edge: {tuple(attr0.keys())}.")


class MWPM:
    def __init__(self, H, weights=None):
        if not isinstance(H, nx.Graph):
            H = csc_matrix(H)
            check_two_checks_per_qubit(H)
            H.sort_indices()
            self.num_stabilisers = H.shape[0]
            num_qubits = H.shape[1]
            if weights is None:
                self.stabiliser_graph = UnweightedStabiliserGraph(
                    H.indices
                )
            else:
                weights = np.asarray(weights)
                if weights.shape[0] != num_qubits:
                    raise ValueError("Weights array must have num_qubits elements")
                if np.any(weights < 0.):
                    raise ValueError("All weights must be non-negative.")
                self.stabiliser_graph = WeightedStabiliserGraph(
                    H.indices,
                    weights
                )
        else:
            self.num_stabilisers = H.number_of_nodes()
            attr0 = list(H.edges(data=True))[0][2]
            if 'weight' in attr0:
                g = WeightedStabiliserGraph(self.num_stabilisers)
                if 'qubit_id' in attr0:
                    for (u, v, attr) in H.edges(data=True):
                        if ('qubit_id' not in attr) or ('weight' not in attr):
                            raise_error_for_edge_attribute(u, v, attr0, attr)
                        e_prob = attr.get('error_probability', -1.)
                        g.add_edge(u, v, attr['qubit_id'], attr['weight'], e_prob)
                else:
                    for (i, (u, v, attr)) in enumerate(H.edges(data=True)):
                        if 'weight' not in attr:
                            raise_error_for_edge_attribute(u, v, attr0, attr)
                        e_prob = attr.get('error_probability', -1.)
                        g.add_edge(u, v, i, attr['weight'])
            else:
                g = UnweightedStabiliserGraph(self.num_stabilisers)
                if 'qubit_id' in attr0:
                    for (u, v, attr) in H.edges(data=True):
                        if 'qubit_id' not in attr:
                            raise_error_for_edge_attribute(u, v, attr0, attr)
                        g.add_edge(u, v, attr['qubit_id'])
                else:
                    for (i, (u, v, attr)) in enumerate(H.edges(data=True)):
                        g.add_edge(u, v, i)
            g.compute_all_pairs_shortest_paths()
            self.stabiliser_graph = g
    
    @property
    def num_qubits(self):
        return self.stabiliser_graph.get_num_qubits()
    
    def decode(self, z):
        if len(z.shape) == 1 and z.shape[0] == self.num_stabilisers:
            defects = z.nonzero()[0]
        elif len(z.shape) == 2 and z.shape[0] == self.num_stabilisers:
            times, checks = z.T.nonzero()
            defects = times*self.num_stabilisers + checks
        else:
            raise ValueError(f"The shape ({z.shape}) of the syndrome vector z is not valid.")
        if (len(defects) % 2) != 0:
            raise ValueError(f"There must be an even number of nonzero syndrome elements.")
        return decode(self.stabiliser_graph, defects)
    
    def add_noise(self):
        """Add noise by flipping edges in the stabiliser graph

        Add noise by flipping edges in the stabiliser graph with 
        a probability given by the error_probility edge attribute.
        This is currently only supported for weighted matching graphs
        initialised using a NetworkX graph.

        Returns
        -------
        numpy.ndarray of dtype int
            Noise vector (binary numpy int array of length self.num_qubits)
        numpy.ndarray of dtype int
            Syndrome vector (binary numpy int array of length self.num_stabilisers)
        """
        if isinstance(self.stabiliser_graph, WeightedStabiliserGraph):
            return self.stabiliser_graph.add_noise()
        else:
            return None
