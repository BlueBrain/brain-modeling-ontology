import os
from rdflib import RDF
from rdflib.paths import ZeroOrMore
from rdflib.term import URIRef, BNode
import pytest
import requests
import copy

# from pyshacl import validate
import json
from bmo.utils import NXV, SHACL, SH

from bmo.schema_to_type_mapping import (
    get_shapes_in_schemas,
    get_schema_to_target_classes_2,
    get_schema_to_target_classes_1,
)


EXAMPLE_RESOURCES_DIR = "./tests/data/example_resources"


@pytest.fixture
def resource_examples(examples_dir=EXAMPLE_RESOURCES_DIR):
    resource_files = os.listdir(examples_dir)
    resource_files = [f for f in resource_files if f.endswith(".json")]
    resources = {}
    for resource_file in resource_files:
        fpath = os.path.join(examples_dir, resource_file)
        with open(fpath, "r") as sfr:
            resources[resource_file] = json.load(sfr)
    return resources


@pytest.fixture
def request_headers(token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return headers


@pytest.fixture
def registered_schemas_ids(forge_endpoint, request_headers):
    url = f"{forge_endpoint}/schemas/neurosciencegraph/datamodels"
    params = {"deprecated": False, "size": 1000}
    response = requests.get(url=url, headers=request_headers, params=params)
    if response.ok:
        return [r["@id"] for r in response.json()["_results"]]
    else:
        raise ValueError(
            f"There is a problem fetching the schemas from Nexus:\n"
            f"{response.status_code} - {response.text}"
        )


@pytest.mark.skip(reason="To be refined")
def test_get_node_shapes_in_schemas(all_schema_graphs):
    schemas_graph, _, _ = all_schema_graphs

    non_deprecated_schemas = get_shapes_in_schemas(schemas_graph)

    node_shapes = list(schemas_graph.subjects(RDF.type, SHACL.NodeShape))
    property_shapes = list(schemas_graph.subjects(RDF.type, SHACL.PropertyShape))

    not_node_or_property_shapes = [
        (schema, something)
        for (schema, something) in non_deprecated_schemas
        if something not in node_shapes and something not in property_shapes
    ]

    assert (
        len(not_node_or_property_shapes) == 0
    ), f"Invalid schemas, invalid shapes: {not_node_or_property_shapes}"


def test_get_schema_to_target_classes(all_schema_graphs, forge):
    schemas_graph, _, _ = all_schema_graphs

    schema_target_class_1 = get_schema_to_target_classes_1(schemas_graph)

    schema_target_class_2 = get_schema_to_target_classes_2(schemas_graph, forge)

    invalid_schemas_1 = [
        schema for schema, classes in schema_target_class_1.items() if len(classes) > 1
    ]
    invalid_schemas_2 = [
        schema for schema, classes in schema_target_class_2.items() if len(classes) > 1
    ]

    assert len(invalid_schemas_1) == len(invalid_schemas_2)

    assert (
        len(invalid_schemas_1) == 0
    ), f"Schemas with more than one target class, {invalid_schemas_1}"

    assert (
        len(invalid_schemas_2) == 0
    ), f"Schemas with more than one target class, {invalid_schemas_2}"


def test_all_schema_are_valid(all_schema_graphs, data_jsonld_context, ontology_list):
    _, schema_graphs_dict, schema_id_to_filepath_dict = all_schema_graphs
    jsonld_context_from_ontologies, _ = data_jsonld_context
    for schema_file, schema_content_dict in schema_graphs_dict.items():
        used_shapes = get_referenced_shapes(
            None, schema_content_dict["graph"], SH.node | SH.property
        )  # used shapes
        already_imported_schemas = []
        directly_imported_schemas, transitive_imported_schemas = get_imported_schemas(
            jsonld_context_from_ontologies,
            schema_content_dict,
            schema_graphs_dict,
            schema_id_to_filepath_dict,
            already_imported_schemas,
            expand_uri=True,
            transitive_imports=True,
            ontology_list=ontology_list,
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
                    jsonld_context_from_ontologies,
                    imported_schema_content_dict,
                    schema_graphs_dict,
                    schema_id_to_filepath_dict,
                    already_imported_schemas,
                    expand_uri=True,
                    transitive_imports=True,
                    ontology_list=ontology_list,
                )

                message = (
                    f"The schema {schema_content_dict['id']} located in {schema_file} "
                    f"imported the schema {imported_schema} "
                    + f"that recursively imports it: {transitive_imported_imported_schemas}. "
                    f"A schema should not be (recursively) imported by one of its imported schema"
                )

                assert (
                    schema_content_dict["id"]
                    not in transitive_imported_imported_schemas
                ), message

        # check imported schemas are actually used
        for imported_schema in directly_imported_schemas:
            imported_schema_content_dict = get_imported_schema_content_dict(
                schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
            )
            imported_shapes = get_referenced_shapes(
                URIRef(imported_schema),
                imported_schema_content_dict["graph"],
                NXV.shapes | (NXV.shapes / SH.property),
            )  # defined shapes

            message = (
                f"The schema {schema_content_dict['id']} located in {schema_file} "
                f"imported the schema {imported_schema} but is not using a shape from it. "
                f"Used shapes are: {used_shapes} while imported shapes are: {imported_shapes}."
                + "For each imported schema, there should be at least one used shape."
            )

            assert (len(used_shapes) == 0) or (
                len(set(used_shapes).intersection(imported_shapes)) >= 1
            ), message

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
                        imported_schema,
                        imported_schema_content_dict["graph"],
                        used_shape,
                    )
                )

            message = (
                f"The schema '{schema_content_dict['id']}' located in {schema_file} "
                f"used a shape {used_shape} defined by {imported_schema_defines_shape.count(True)}"
                + f"(imported or local) schemas. Imported schemas are: {transitive_imported_schemas}. "
                f"Each used shapes should be defined by local or imported schemas."
            )

            assert imported_schema_defines_shape.count(True) >= 1, message

    # check against SHACL of SHACL
    # https://incf.github.io/neuroshapes/contexts/schema.json


