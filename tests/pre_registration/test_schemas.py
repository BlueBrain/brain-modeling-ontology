import os
from rdflib import RDF
from rdflib.paths import ZeroOrMore
from rdflib.term import URIRef, BNode
import pytest
import requests
import yaml
import copy
from kgforge.core.forge import KnowledgeGraphForge
# from pyshacl import validate
import json
from bmo.utils import NXV, SHACL, SH
from bmo.ontologies import (
    find_ontology_resource,
    replace_ontology_id,
    add_defines_relation
)
from bmo.schema_to_type_mapping import (
    get_shapes_in_schemas,
    get_schema_to_target_classes_2,
    get_schema_to_target_classes_1
)
from bmo.slim_ontologies import (
    create_slim_ontology_graph,
    get_slim_ontology_id
)


EXAMPLE_RESOURCES_DIR = './tests/data/example_resources'
WRONG_EXAMPLE_RESOURCES_DIR = './tests/data/wrong_example_resources'
NEW_JSON_CONTEXT_PATH = './jsonldcontext/new_jsonld_context.json'


@pytest.fixture
def resource_examples(examples_dir=EXAMPLE_RESOURCES_DIR):
    resource_files = os.listdir(examples_dir)
    resource_files = [f for f in resource_files if f.endswith(".json")]
    resources = {}
    for resource_file in resource_files:
        fpath = os.path.join(examples_dir, resource_file)
        with open(fpath, 'r') as sfr:
            resources[resource_file] = json.load(sfr)
    return resources


@pytest.fixture
def request_headers(token):
    headers = {'Authorization': f"Bearer {token}",
               "Content-Type": "application/json"}
    return headers


@pytest.fixture
def registered_schemas_ids(forge_endpoint, request_headers):
    url = f"{forge_endpoint}/schemas/neurosciencegraph/datamodels"
    params = {'deprecated': False, 'size': 1000}
    response = requests.get(url=url, headers=request_headers, params=params)
    if response.ok:
        return [r['@id'] for r in response.json()['_results']]
    else:
        raise ValueError(f'There is a problem fetching the schemas from Nexus:\n'
                         f'{response.status_code} - {response.text}')


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


