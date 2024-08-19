from contextlib import redirect_stdout
import io
import os
import json

from collections import defaultdict
from typing import Dict, Optional, Tuple
from rdflib import RDF
from rdflib.paths import ZeroOrMore
from rdflib.term import URIRef, BNode
import pytest
import requests


from kgforge.core import Resource, KnowledgeGraphForge
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
        used_shapes = _get_referenced_shapes(
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
            assert imported_schema in schema_id_to_filepath_dict, f"{imported_schema} couldn't be found in any file"
            # there is a file within which the imported_schema is defined
            # check no recursive schema import
            imported_schema_content_dict = _get_imported_schema_content_dict(
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
                    f"that recursively imports it: {transitive_imported_imported_schemas}. "
                    f"A schema should not be (recursively) imported by one of its imported schema"
                )

                assert (
                    schema_content_dict["id"]
                    not in transitive_imported_imported_schemas
                ), message

        # check imported schemas are actually used
        for imported_schema in directly_imported_schemas:
            imported_schema_content_dict = _get_imported_schema_content_dict(
                schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
            )
            imported_shapes = _get_referenced_shapes(
                URIRef(imported_schema),
                imported_schema_content_dict["graph"],
                NXV.shapes | (NXV.shapes / SH.property),
            )  # defined shapes

            message = (
                f"The schema {schema_content_dict['id']} located in {schema_file} "
                f"imported the schema {imported_schema} but is not using a shape from it. "
                f"Used shapes are: {used_shapes} while imported shapes are: {imported_shapes}."
                "For each imported schema, there should be at least one used shape."
            )

            assert (len(used_shapes) == 0) or (
                len(set(used_shapes).intersection(imported_shapes)) >= 1
            ), message

        # check used schemas are defined locally or imported
        for used_shape in used_shapes:
            imported_schema_defines_shape = []
            imported_schema_defines_shape.append(
                _is_shape_defined_by_schema(
                    schema_content_dict["id"], schema_content_dict["graph"], used_shape
                )
            )
            for imported_schema in set(transitive_imported_schemas):
                imported_schema_content_dict = _get_imported_schema_content_dict(
                    schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
                )
                imported_schema_defines_shape.append(
                    _is_shape_defined_by_schema(
                        imported_schema,
                        imported_schema_content_dict["graph"],
                        used_shape,
                    )
                )

            message = (
                f"The schema '{schema_content_dict['id']}' located in {schema_file} "
                f"used a shape {used_shape} defined by {imported_schema_defines_shape.count(True)} "
                f"(imported or local) schemas. Imported schemas are: {transitive_imported_schemas}. "
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
    # print("what is ontology list", ontology_list)
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


def _is_shape_defined_by_schema(schema_id, schema_graph, shape):
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


def _get_imported_schema_content_dict(
    schema_graphs_dict, schema_id_to_filepath_dict, imported_schema
):
    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
    return imported_schema_content_dict


def _get_referenced_shapes(schema_uri, schema_graph, sparql_path):
    return [
        defined_shape
        for defined_shape in schema_graph.objects(schema_uri, sparql_path)
        if not isinstance(defined_shape, BNode)
    ]


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
) -> Tuple[bool, Optional[str]]:
    if type_ not in class_schema:
        return False, f"Not found {type_} in class_schema, possible keys: {class_schema.keys()}"

    schema_id = class_schema[type_]
    if schema_id not in schema_to_file_dict:
        return False, f"Not found source file for schema with id {schema_id}, possible keys are: {schema_to_file_dict.keys()}"

    schema_file = schema_to_file_dict[schema_id]
    class_id = schema_dict[schema_file]

    if not class_id:
        return False, f"Class id for {type_} is {class_id}, with example_file: {example_file}, {schema_dict.keys()}"

    schema_jsonld = schema_dict[schema_file]["jsonld"]

    if schema_id != schema_jsonld["@id"]:
        return False, f"{schema_id} != {schema_jsonld['@id']}"

    if not schema_file:
        return False, f"Schema for the type {type_} was not found with class id {class_id}."

    if schema_file not in schema_dict:
        return False, f"Schema file {schema_file} was not found in the schema dictionary: {schema_dict.keys()}"

    return True, None


def test_schemas_validate_examples(
    schemas_classes_dicts, forge_rdfmodel, resource_examples, new_context_path
):
    """Check that schemas validate against sample resources"""
    # Get resources and classes mapping
    schema_dict, schema_to_file_dict, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    errs = {}
    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split(".json")[0]]

        success, err_message = check_type_in_loaded_context(
            example_file, type_, class_schema, schema_to_file_dict, schema_dict
        )
        if not success:
            errs[example_file] = err_message
            continue

        schema_id = class_schema[type_]

        success, msg = _try_validation(
            forge=forge_rdfmodel, example_file=example_file, example=example, type_=type_,
            schema_id=schema_id, success_expected=True, new_context_path=new_context_path
        )

        if not success:
            errs[example_file] = msg

    assert len(errs) == 0, json.dumps(errs, indent=4)


