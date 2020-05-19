import numpy as np
import networkx as nx
from scipy.sparse import csc_matrix, spmatrix, vstack

from pymatching._cpp_mwpm import (all_pairs_shortest_path, 
                            decode, 
                            UnweightedStabiliserGraph,
                            WeightedStabiliserGraph)


def check_two_checks_per_qubit(H):
    if np.count_nonzero(H.indptr[1:]-H.indptr[0:-1]-2) != 0:
        raise ValueError("Parity check matrix does not have two "
                            "non-zero entries per column")


def find_boundary_nodes(G):
    """Find the boundary vertex in G, if present

    Find the boundary vertex in G, which has the attribute
    `is_boundary' set to `True'. Return the index of the 
    boundary node, or -1 if no boundary is present.

    Parameters
    ----------
    G : NetworkX graph
        The graph to be contracted

    Returns
    -------
    boundary
        The index of the boundary vertex in G (or -1 if 
        no boundary is present).
    """
    return [i for i, attr in G.nodes(data=True) 
            if attr.get("is_boundary", False)]
    

class Matching:
    def __init__(self, H, weights=None, error_probabilities=None):
        if not isinstance(H, nx.Graph):
            H = csc_matrix(H)
            unique_elements = np.unique(H.data)
            if len(unique_elements)>1 or unique_elements[0] != 1:
                raise ValueError("Nonzero elements in the parity check matrix"
                                 f" must be 1, not {unique_elements}.")
            column_weights = np.asarray(H.sum(axis=0))[0]
            unique_column_weights = np.unique(column_weights)
            if np.setdiff1d(unique_column_weights, np.array([1,2])).size > 0:
                raise ValueError("Each qubit must be contained in either "
                                 "1 or 2 check operators.")
            if 1 in unique_column_weights:
                # Add boundary and connect it to all weight-1 stabilisers
                H = vstack([H, csc_matrix((column_weights==1).astype(np.uint8))])
                boundary = [H.shape[0]-1]
            else:
                boundary = []
            H = csc_matrix(H)
            H.eliminate_zeros()
            H.sort_indices()
            self.num_stabilisers = H.shape[0] if len(boundary) == 0 else H.shape[0]-1
            num_qubits = H.shape[1]
            if weights is None and error_probabilities is None:
                self.stabiliser_graph = UnweightedStabiliserGraph(
                    H.indices,
                    boundary
                )
            else:
                weights = np.asarray(weights) if weights is not None else np.ones(H.shape[1])
                if weights.shape[0] != num_qubits:
                    raise ValueError("Weights array must have num_qubits elements")
                if np.any(weights < 0.):
                    raise ValueError("All weights must be non-negative.")
                if error_probabilities is None:
                    self.stabiliser_graph = WeightedStabiliserGraph(
                        H.indices,
                        weights,
                        boundary
                    )
                else:
                    self.stabiliser_graph = WeightedStabiliserGraph(
                        H.indices,
                        weights,
                        error_probabilities,
                        boundary
                    )
        else:
            boundary = find_boundary_nodes(H)
            num_nodes = H.number_of_nodes()
            self.num_stabilisers = num_nodes - len(boundary)
            g = WeightedStabiliserGraph(self.num_stabilisers, boundary)
            for (u, v, attr) in H.edges(data=True):
                qubit_id = attr.get("qubit_id", -1)
                weight = attr.get("weight", 1) # Default weight is 1 if not provided
                if weight < 0:
                    raise ValueError("Weights cannot be negative.")
                e_prob = attr.get("error_probability", -1)
                g.add_edge(u, v, qubit_id, weight, e_prob, 0<=e_prob<=1)
            self.stabiliser_graph = g
        self.stabiliser_graph.compute_all_pairs_shortest_paths()
    
    @property
    def num_qubits(self):
        return self.stabiliser_graph.get_num_qubits()
    
    @property
    def boundary(self):
        return self.stabiliser_graph.get_boundary()
    
    def decode(self, z):
        if len(z.shape) == 1 and (self.num_stabilisers <= z.shape[0]
                <= self.num_stabilisers+len(self.boundary)):
            defects = z.nonzero()[0]
            if len(defects) % 2 != 0:
                if len(self.boundary) == 0:
                    raise ValueError("Syndrome must contain an even number of defects "
                                     "if no boundary vertex is given.")
                defects = np.setxor1d(defects, np.array(self.boundary[0:1]))
        elif len(z.shape) == 2 and z.shape[0] == self.num_stabilisers:
            times, checks = z.T.nonzero()
            defects = times*self.num_stabilisers + checks
            if len(defects) % 2 != 0:
                raise ValueError("Number of defects is odd (boundaries not yet supported "
                                 "for 2D syndromes).")
        else:
            raise ValueError(f"The shape ({z.shape}) of the syndrome vector z is not valid.")
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
            Syndrome vector (binary numpy int array of length 
            self.num_stabilisers if there is no boundary, or self.num_stabilisers+1
            if there is a boundary)
        """
        if isinstance(self.stabiliser_graph, WeightedStabiliserGraph):
            if not self.stabiliser_graph.all_edges_have_error_probabilities:
                return None
            return self.stabiliser_graph.add_noise()
        else:
            return None