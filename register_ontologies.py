import argparse
import glob
import json
import os
from copy import deepcopy

import rdflib
from kgforge.core.commons import Context

import bmo_tools.ontologies as bmo

from kgforge.core import KnowledgeGraphForge

from kgforge.specializations.mappings import DictionaryMapping

from rdflib import Namespace, RDF, OWL, RDFS

from bmo_tools.utils import remove_non_ascii, PREFIX_MAPPINGS

import nexussdk as nexus

WEBPROTEGE_TO_NEXUS = {
    # Target ontology ID's to define
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes": "https://bbp.epfl.ch/ontologies/core/molecular-systems",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/c0f3a3e7-6dd2-4802-a00a-61ae366a35bb/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mba",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/7515dc12-ce84-4eea-ba8e-6262670ac741/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/etypes",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/6a23494a-360c-4152-9e81-fd9828f44db9/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mtypes",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/ea484e60-5a27-4790-8f2a-e2975897f407/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/stimulustypes/",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/ea484e60-5a27-4790-8f2a-e2975897f407/edit/Classes?selection=Class(%3Chttps://bbp.epfl.ch/ontologies/core/bmo/ElectricalStimulus%3E)": "https://bbp.epfl.ch/ontologies/core/bmo/ElectricalStimulus",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/d4ee40c6-4131-4915-961d-51a5c587c667/edit/Classes": "https://bbp.epfl.ch/ontologies/core/efeatures",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/a9878003-7d0b-4f75-aad8-7de3eeeacd73/edit/Classes": "https://bbp.epfl.ch/ontologies/core/mfeatures",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/648aec19-2694-4ab2-9231-3905e2bd3d38/edit/Classes": "https://bbp.epfl.ch/ontologies/core/metypes",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/c9128328-fe63-4e5e-8ec1-c7f0f0f33d19/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/speciestaxonomy/",
    "urn:webprotege:ontology:b307df0e-232d-4e20-9467-80e0733ecbec/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/celltypes",
    "urn:webprotege:ontology:b307df0e-232d-4e20-9467-80e0733ecbec": "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/celltypes",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/ChemicalReaction%3E)": "https://neuroshapes.org/ChemicalReaction",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/Molecule%3E)": "https://neuroshapes.org/Molecule",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/ReactionKineticParameter%3E)": "https://neuroshapes.org/ReactionKineticParameter",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/ReactionRateEquation%3E)": "https://neuroshapes.org/ReactionRateEquation",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/SteadyStateMolecularConcentration%3E)": "https://neuroshapes.org/SteadyStateMolecularConcentration",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/Complex%3E)": "https://neuroshapes.org/Complex",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/Metabolite%3E)": "https://neuroshapes.org/Metabolite",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes?selection=Class(%3Chttps://neuroshapes.org/Protein%3E)": "https://neuroshapes.org/Protein",
    "https://bbp.epfl.ch/nexus/webprotege/#projects/ea484e60-5a27-4790-8f2a-e2975897f407/edit/Classes?selection=Class(%3Chttps://bbp.epfl.ch/ontologies/core/bmo/ElectricalStimulus%3E)": "https://bbp.epfl.ch/ontologies/core/bmo/ElectricalStimulus"
}

JSONLD_CONTEXT_IRI = "https://neuroshapes.org"
JSONLD_SCHEMA_CONTEXT_IRI = "https://incf.github.io/neuroshapes/contexts/schema.json"

