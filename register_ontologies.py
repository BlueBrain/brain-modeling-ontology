import argparse

import rdflib

import bmo_tools.ontologies as bmo

from os import listdir

from kgforge.core import KnowledgeGraphForge

from ontospy import Ontospy

from os.path import isfile, join

from rdflib import Namespace


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
    parser.add_argument("--token", help="The nexus token", type=str, required=True)
    parser.add_argument("--files", nargs="+", default=[], required=False)
    parser.add_argument("--tag", help="The tag of the ontology. Defaults to None", default=None, type=str)
    return parser


def execute_registration(forge, ontology_path, tag=None):
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param tag: optional tag
    :return:
    """
    PREFIX = "https://neuroshapes.org/"
    ontologyspy = Ontospy(ontology_path, verbose=True)
    for x in ontologyspy.stats(): print(f"{x[0]}: {x[1]}")
    NSG = Namespace('https://neuroshapes.org/')
    UBERON = Namespace('http://purl.obolibrary.org/obo/UBERON_')
    SKOS = Namespace('http://www.w3.org/2004/02/skos/core#')
    OWL = Namespace('http://www.w3.org/2002/07/owl#')
    ontology_graph = rdflib.Graph()
    ontology_graph.parse(ontology_path, format="turtle")
    ontology_graph.bind('nsg', NSG)
    ontology_graph.bind('skos', SKOS)
    ontology_graph.bind('owl', OWL)
    ontology_graph.bind('UBERON', UBERON)
    ontology = bmo.find_ontology_resource(ontology_graph)

    if not ontology_graph.label(ontology):
        bmo.add_ontology_label(ontology_graph, ontology)

    bmo.add_defines_relation(ontology_graph, PREFIX)

    bmo.restrictions_to_triples(ontology_graph)

    WEBPROTEGE_TO_NEXUS = {
        # Target ontology ID's to define
        "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes": "https://bbp.epfl.ch/ontologies/lib/molecular-systems",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/facad879-18ea-4499-8f44-b154ed6c0020/edit/Classes": "https://bbp.epfl.ch/ontologies/lib/e-features",
        # Already exist in Nexus
        "https://bbp.epfl.ch/nexus/webprotege/#projects/c0f3a3e7-6dd2-4802-a00a-61ae366a35bb/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mba",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/7515dc12-ce84-4eea-ba8e-6262670ac741/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/etypes",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/6a23494a-360c-4152-9e81-fd9828f44db9/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mtypes",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/e57bffdc-40fb-4507-b23e-e7b279625a45/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/stimulustypes/"
    }

    bmo.replace_is_defined_by_uris(ontology_graph, WEBPROTEGE_TO_NEXUS)

    # context = forge.retrieve("https://neuroshapes.org")
    context = forge.retrieve("https://bbp.neuroshapes.org")
    context = forge.as_jsonld(context)["@context"]
    context["label"] = {
        "@id": "rdfs:label",
        "@language": "en"
    }

    context["prefLabel"] = {
        "@id": "skos:prefLabel",
        "@language": "en"
    }

    context["altLabel"] = {
        "@id": "skos:altLabel",
        "@language": "en"
    }

    context["definition"] = {
        "@id": "skos:definition",
        "@language": "en"
    }
    print(f"Registering ontology: {ontology_path}")
    bmo.register_ontology(forge, ontology_graph, context, ontology_path, PREFIX, tag)

    bmo.remove_defines_relation(ontology_graph, PREFIX)

    class_jsons = bmo.frame_classes(ontology_graph, context, PREFIX)
    print(f"Registering classes for ontology: {ontology_path}")
    bmo.register_classes(forge, class_jsons)
    print(f"Registration finished for ontology: {ontology_path}")


def parse_and_register_ontologies(arguments):
    """
    Parses the arguments and registers the ontologies for each turtle file

    :param arguments: The arguments namespace
    :type arguments: Namespace
    :return:
    """
    environment = arguments.environment
    token = arguments.token
    files = arguments.files
    tag = arguments.tag

    if environment == "staging":
        endpoint = "https://staging.nexus.ocp.bbp.epfl.ch/v1"
        # ontology files are all changed files that are placed under the "ontologies/" directory
        ontology_files = [file for file in files if "ontologies/bbp" in file]
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
        # ontology files are all files under ./ontologies/bbp
        ontology_path = "./ontologies/bbp"
        ontology_files = [f"{ontology_path}/{file}" for file in listdir(ontology_path) if isfile(join(ontology_path, file))]
    else:
        raise ValueError("Environment argument must be either \"staging\" or \"production\" ")

    BUCKET = "neurosciencegraph/datamodels"

    forge = KnowledgeGraphForge(
        "https://raw.githubusercontent.com/BlueBrain/nexus-forge/master/examples/notebooks/use-cases/prod-forge-nexus.yml",
        endpoint=endpoint, bucket=BUCKET, token=token)

    # for every ontology files that changed
    for ontology_filename in ontology_files:
        execute_registration(forge, ontology_filename, tag)


if __name__ == "__main__":

    # defines and receives script arguments
    parser = define_arguments()
    received_args, leftovers = parser.parse_known_args()
    # registers the ontologies
    parse_and_register_ontologies(received_args)