def test_all_schema_are_valid(all_schema_graphs, data_jsonld_context, slim_ontology_list):
    schema_graphs, schema_graphs_dict, schema_id_to_filepath_dict = all_schema_graphs
    jsonld_context_from_ontologies, _ = data_jsonld_context
    slim_ontology_list = [str(el) for el in slim_ontology_list]  # before they where URIRef
    for schema_file, schema_content_dict in schema_graphs_dict.items():
        used_shapes = get_referenced_shapes(
            None, schema_content_dict["graph"], SH.node | SH.property
        )  # used shapes
        already_imported_schemas = []
        directly_imported_schemas, transitive_imported_schemas = get_imported_schemas(
            jsonld_context_from_ontologies, schema_content_dict, schema_graphs_dict,
            schema_id_to_filepath_dict, already_imported_schemas, expand_uri=True,
            transitive_imports=True, ontology_list=slim_ontology_list
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
                    transitive_imports=True, ontology_list=slim_ontology_list
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
        expand_uri=True, transitive_imports=True, ontology_list=[]
):
    print('what is ontology list', ontology_list)
    imported_schemas = set()
    transitive_imported_schemas = set()
    if schema_content_dict["id"] not in already_imported_schemas:
        already_imported_schemas.append(schema_content_dict["id"])
        if "imports" in schema_content_dict:
            imported_schemas = {jsonld_context.expand(i) for i in schema_content_dict["imports"]
                                if i not in ontology_list}
            transitive_imported_schemas.update(imported_schemas)
            if transitive_imports:
                for imported_schema in imported_schemas:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
                    i_p, t_i_s = get_imported_schemas(
                        jsonld_context, imported_schema_content_dict,
                        schema_graphs_dict, schema_id_to_filepath_dict,
                        already_imported_schemas, expand_uri, transitive_imports,
                        ontology_list
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


@pytest.fixture(scope="session")
def forge_rdfmodel(forge, all_ontology_graphs,
                   all_ontology_graph_merged_brain_region_atlas_hierarchy,
                   updated_local_jsonld_context,
                   context_path=NEW_JSON_CONTEXT_PATH):
    _, brain_region_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy
    # create tmp directory in the same place as the schemas
    tmp_dir = './tmp_shapes/'
    if not os.path.exists(tmp_dir):
        os.mkdir(tmp_dir)
    ontologies_dirpath = f'{tmp_dir}/ontologies'
    if not os.path.exists(ontologies_dirpath):
        os.mkdir(ontologies_dirpath)

    # create slim ontologies and save them to files
    _, ontology_graphs_dict = all_ontology_graphs
    for ontology_file, ontology_graph in ontology_graphs_dict.items():
        if 'brainregion' in ontology_file:  # replave the brain region graph with the merged graph
            ontology_graph = brain_region_graph
            dirpath = f"./{ontology_file.split('/')[-1].split('.')[0]}"
            dirpath_ttl = f"{dirpath}_before_slim.ttl"
            ontology_graph.serialize(destination=dirpath_ttl, format="ttl")
        ontology = find_ontology_resource(ontology_graph)
        add_defines_relation(ontology_graph, ontology)

        # Create slim version of ontologies
        slim_ontology_graph = create_slim_ontology_graph(ontology_graph)
        slim_ontology = get_slim_ontology_id(ontology)
        replace_ontology_id(slim_ontology_graph, slim_ontology)

        # Replace ontology graph id
        dirpath = f"{ontologies_dirpath}/{ontology_file.split('/')[-1].split('.')[0]}"
        dirpath_ttl = f"{dirpath}_slim.ttl"
        slim_ontology_graph.serialize(destination=dirpath_ttl, format="ttl")

    # dump the new json context
    context_document = updated_local_jsonld_context.document
    with open(context_path, 'w') as f:
        json.dump(context_document, f, indent=2)

    os.system(f'cp -r ./shapes {tmp_dir}')

    # use an existing configuration file and modify it
    with open('./config/forge-config.yml', 'r') as fc:
        config = yaml.safe_load(fc)
    config['Model']['origin'] = 'directory'
    config['Model']['source'] = f'{tmp_dir}'
    config['Model']['context']['iri'] = context_path
    config['Model']['context']['bucket'] = './jsonldcontext'

    config_path = './config/tmp-forge-config.yml'
    with open(config_path, 'w') as fo:
        yaml.safe_dump(config, fo)

    # Generate a forge instance from a directory with all schemas, ontologies and the new context
    return KnowledgeGraphForge(config_path,
                               endpoint=forge._store.endpoint,
                               bucket=forge._store.bucket,
                               token=forge._store.token)


@pytest.fixture(scope="session")
def schemas_classes_dicts(forge, all_schema_graphs):
    schemas_graph, schema_dict, schema_to_file_dict = all_schema_graphs
    schema_class = get_schema_to_target_classes_2(schemas_graph, forge)
    class_schema = {v[0].split('/')[-1]: k for k, v in schema_class.items()}
    return schema_dict, schema_to_file_dict, class_schema


def check_type_in_loaded_context(example_file, type_, class_schema, schema_to_file_dict, schema_dict):
    if type_ not in class_schema:
        raise ValueError(f"Not found {type_} in class_schema, possible keys: {class_schema.keys()}")

    schema_id = class_schema[type_]
    if schema_id not in schema_to_file_dict:
        raise ValueError(f"Not found source file for schema with id {schema_id}, possible keys are: {schema_to_file_dict.keys()}")
    schema_file = schema_to_file_dict[schema_id]
    class_id = schema_dict[schema_file]
    if not class_id:
        raise ValueError(f"Class id for {type_} is {class_id}, with example_file: {example_file}, {schema_dict.keys()}")

    schema_jsonld = schema_dict[schema_file]['jsonld']
    assert schema_id == schema_jsonld['@id']

    if not schema_file:
        raise ValueError(f"Schema for the type {type_} was not found with class id {class_id}.")

    if schema_file not in schema_dict:
        raise ValueError(f"Schema file {schema_file} was not found in the schema dictionary: {schema_dict.keys()}")


def test_schemas_validate_examples(schemas_classes_dicts,
                                   forge_rdfmodel, resource_examples,
                                   context_iri=NEW_JSON_CONTEXT_PATH):
    "Check that schemas validate againts sample resources"
    # Get resources and classes mapping
    schema_dict, schema_to_file_dict, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split('.json')[0]]
        check_type_in_loaded_context(example_file, type_, class_schema, schema_to_file_dict, schema_dict)
        schema_id = class_schema[type_]
        # Run validation
        try:
            print(" --- Validating ", example_file)
            # change the context iri to be the one of the directory
            example['@context'] = context_iri
            example_resource = forge_rdfmodel._store.service.to_resource(example)
            forge_rdfmodel.validate(example_resource, type_=type_)
            if not example_resource._last_action.succeeded:
                raise ValueError(f"Local validation failed: {example_resource._last_action.message}, {type_}")
        except Exception as e:
            raise ValueError(f"The example from file {example_file} \n {example}\n"
                             f"failed to validate schema {schema_id}, with error {e}")


def test_schemas_validate_wrong_examples(schemas_classes_dicts,
                                         forge_rdfmodel, resource_examples,
                                         context_iri=NEW_JSON_CONTEXT_PATH):
    "Check that schemas validate againts sample resources"
    # Get resources and classes mapping
    _, _, class_schema = schemas_classes_dicts
    class_lower = {k.lower(): k for k in class_schema.keys()}

    for example_file, example in resource_examples.items():
        type_ = class_lower[example_file.split('.json')[0]]
        schema_id = class_schema[type_]

        example['@context'] = context_iri
        example_resource = forge_rdfmodel._store.service.to_resource(example)
        if hasattr(example_resource, 'brainLocation'):
            old_brain_region = copy.deepcopy(example_resource.brainLocation.brainRegion)
            example_resource.brainLocation.brainRegion.id = "http://example_hierarchy_allen/549"
            # Check validation FAILS
            try:
                # change the context iri to be the one of the directory
                forge_rdfmodel.validate(example_resource, type_=type_)
                if example_resource._last_action.succeeded:
                    raise ValueError(f"Local validation should have failed for type: {type_}")
            except Exception as e:
                raise ValueError(f"Error in {example_file} \n {example}\n"
                                 f"validated againts schema {schema_id}, with error {e}")
            example_resource.brainLocation.brainRegion = old_brain_region
        # test wrong species
        if hasattr(example_resource, 'subject'):
            example_resource.subject.species.id = "http://example.obolibrary.org/Mouse"
            # Check validation FAILS
            try:
                # change the context iri to be the one of the directory
                forge_rdfmodel.validate(example_resource, type_=type_)
                if example_resource._last_action.succeeded:
                    raise ValueError(f"Local validation should have failed for type: {type_}")
            except Exception as e:
                raise ValueError(f"Error in {example_file} \n {example}\n"
                                 f"validated againts schema {schema_id}, with error {e}")
