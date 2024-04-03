import pytest


@pytest.fixture
def local_schemas_ids(all_schema_graphs):
    _, schema_graphs_dict, _ = all_schema_graphs
    local_resources = [el["resource"] for el in schema_graphs_dict.values()]
    return set(
        el.get_identifier() for el in local_resources
        if not el.__dict__.get("owl:deprecated", False)
    )


@pytest.fixture
def registered_schemas_ids(forge):
    q = "SELECT ?id WHERE {GRAPH ?g { ?id a Schema ; _deprecated false }}"
    return set(el.id for el in forge.sparql(q, limit=None))


def test_local_schemas_are_registered(local_schemas_ids, registered_schemas_ids):
    local_not_registered = local_schemas_ids.difference(registered_schemas_ids)
    assert len(local_not_registered) == 0, \
        f"The following schemas were found but were not registered {local_not_registered}"


def test_registered_schemas_are_local(local_schemas_ids, registered_schemas_ids):
    registered_not_local = registered_schemas_ids.difference(local_schemas_ids)
    assert len(registered_not_local) == 0, \
        f"The following schemas were registered but were not found locally {registered_not_local}"