def define_arguments():
    """
    Defines the arguments of the Python script

    :return: the argument parser
    :rtype: ArgumentParser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment',
                        choices=["production", "staging"],
                        help='In which Nexus environment should the script run?',
                        required=True)
    parser.add_argument(
        "--token", help="The nexus token", type=str, required=True)
    parser.add_argument(
        "--tag", help="The tag of the ontology. Defaults to None",
        default=None, type=str)

    parser.add_argument(
        "--bucket", help="The Nexus org/project in which to push the ontologies and the schemas.",
        default=None, type=str, required=True)

    parser.add_argument(
        "--ontology_dir", help="The path to load ontologies from.",
        default=None, type=str, required=True)

    parser.add_argument(
        "--schema_dir", help="The path to load schemas from.",
        default=None, type=str, required=True)
    parser.add_argument(
        "--transformed_schema_path", help="The path to write and load schemas transformed for use by ontodocs.",
        default="./ontologies/bbp/shapes_jsonld_expanded", type=str)

    return parser


def execute_registration(forge, ontology_path, ontology_graph, all_class_resources_mapped_dict, new_forge_context, new_jsonld_context_dict, tag=None):
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param ontology_graph: the rdflib.Graph() of the ontology to register
    :param all_class_resources_mapped_dict: all ontology classes
    :param new_forge_context: the newly generated forge context object
    :param new_jsonld_context_dict: the newly generated forge context dictionary
    :param tag: optional tag
    :return:
    """

    ontology = bmo.find_ontology_resource(ontology_graph)

    # Enforce a label for the ontology
    ontology_labels = list(ontology_graph.objects(ontology, RDFS.label))
    if len(ontology_labels) == 0:
        bmo.add_ontology_label(ontology_graph, ontology)


    # Adds a nsg:defines relationships from the ontology to each of owl:Class it contains. Note that nsg:defines is not
    # a reverse property of RDFS:isDefinedBy.
    bmo.add_defines_relation(ontology_graph, ontology)

    # Consider keeping restrictions in ontology and remove them in classes
    #bmo.restrictions_to_triples(ontology_graph)
    ontology = bmo.replace_is_defined_by_uris(ontology_graph, WEBPROTEGE_TO_NEXUS, str(ontology))

    class_resources_mapped = _get_classes_in_ontology(ontology_graph, all_class_resources_mapped_dict)

    bmo.register_ontology(forge, ontology_graph, new_forge_context, new_jsonld_context_dict, ontology_path, tag, class_resources_mapped)
    #bmo.remove_defines_relation(ontology_graph, ontology)


def _get_classes_in_ontology(ontology_graph, all_class_resources_mapped_dict):
    return [all_class_resources_mapped_dict.get(str(cls)) for cls in ontology_graph.subjects(RDF.type, OWL.Class)]


