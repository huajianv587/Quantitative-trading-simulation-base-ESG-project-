from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes


def chunk_documents(documents: list) -> tuple[list, list]:
    """
    Split documents into a parent-child node hierarchy.

    Returns:
        all_nodes  — every node (parent + child), needed for the docstore
        leaf_nodes — smallest nodes only, used to build the vector index
    """
    parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[2048, 512, 128]  # parent → mid → leaf
    )
    all_nodes = parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(all_nodes)
    return all_nodes, leaf_nodes