def get_imported_schemas(
    jsonld_context,
    schema_content_dict,
    schema_graphs_dict,
    schema_id_to_filepath_dict,
    already_imported_schemas=[],
    expand_uri=True,
    transitive_imports=True,
    ontology_list=[],
):
    print("what is ontology list", ontology_list)
    imported_schemas = set()
    transitive_imported_schemas = set()
    if schema_content_dict["id"] not in already_imported_schemas:
        already_imported_schemas.append(schema_content_dict["id"])
        if "imports" in schema_content_dict:
            imported_schemas = {
                jsonld_context.expand(i)
                for i in schema_content_dict["imports"]
                if i not in ontology_list
            }
            transitive_imported_schemas.update(imported_schemas)
            if transitive_imports:
                for imported_schema in imported_schemas:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                    imported_schema_content_dict = schema_graphs_dict[
                        imported_schema_file
                    ]
                    i_p, t_i_s = get_imported_schemas(
                        jsonld_context,
                        imported_schema_content_dict,
                        schema_graphs_dict,
                        schema_id_to_filepath_dict,
                        already_imported_schemas,
                        expand_uri,
                        transitive_imports,
                        ontology_list,
                    )
                    transitive_imported_schemas.update(t_i_s)
            already_imported_schemas.extend(list(imported_schemas))
    return imported_schemas, transitive_imported_schemas


def is_shape_defined_by_schema(schema_id, schema_graph, shape):
    schema_defines_shape = [
        NXV.shapes,
        NXV.shapes
        / SH["and"]
        * ZeroOrMore
        / (RDF.rest | RDF.first | RDF.rest)
        * ZeroOrMore,
        NXV.shapes
        / SH["or"]
        * ZeroOrMore
        / (RDF.rest | RDF.first | RDF.rest)
        * ZeroOrMore,
        NXV.shapes
        / SH["xone"]
        * ZeroOrMore
        / (RDF.rest | RDF.first | RDF.rest)
        * ZeroOrMore,
        NXV.shapes / SH["property"],
    ]
    # A shape is defined by a schema if it is linked to it through the "NXV.shapes" property
    # either directly or with SH["and"], SH["or"], SH["xone"] and SH["property"]
    # SH["and"], SH["or"], SH["xone"] properties being RDF lists, they need to be
    # traversed using (RDF.rest|RDF.first|RDF.rest)*ZeroOrMore

    return any(
        (URIRef(schema_id), p, shape) in schema_graph for p in schema_defines_shape
    )


def get_imported_schema_content_dict(
    schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
):
    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
    return imported_schema_content_dict


def get_referenced_shapes(schema_uri, schema_graph, sparql_path):
    defined_shapes = []
    for defined_shape in schema_graph.objects(schema_uri, sparql_path):
        if not isinstance(defined_shape, BNode):
            defined_shapes.append(defined_shape)
    return defined_shapes


@pytest.fixture(scope="session")
def schemas_classes_dicts(forge, all_schema_graphs):
    schemas_graph, schema_dict, schema_to_file_dict = all_schema_graphs
    schema_class = get_schema_to_target_classes_2(schemas_graph, forge)
    class_schema = {}
    for k, v in schema_class.items():
        if "#" in v[0]:
            kitem = v[0].split("#")[-1]
        else:
            kitem = v[0].split("/")[-1]
        class_schema[kitem] = k
    return schema_dict, schema_to_file_dict, class_schema