def parse_and_register_ontologies(arguments):
    """
    Parses the arguments and registers the ontologies and schemas

    :param arguments: The arguments namespace
    :type arguments: Namespace
    :return:
    """
    environment = arguments.environment
    token = arguments.token
    tag = arguments.tag
    ontology_dir = arguments.ontology_dir
    BUCKET = arguments.bucket
    schema_dir = arguments.schema_dir
    transformed_schema_path = arguments.transformed_schema_path

    if environment == "staging":
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            "Environment argument must be either \"staging\" or \"production\" ")

    forge = KnowledgeGraphForge("config/forge-config.yml", endpoint=endpoint, bucket=BUCKET, token=token, debug=True)
    forge_schema = KnowledgeGraphForge("config/forge-schema-config.yml", endpoint=endpoint, bucket=BUCKET, token=token, debug=True)


    print(f"Loading the ontologies")
    all_ontology_graphs = initialise_graph()
    ontology_graphs_dict = load_ontologies(ontology_dir, all_ontology_graphs)
    print(f"Finished loading {len(ontology_graphs_dict)} ontologies with {len(all_ontology_graphs)} triples")
    print(f"Loading the schema")
    print(f"\t Updating the schema JSON-LD context because the schemas refer the JSONLD context")

    with open ("./jsonldcontext/schema.json", "r") as f:
        new_jsonld_schema_context_document = json.load(f)

    new_jsonld_schema_context = Context(document=new_jsonld_schema_context_document["@context"], iri=new_jsonld_schema_context_document['@id'])

    new_jsonld_schema_context_resource = forge_schema.from_json(new_jsonld_schema_context_document)
    schema_context = forge_schema.retrieve(JSONLD_SCHEMA_CONTEXT_IRI)
    new_jsonld_schema_context_resource._self = schema_context._store_metadata._self
    nexus.resources.update(forge.as_json(new_jsonld_schema_context_resource), schema_context._store_metadata._rev)
    print(f"Finished updating JSON-LD schema context {new_jsonld_schema_context_document['@id']}")

    all_schema_graphs = initialise_graph()
    schema_graphs_dict, schema_id_to_filepath_dict = load_schemas(schema_dir, transformed_schema_path, forge_schema, all_schema_graphs, recursive=True,
                                      save_transformed_schema=True)

    print(f"Finished loading {len(schema_graphs_dict)} schemas with {len(all_schema_graphs)} triples")

    print(f"Collecting JSON-LD data context from all ontologies and from all schemas")

    with open ("./jsonldcontext/neuroshapes_org.json", "r") as f:
        forge_model_context_document = json.load(f)
    forge_model_context = Context(document=forge_model_context_document["@context"], iri=forge_model_context_document['@id'])

    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(all_ontology_graphs, forge_model_context)
    new_jsonld_context, schema_errors = bmo.build_context_from_schema(all_schema_graphs, new_jsonld_context)
    errors = []
    errors.extend(ontology_errors)
    errors.extend(schema_errors)
    if len(errors) > 0:
        raise ValueError(f"Failed to build context from ontologies in {ontology_dir} and schemas in {schema_dir}: {errors}")

    print(f"Finished collecting JSON-LD data context from ontologies in {ontology_dir}  and schemas in {schema_dir}.")


    new_jsonld_context_document = new_jsonld_context.document
    new_jsonld_context_document["@id"] = JSONLD_CONTEXT_IRI
    new_jsonld_context.iri = JSONLD_CONTEXT_IRI
    new_jsonld_context_resource = forge.from_json(new_jsonld_context_document)
    print(f"Updating JSON-LD context {new_jsonld_context_document['@id']}")
    with open("./new_jsonld_context_resource.json", "w") as f:
        json.dump(forge.as_json(new_jsonld_context_resource), f)

    context = forge.retrieve(JSONLD_CONTEXT_IRI)
    new_jsonld_context_resource._self = context._store_metadata._self
    nexus.resources.update(forge.as_json(new_jsonld_context_resource), context._store_metadata._rev)
    print(f"Finished updating JSON-LD context {new_jsonld_context_document['@id']}")

    print("Preparing ontology classes")
    new_jsonld_context_dict = new_jsonld_context_document["@context"]

    new_jsonld_context_dict["label"] = {
        "@id": "rdfs:label",
        "@language": "en"
    }

    new_jsonld_context_dict["prefLabel"] = {
        "@id": "skos:prefLabel",
        "@language": "en"
    }

    new_jsonld_context_dict["altLabel"] = {
        "@id": "skos:altLabel",
        "@language": "en"
    }

    new_jsonld_context_dict["definition"] = {
        "@id": "skos:definition",
        "@language": "en"
    }
    new_jsonld_context_dict["notation"] = {
        "@id": "skos:notation",
        "@language": "en"
    }

    bmo.replace_is_defined_by_uris(all_ontology_graphs, WEBPROTEGE_TO_NEXUS)
    class_ids, class_jsons, all_blank_node_triples = bmo.frame_classes(all_ontology_graphs, new_jsonld_context, new_jsonld_context_dict)
    print(f"Got {len(class_jsons)} non mapped classes")
    print(class_jsons[15])
    class_resources_mapped = forge.map(data=class_jsons,
                                       mapping=DictionaryMapping.load("./config/mappings/term-to-resource-mapping.hjson"),
                                       na=None)
    print(class_resources_mapped[15])
    print(f"Got {len(class_resources_mapped)} mapped classes")
    all_class_resources_mapped_dict = dict(zip(class_ids, class_resources_mapped))
    print(f"Finished preparing {len(class_resources_mapped)} ontology classes")

    with open("./class_json.json", "w") as f:
        json.dump(class_jsons, f)

    print(f"Registering {len(list(schema_graphs_dict.keys()))} schemas")
    already_registered = []
    for schema_file, schema_content in schema_graphs_dict.items():
        register_schemas(forge_schema, schema_file, schema_content, schema_graphs_dict, schema_id_to_filepath_dict,
                         all_schema_graphs, new_jsonld_schema_context,tag=tag,
                         already_registered=already_registered)
    print(f"Registration finished for all schemas.")

    for ontology_path, ontology_graph in ontology_graphs_dict.items():
        print(f"Registering ontology: {ontology_path}")
        execute_registration(forge, ontology_path, ontology_graph, all_class_resources_mapped_dict, new_jsonld_context, new_jsonld_context_dict, tag)
        print(f"Registration finished for ontology: {ontology_path}")
    
    print(f"Registering {len(class_jsons)} classes")
    class_errors = bmo.register_classes(forge, class_jsons, tag)
    print(f"Registering finished for all {len(class_jsons)} classes with errors: {class_errors}")


def register_schemas(forge, schema_file, schema_content, schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graph, jsonld_schema_context, tag, already_registered=[]):
    if schema_content["resource"].id not in already_registered:
        if "imports" in schema_content:
            imported_schemas = [jsonld_schema_context.expand(i) for i in schema_content["imports"]]
            for imported_schema in imported_schemas:
                if imported_schema in schema_id_to_filepath_dict:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                else:
                    raise ValueError(f"The schema {imported_schema} (imported from {schema_content['id']} in {schema_file}) was not found.")
                imported_schema_content = schema_graphs_dict[imported_schema_file]
                register_schemas(forge, imported_schema_file, imported_schema_content, schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graph, jsonld_schema_context, tag, already_registered=already_registered)
                already_registered.extend(imported_schema_content["resource"].id)
        bmo._register_schema(forge, schema_file, schema_content["resource"], all_schema_graph, jsonld_schema_context, tag)
        already_registered.append(schema_content["resource"].id)


