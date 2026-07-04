"""T5.1: DAG scheduler — topo layering, cycle detection, parallel batches."""

import pytest

from cld.dag import CycleError, has_cycle, parallel_batches, topo_layers


def test_empty():
    assert topo_layers({}) == []


def test_single_no_deps():
    assert topo_layers({"A": []}) == [["A"]]


def test_linear_chain():
    deps = {"C": ["B"], "B": ["A"], "A": []}
    assert topo_layers(deps) == [["A"], ["B"], ["C"]]


def test_layer_groups_independent_in_sorted_order():
    # A and B independent (layer 0), C depends on both (layer 1)
    deps = {"C": ["A", "B"], "B": [], "A": []}
    layers = topo_layers(deps)
    assert layers[0] == ["A", "B"]  # sorted within layer
    assert layers[1] == ["C"]


def test_dep_only_id_treated_as_layer0():
    # "A" appears only as a dependency, never a key
    deps = {"B": ["A"]}
    layers = topo_layers(deps)
    assert layers[0] == ["A"]
    assert layers[1] == ["B"]


def test_every_id_appears_once():
    deps = {"D": ["B", "C"], "C": ["A"], "B": ["A"], "A": []}
    flat = [x for layer in topo_layers(deps) for x in layer]
    assert sorted(flat) == ["A", "B", "C", "D"]
    assert len(flat) == len(set(flat))  # no dupes


def test_parallel_batches_matches_topo_layers():
    deps = {"B": ["A"], "A": []}
    assert parallel_batches(deps) == topo_layers(deps)


def test_cycle_raises():
    deps = {"A": ["B"], "B": ["A"]}
    with pytest.raises(CycleError):
        topo_layers(deps)


def test_self_loop_is_cycle():
    with pytest.raises(CycleError):
        topo_layers({"A": ["A"]})


def test_has_cycle_true_false():
    assert has_cycle({"A": ["B"], "B": ["A"]}) is True
    assert has_cycle({"A": ["A"]}) is True
    assert has_cycle({"B": ["A"], "A": []}) is False
    assert has_cycle({}) is False
