#include <boost/graph/graph_traits.hpp>
#include <boost/graph/adjacency_list.hpp>
#include <boost/graph/dijkstra_shortest_paths.hpp>
#include <memory>
#include "stabiliser_graph.h"

struct WeightedEdgeData {
    int qubit_id;
    double weight;
};

typedef boost::adjacency_list < boost::listS, boost::vecS, boost::undirectedS,
    boost::no_property, WeightedEdgeData > wgraph_t;
typedef boost::graph_traits < wgraph_t >::vertex_descriptor vertex_descriptor;
typedef boost::graph_traits < wgraph_t >::edge_descriptor edge_descriptor;


class WeightedStabiliserGraph : public IStabiliserGraph{
    public:
        wgraph_t stabiliser_graph;
        WeightedStabiliserGraph(int num_stabilisers);
        void AddEdge(int node1, int node2, int qubit_id, double weight);
        void ComputeAllPairsShortestPaths();
        virtual int Distance(int node1, int node2) const;
        virtual std::vector<int> ShortestPath(int node1, int node2) const;
        virtual int QubitID(int node1, int node2) const;
        virtual int GetNumQubits() const;
        virtual int GetNumStabilisers() const;
        std::vector<std::vector<double>> all_distances;
        std::vector<std::vector<vertex_descriptor>> all_predecessors;
        int num_stabilisers;

};