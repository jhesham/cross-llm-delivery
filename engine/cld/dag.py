class CycleError(Exception):
    """Raised when the dependency graph has a cycle."""
    pass


def topo_layers(deps: dict[str, list[str]]) -> list[list[str]]:
    """
    Return a list of layers (batches) representing the execution order.
    Layer 0 contains all ids with no deps.
    Each subsequent layer contains ids whose deps are all in earlier layers.
    Within a layer, ids are sorted alphabetically.
    Raises CycleError if a cycle exists.
    """
    all_nodes = set()
    for u, vs in deps.items():
        all_nodes.add(u)
        all_nodes.update(vs)

    indegree = {u: 0 for u in all_nodes}
    adj = {u: [] for u in all_nodes}

    for u, vs in deps.items():
        for v in vs:
            # u depends on v, so the edge is v -> u
            adj[v].append(u)
            indegree[u] += 1

    layers = []
    current_layer = [u for u in all_nodes if indegree[u] == 0]

    processed_count = 0
    while current_layer:
        current_layer.sort()
        layers.append(current_layer)
        processed_count += len(current_layer)

        next_layer = []
        for v in current_layer:
            for u in adj[v]:
                indegree[u] -= 1
                if indegree[u] == 0:
                    next_layer.append(u)

        current_layer = next_layer

    if processed_count != len(all_nodes):
        # Gather nodes that are part of the cycle to provide a better error message if possible
        unprocessed = [u for u in all_nodes if indegree[u] > 0]
        raise CycleError(f"Cycle detected involving nodes: {sorted(unprocessed)}")

    return layers


def parallel_batches(deps: dict[str, list[str]]) -> list[list[str]]:
    """
    Alias for topo_layers. Returns batches that can be run in parallel.
    """
    return topo_layers(deps)


def has_cycle(deps: dict[str, list[str]]) -> bool:
    """
    Return True if the graph has a cycle, False otherwise.
    """
    try:
        topo_layers(deps)
        return False
    except CycleError:
        return True
