from rdflib import URIRef, RDF

from bmo.schema_to_type_mapping import (
    get_shapes_in_schemas,
    get_schema_to_target_classes_2,
    get_schema_to_target_classes_1
)

from bmo.utils import NXV, SHACL
import pytest


@pytest.mark.skip(reason="To be refined")
def test_get_node_shapes_in_schemas(all_schema_graphs):
    schemas_graph, _, _ = all_schema_graphs

    non_deprecated_schemas = get_shapes_in_schemas(schemas_graph)

    node_shapes = list(schemas_graph.subjects(RDF.type, SHACL.NodeShape))
    property_shapes = list(schemas_graph.subjects(RDF.type, SHACL.PropertyShape))

    not_node_or_property_shapes = [
        (schema, something) for (schema, something) in non_deprecated_schemas
        if something not in node_shapes and something not in property_shapes
    ]

    assert len(not_node_or_property_shapes) == 0, \
        f"Invalid schemas, invalid shapes: {not_node_or_property_shapes}"


def test_get_schema_to_target_classes(all_schema_graphs, forge):
    schemas_graph, _, _ = all_schema_graphs

    schema_target_class_1 = get_schema_to_target_classes_1(schemas_graph)

    schema_target_class_2 = get_schema_to_target_classes_2(schemas_graph, forge)

    invalid_schemas_1 = [
        schema for schema, classes in schema_target_class_1.items()
        if len(classes) > 1
    ]
    invalid_schemas_2 = [
        schema for schema, classes in schema_target_class_2.items()
        if len(classes) > 1
    ]

    assert len(invalid_schemas_1) == len(invalid_schemas_2)

    assert len(invalid_schemas_1) == 0, \
        f"Schemas with more than one target class, {invalid_schemas_1}"

    assert len(invalid_schemas_2) == 0, \
        f"Schemas with more than one target class, {invalid_schemas_2}"
