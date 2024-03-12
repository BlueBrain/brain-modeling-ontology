def test_registered_schemas_local_schemas_diff(all_schema_graphs, forge):
    _, schema_graphs_dict, _ = all_schema_graphs
    local_resources = [el["resource"] for el in schema_graphs_dict.values()]

    q = "SELECT ?id WHERE {GRAPH ?g { ?id a Schema ; _deprecated false }}"
    registered_ids = set(el.id for el in forge.sparql(q, limit=None))

    local_ids = set(
        el.get_identifier() for el in local_resources
        if not el.__dict__.get("owl:deprecated", False)
    )

    local_not_registered = local_ids.difference(registered_ids)
    assert len(local_not_registered) == 0, \
        f"The following schemas were found but were not registered {local_not_registered}"

    registered_not_local = registered_ids.difference(local_ids)
    assert len(registered_not_local) == 0, \
        f"The following schemas were registered but were not found locally {registered_not_local}"