def _try_validation(
        forge: KnowledgeGraphForge, example_file: str,
        example: Dict, type_: str, schema_id: str, success_expected: bool, new_context_path: str,
        resource_edit=lambda x: x
):
    # change the context iri to be the one of the directory
    example["@context"] = new_context_path
    example_resource = forge._store.service.to_resource(example)
    example_resource = resource_edit(example_resource)

    if example_resource is None:
        return True, None

    try:
        f = io.StringIO()
        with redirect_stdout(f):
            forge.validate(example_resource, type_=type_)
        success = example_resource._last_action.succeeded == success_expected

        if not success:
            err_message = f"Local validation failed: {example_resource._last_action.message}, {type_}" \
                if success_expected else f"Local validation should have failed for type: {type_}"
        else:
            err_message = None

        return success, err_message

    except Exception as e:
        jsonified_resource = json.dumps(forge.as_json(example_resource), indent=4)

        return False, f"The example from file {example_file} \n {jsonified_resource}\n" \
                      f"raised an error when attempting to validate schema {schema_id}, with error {e}"


def test_schemas_validate_wrong_examples(
    schemas_classes_dicts, forge_rdfmodel, resource_examples, new_context_path
):
    """Check that schemas validate against sample resources"""
    # Get resources and classes mapping
    _, _, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    def edit_brain_region(res: Resource) -> Optional[Resource]:
        if hasattr(res, "brainLocation"):
            res.brainLocation.brainRegion.id = "http://example_hierarchy_allen/549"
            return res
        return None

    def edit_subject_species(res: Resource) -> Optional[Resource]:
        if hasattr(res, "subject"):
            if hasattr(res.subject, "species"):
                res.subject.species.id = "http://example.obolibrary.org/Mouse"
                return res
        return None

    def edit_subject_strain(res: Resource) -> Optional[Resource]:
        if hasattr(res, "subject"):
            if hasattr(res.subject, "strain"):
                res.subject.strain.id = "http://example.obolibrary.org/AWrongStrainId"
                return res
        return None

    errs = defaultdict(list)

    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split(".json")[0]]
        schema_id = class_schema[type_]

        # test wrong brainRegion
        # change to wrong id
        success_flag_a, msg_a = _try_validation(
            forge=forge_rdfmodel, example_file=example_file, example=example, type_=type_,
            schema_id=schema_id, success_expected=False, new_context_path=new_context_path,
            resource_edit=edit_brain_region
        )

        if not success_flag_a:
            errs[example_file].append(msg_a + " - Wrong brain region was still successful")

        # # Change to wrong label
        # example_resource.brainLocation.brainRegion.id = correct_brain_region.id
        # example_resource.brainLocation.brainRegion.label = (
        #     "For Under Capacity Keys of Brain Stem"
        # )
        # # Check validation FAILS
        # _try_validation(example_file, example_resource, type_, schema_id)

        # test wrong subject species
        # Change to wrong id
        success_flag_b, msg_b = _try_validation(
            forge=forge_rdfmodel, example_file=example_file, example=example, type_=type_,
            schema_id=schema_id, success_expected=False, new_context_path=new_context_path,
            resource_edit=edit_subject_species
        )
        if not success_flag_b:
            errs[example_file].append(msg_b + " - Wrong subject species was still successful")

        # # Change to wrong label
        # example_resource.subject.species.id = correct_subject.species.id
        # example_resource.subject.species.label = (
        #     "A species label not in the ontology"
        # )
        # # Check validation FAILS
        # _try_validation(example_file, example_resource, type_, schema_id)

        # test wrong subject strain
        # Change to wrong id
        success_flag_c, msg_c = _try_validation(
            forge=forge_rdfmodel, example_file=example_file, example=example, type_=type_,
            schema_id=schema_id, success_expected=False, new_context_path=new_context_path,
            resource_edit=edit_subject_strain
        )

        if not success_flag_c:
            errs[example_file].append(msg_c + " - Wrong subject strain was still successful")

        # # Change the label
        # example_resource.subject.strain.id = correct_subject.strain.id
        # example_resource.subject.strain.label = (
        #     "A strain label not in the ontology"
        # )
        # # Check validation FAILS
        # _try_validation(example_file, example_resource, type_, schema_id)

    assert len(errs) == 0, json.dumps(errs, indent=4)