def initialise_graph():
    graph = rdflib.Graph()
    for prefix, mapping in PREFIX_MAPPINGS.items():
        graph.bind(prefix, Namespace(mapping))
    return graph


def load_schemas(schema_dir, transformed_schema_path, forge, all_schema_graphs, recursive=False, save_transformed_schema = False):
    schemas_files = glob.glob(schema_dir, recursive=recursive)
    schema_graphs_dict={}
    schema_id_to_filepath_dict={}
    for schema_file in schemas_files:
        schema_file_path_parts = schema_file.split("/")

        with open(schema_file, 'r') as sfr:
            schema_jsonld = json.load(sfr)

        original_schema_context = deepcopy(schema_jsonld["@context"])
        dict_in_schema_context = [d for d in schema_jsonld["@context"] if isinstance(d, dict)]
        schema_context = ["./jsonldcontext/schema.json"]
        schema_context.extend(dict_in_schema_context)
        schema_jsonld["@context"] = schema_context

        schema_resource = forge.from_jsonld(schema_jsonld)
        schema_jsonld_expanded = forge.as_jsonld(schema_resource, form="expanded")
        #schema_jsonld_compacted = forge.as_jsonld(schema_resource, form="compacted")
        schema_subdir = schema_file_path_parts[-2]
        schema_subdir_parent = schema_file_path_parts[-3]
        schema_jsonld_expanded_graph = rdflib.Graph().parse(data=schema_jsonld_expanded, format="json-ld")
        all_schema_graphs.parse(data=schema_jsonld_expanded, format="json-ld")

        if save_transformed_schema: #This is needed for ontodocs to be able to generate doc web app
            schema_name, schema_file_extension = os.path.splitext(schema_file_path_parts[-1])  # os.path.splitext(schema_file)
            shapes_jsonld_expanded_filename = transformed_schema_path + "/" + schema_subdir_parent + "/" + schema_subdir + "/" + schema_name + ".ttl" if schema_subdir != "commons" else transformed_schema_path + "/" + schema_subdir + "/" + schema_name + ".ttl"
            schema_jsonld_expanded_graph.serialize(shapes_jsonld_expanded_filename, format="ttl")
        schema_resource.context=original_schema_context
        schema_jsonld["@context"] = original_schema_context

        owl_imports = schema_resource.imports if hasattr(schema_resource, "imports") else []
        schema_graphs_dict[schema_file] = {"resource": schema_resource, "graph": schema_jsonld_expanded_graph, "jsonld":schema_jsonld,"imports":owl_imports, "id":schema_resource.id}
        schema_id_to_filepath_dict[schema_resource.id] = schema_file

    return schema_graphs_dict, schema_id_to_filepath_dict


def load_ontologies(ontology_dir, all_ontology_graphs):
    ontology_files = glob.glob(ontology_dir)
    ontology_files = [
        "./ontologies/bbp/bmo.ttl",
        "./ontologies/bbp/speciestaxonomy.ttl",
        "./ontologies/bbp/brainregion.ttl",
        "./ontologies/bbp/stimulustypes.ttl",
        "./ontologies/bbp/celltypes.ttl",
        "./ontologies/bbp/efeatures.ttl",
        "./ontologies/bbp/mfeatures.ttl",
        "./ontologies/bbp/molecular-systems.ttl",
        "./ontologies/bbp/data-types.ttl",
        "./ontologies/bbp/pato.ttl"
    ]
    ontology_graphs_dict={}
    errors = []
    for ontology_path in ontology_files:
        try:
            #remove_non_ascii(ontology_path)
            # read the ontology
            ontology_graph = rdflib.Graph()
            for prefix, mapping in PREFIX_MAPPINGS.items():
                ontology_graph.bind(prefix, Namespace(mapping))
            ontology_graph.parse(ontology_path, format="turtle")
            all_ontology_graphs.parse(ontology_path, format="turtle")
            ontology_graphs_dict[ontology_path] = ontology_graph
        except Exception as e:
            errors.append(f"Failed to load ontology {ontology_path}: {e}")
        if len(errors) > 0:
            raise ValueError(f"Failed to load ontologies: {errors}")
    return ontology_graphs_dict



if __name__ == "__main__":

    # defines and receives script arguments
    parser = define_arguments()
    received_args, leftovers = parser.parse_known_args()
    # registers the ontologies and the schemas
    parse_and_register_ontologies(received_args)
