from nexus.runtime.understanding import (
    normalize_understanding_structure,
)


def normalize(value):
    return normalize_understanding_structure(
        {
            "mutation_policy": value,
        }
    )["mutation_policy"]


def test_read_only_aliases():
    assert normalize("read only") == "READ_ONLY"
    assert normalize("read-only") == "READ_ONLY"
    assert normalize("readonly") == "READ_ONLY"


def test_mutating_aliases():
    assert normalize("mutating") == "MUTATING"
    assert normalize("mutation") == "MUTATING"
    assert normalize("write") == "MUTATING"


def test_unsure_aliases():
    assert normalize("unsure") == "UNSURE"
    assert normalize("unknown") == "UNSURE"


def test_unknown_semantic_value_is_not_invented():
    assert normalize("banana") == "banana"
