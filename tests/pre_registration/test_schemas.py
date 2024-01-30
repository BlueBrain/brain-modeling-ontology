from rdflib import RDF, SH
from rdflib.paths import ZeroOrMore
from rdflib.term import URIRef, BNode
import pytest
from bmo.utils import NXV
from bmo.utils import SHACL
from bmo.schema_to_type_mapping import (
    get_shapes_in_schemas,
    get_schema_to_target_classes_2,
    get_schema_to_target_classes_1
)


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


def test_all_schema_are_valid(all_schema_graphs, data_jsonld_context):
    schema_graphs, schema_graphs_dict, schema_id_to_filepath_dict = all_schema_graphs
    jsonld_context_from_ontologies, _ = data_jsonld_context
    for schema_file, schema_content_dict in schema_graphs_dict.items():
        used_shapes = get_referenced_shapes(
            None, schema_content_dict["graph"], SH.node | SH.property
        )  # used shapes
        already_imported_schemas = []
        directly_imported_schemas, transitive_imported_schemas = get_imported_schemas(
            jsonld_context_from_ontologies, schema_content_dict, schema_graphs_dict,
            schema_id_to_filepath_dict, already_imported_schemas, expand_uri=True,
            transitive_imports=True
        )
        for imported_schema in transitive_imported_schemas:
            # check imported schemas are defined
            assert imported_schema in schema_id_to_filepath_dict
            # there is a file within which the imported_schema is defined
            # check no recursive schema import
            imported_schema_content_dict = get_imported_schema_content_dict(
                schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
            )
            if "imports" in imported_schema_content_dict:
                already_imported_schemas = []
                _, transitive_imported_imported_schemas = get_imported_schemas(
                    jsonld_context_from_ontologies, imported_schema_content_dict,
                    schema_graphs_dict,
                    schema_id_to_filepath_dict, already_imported_schemas, expand_uri=True,
                    transitive_imports=True
                )

                message = f"The schema {schema_content_dict['id']} located in {schema_file} " \
                          f"imported the schema {imported_schema} " + \
                          f"that recursively imports it: {transitive_imported_imported_schemas}. " \
                          f"A schema should not be (recursively) imported by one of its imported schema"

                assert schema_content_dict["id"] not in transitive_imported_imported_schemas, message

        # check imported schemas are actually used
        for imported_schema in directly_imported_schemas:
            imported_schema_content_dict = get_imported_schema_content_dict(
                schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
            )
            imported_shapes = get_referenced_shapes(
                URIRef(imported_schema),
                imported_schema_content_dict["graph"],
                NXV.shapes | (NXV.shapes / SH.property)
            )  # defined shapes

            message = f"The schema {schema_content_dict['id']} located in {schema_file} " \
                      f"imported the schema {imported_schema} but is not using a shape from it. " \
                      f"Used shapes are: {used_shapes} while imported shapes are: {imported_shapes}." + \
                      "For each imported schema, there should be at least one used shape."

            assert (len(used_shapes) == 0) or (
                        len(set(used_shapes).intersection(imported_shapes)) >= 1), message

        # check used schemas are defined locally or imported
        for used_shape in used_shapes:
            imported_schema_defines_shape = []
            imported_schema_defines_shape.append(
                is_shape_defined_by_schema(
                    schema_content_dict["id"], schema_content_dict["graph"], used_shape
                )
            )
            for imported_schema in set(transitive_imported_schemas):
                imported_schema_content_dict = get_imported_schema_content_dict(
                    schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
                )
                imported_schema_defines_shape.append(
                    is_shape_defined_by_schema(
                        imported_schema, imported_schema_content_dict["graph"], used_shape
                    )
                )

            message = f"The schema '{schema_content_dict['id']}' located in {schema_file} " \
                      f"used a shape {used_shape} defined by {imported_schema_defines_shape.count(True)}" + \
                      f"(imported or local) schemas. Imported schemas are: {transitive_imported_schemas}. " \
                      f"Each used shapes should be defined by local or imported schemas."

            assert imported_schema_defines_shape.count(True) >= 1, message

    # check against SHACL of SHACL
    # https://incf.github.io/neuroshapes/contexts/schema.json


def get_imported_schemas(
        jsonld_context, schema_content_dict, schema_graphs_dict,
        schema_id_to_filepath_dict, already_imported_schemas=[],
        expand_uri=True, transitive_imports=True
):
    imported_schemas = set()
    transitive_imported_schemas = set()
    if schema_content_dict["id"] not in already_imported_schemas:
        already_imported_schemas.append(schema_content_dict["id"])
        if "imports" in schema_content_dict:
            imported_schemas = {jsonld_context.expand(i) for i in schema_content_dict["imports"]}
            transitive_imported_schemas.update(imported_schemas)
            if transitive_imports:
                for imported_schema in imported_schemas:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
                    i_p, t_i_s = get_imported_schemas(
                        jsonld_context, imported_schema_content_dict,
                        schema_graphs_dict, schema_id_to_filepath_dict,
                        already_imported_schemas, expand_uri, transitive_imports
                    )
                    transitive_imported_schemas.update(t_i_s)
            already_imported_schemas.extend(list(imported_schemas))
    return imported_schemas, transitive_imported_schemas


def is_shape_defined_by_schema(schema_id, schema_graph, shape):
    schema_defines_shape = [
        NXV.shapes,
        NXV.shapes / SH["and"] * ZeroOrMore / (RDF.rest | RDF.first | RDF.rest) * ZeroOrMore,
        NXV.shapes / SH["or"] * ZeroOrMore / (RDF.rest | RDF.first | RDF.rest) * ZeroOrMore,
        NXV.shapes / SH["xone"] * ZeroOrMore / (RDF.rest | RDF.first | RDF.rest) * ZeroOrMore,
        NXV.shapes / SH["property"]
    ]
    # A shape is defined by a schema if it is linked to it through the "NXV.shapes" property
    # either directly or with SH["and"], SH["or"], SH["xone"] and SH["property"]
    # SH["and"], SH["or"], SH["xone"] properties being RDF lists, they need to be
    # traversed using (RDF.rest|RDF.first|RDF.rest)*ZeroOrMore

    return any(
        (URIRef(schema_id), p, shape) in schema_graph
        for p in schema_defines_shape
    )


def get_imported_schema_content_dict(schema_graphs_dict, schema_id_to_filepath_dict, imported_schema):
    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
    return imported_schema_content_dict


def get_referenced_shapes(schema_uri, schema_graph, sparql_path):
    defined_shapes = []
    for defined_shape in schema_graph.objects(schema_uri, sparql_path):
        if not isinstance(defined_shape, BNode):
            defined_shapes.append(defined_shape)
    return defined_shapes