def check_type_in_loaded_context(
    example_file, type_, class_schema, schema_to_file_dict, schema_dict
):
    if type_ not in class_schema:
        raise ValueError(
            f"Not found {type_} in class_schema, possible keys: {class_schema.keys()}"
        )

    schema_id = class_schema[type_]
    if schema_id not in schema_to_file_dict:
        raise ValueError(
            f"Not found source file for schema with id {schema_id}, possible keys are: {schema_to_file_dict.keys()}"
        )
    schema_file = schema_to_file_dict[schema_id]
    class_id = schema_dict[schema_file]
    if not class_id:
        raise ValueError(
            f"Class id for {type_} is {class_id}, with example_file: {example_file}, {schema_dict.keys()}"
        )

    schema_jsonld = schema_dict[schema_file]["jsonld"]
    assert schema_id == schema_jsonld["@id"]

    if not schema_file:
        raise ValueError(
            f"Schema for the type {type_} was not found with class id {class_id}."
        )

    if schema_file not in schema_dict:
        raise ValueError(
            f"Schema file {schema_file} was not found in the schema dictionary: {schema_dict.keys()}"
        )


def test_schemas_validate_examples(
    schemas_classes_dicts, forge_rdfmodel, resource_examples, new_context_path
):
    "Check that schemas validate againts sample resources"
    # Get resources and classes mapping
    schema_dict, schema_to_file_dict, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split(".json")[0]]
        check_type_in_loaded_context(
            example_file, type_, class_schema, schema_to_file_dict, schema_dict
        )
        schema_id = class_schema[type_]
        # Run validation
        try:
            print(" --- Validating ", example_file)
            # change the context iri to be the one of the directory
            example["@context"] = new_context_path
            example_resource = forge_rdfmodel._store.service.to_resource(example)
            forge_rdfmodel.validate(example_resource, type_=type_)
            if not example_resource._last_action.succeeded:
                raise ValueError(
                    f"Local validation failed: {example_resource._last_action.message}, {type_}"
                )
        except Exception as e:
            raise ValueError(
                f"The example from file {example_file} \n {example}\n"
                f"failed to validate schema {schema_id}, with error {e}"
            )


def test_schemas_validate_wrong_examples(
    schemas_classes_dicts, forge_rdfmodel, resource_examples, new_context_path
):
    "Check that schemas validate againts sample resources"
    # Get resources and classes mapping
    _, _, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    def _try_validation(
        forge, example, example_file, example_resource, type_, schema_id
    ):
        try:
            # change the context iri to be the one of the directory
            forge.validate(example_resource, type_=type_)
            if example_resource._last_action.succeeded:
                raise ValueError(
                    f"Local validation should have failed for type: {type_}"
                )
        except Exception as e:
            raise ValueError(
                f"Error in {example}:\n {json.dumps(forge.as_json(example_resource), indent=4)}\n"
                f"validated againts schema {schema_id}, with error {e}"
            )

    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split(".json")[0]]
        schema_id = class_schema[type_]
        example["@context"] = new_context_path
        example_resource = forge_rdfmodel._store.service.to_resource(example)
        # test wrong brainRegion
        if hasattr(example_resource, "brainLocation"):
            correct_brain_region = copy.deepcopy(
                example_resource.brainLocation.brainRegion
            )
            # change to wrong id
            example_resource.brainLocation.brainRegion.id = (
                "http://example_hierarchy_allen/549"
            )
            # Check validation FAILS
            _try_validation(
                forge_rdfmodel,
                example,
                example_file,
                example_resource,
                type_,
                schema_id,
            )
            # # Change to wrong label
            # example_resource.brainLocation.brainRegion.id = correct_brain_region.id
            # example_resource.brainLocation.brainRegion.label = (
            #     "For Under Capacity Keys of Brain Stem"
            # )
            # # Check validation FAILS
            # _try_validation(
            #     forge_rdfmodel,
            #     example,
            #     example_file,
            #     example_resource,
            #     type_,
            #     schema_id,
            # )
            example_resource.brainLocation.brainRegion = correct_brain_region
        # test wrong subject
        if hasattr(example_resource, "subject"):
            correct_subject = copy.deepcopy(example_resource.subject)
            # Change to wrong id
            example_resource.subject.species.id = "http://example.obolibrary.org/Mouse"
            # Check validation FAILS
            _try_validation(
                forge_rdfmodel,
                example,
                example_file,
                example_resource,
                type_,
                schema_id,
            )
            # # Change  to wrong label
            # example_resource.subject.species.id = correct_subject.species.id
            # example_resource.subject.species.label = (
            #     "A species label not in the ontology"
            # )
            # # Check validation FAILS
            # _try_validation(
            #     forge_rdfmodel,
            #     example,
            #     example_file,
            #     example_resource,
            #     type_,
            #     schema_id,
            # )
            # test wrong strain
            if hasattr(example_resource.subject, "strain"):
                example_resource.subject.strain.id = (
                    "http://example.obolibrary.org/AWrongStrainId"
                )
                # Check validation FAILS
                _try_validation(
                    forge_rdfmodel,
                    example,
                    example_file,
                    example_resource,
                    type_,
                    schema_id,
                )
                # # Change the label
                # example_resource.subject.strain.id = correct_subject.strain.id
                # example_resource.subject.strain.label = (
                #     "A strain label not in the ontology"
                # )
                # # Check validation FAILS
                # _try_validation(
                #     forge_rdfmodel,
                #     example,
                #     example_file,
                #     example_resource,
                #     type_,
                #     schema_id,
                # )
            example_resource.subject = correct_subject
