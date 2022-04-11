import argparse
import glob

import rdflib

import bmo_tools.ontologies as bmo

from kgforge.core import KnowledgeGraphForge

from ontospy import Ontospy

from rdflib import Namespace

from bmo_tools.utils import remove_non_ascii


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
    return parser


PREFIX_MAPPINGS = {
    "mso": "https://bbp.epfl.ch/ontologies/core/molecular-systems/",
    "GO": "http://purl.obolibrary.org/obo/GO_",
    "dc": "http://purl.org/dc/elements/1.1/",
    "sh": "http://www.w3.org/ns/shacl#",
    "bmo": "https://bbp.epfl.ch/ontologies/core/bmo/",
    "bmc": "https://bbp.epfl.ch/ontologies/core/bmc/",
    "nsg": "https://neuroshapes.org/",
    "nxv": "https://bluebrain.github.io/nexus/vocabulary/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xml": "http://www.w3.org/XML/1998/namespace/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "shsh": "http://www.w3.org/ns/shacl-shacl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "vann": "http://purl.org/vocab/vann/",
    "void": "http://rdfs.org/ns/void#",
    "uberon": "http://purl.obolibrary.org/obo/UBERON_",
    "schema": "http://schema.org/",
    "dcterms": "http://purl.org/dc/terms/",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "NCBITaxon_TAXON": "http://purl.obolibrary.org/obo/NCBITaxon#_",
    "stim": "https://bbp.epfl.ch/neurosciencegraph/ontologies/stimulustypes/",
    "datashapes": "https://neuroshapes.org/dash/",
    "commonshapes": "https://neuroshapes.org/commons/",
    "ilx": "http://uri.interlex.org/base/ilx_",
    "efe": "https://bbp.epfl.ch/ontologies/core/efeatures/",
    "et": "http://bbp.epfl.ch/neurosciencegraph/ontologies/etypes/",
    "mt": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mtypes/",
    "tt": "http://bbp.epfl.ch/neurosciencegraph/ontologies/ttypes/",
    "EFO": "http://www.ebi.ac.uk/efo/EFO_",
    "RS": "http://purl.obolibrary.org/obo/RS_",
    "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_"
}


def execute_registration(forge, ontology_path, tag=None):
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param tag: optional tag
    :return:
    """
    ontologyspy = Ontospy(ontology_path, verbose=True)
    for x in ontologyspy.stats(): print(f"{x[0]}: {x[1]}")
    # first remove non-ascii characters from ontology
    remove_non_ascii(ontology_path)
    # read the ontology
    ontology_graph = rdflib.Graph()
    ontology_graph.parse(ontology_path, format="turtle")
    for prefix, mapping in PREFIX_MAPPINGS.items():
        ontology_graph.bind(prefix, Namespace(mapping))

    ontology = bmo.find_ontology_resource(ontology_graph)

    if not ontology_graph.label(ontology):
        bmo.add_ontology_label(ontology_graph, ontology)

    bmo.add_defines_relation(ontology_graph)

    bmo.restrictions_to_triples(ontology_graph)

    WEBPROTEGE_TO_NEXUS = {
        # Target ontology ID's to define
        "https://bbp.epfl.ch/nexus/webprotege/#projects/755556fa-73b1-4863-96af-e8359109b4ef/edit/Classes": "https://bbp.epfl.ch/ontologies/core/molecular-systems",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/c0f3a3e7-6dd2-4802-a00a-61ae366a35bb/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mba",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/7515dc12-ce84-4eea-ba8e-6262670ac741/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/etypes",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/6a23494a-360c-4152-9e81-fd9828f44db9/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mtypes",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/ea484e60-5a27-4790-8f2a-e2975897f407/edit/Classes": "http://bbp.epfl.ch/neurosciencegraph/ontologies/stimulustypes/",
        "https://bbp.epfl.ch/nexus/webprotege/#projects/d4ee40c6-4131-4915-961d-51a5c587c667/edit/Classes": "https://bbp.epfl.ch/ontologies/core/efeatures"
    }

    bmo.replace_is_defined_by_uris(ontology_graph, WEBPROTEGE_TO_NEXUS)

    # context = forge.retrieve("https://neuroshapes.org")
    context = forge.retrieve("https://neuroshapes.org")
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
    bmo.register_ontology(forge, ontology_graph, context, ontology_path, tag)
    bmo.remove_defines_relation(ontology_graph)

    class_jsons = bmo.frame_classes(ontology_graph, context)
    print(f"Registering classes for ontology: {ontology_path}")
    bmo.register_classes(forge, class_jsons, tag)
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
    tag = arguments.tag

    # ontology files are all turtle files that are placed under the
    # "ontologies/bbp" directory
    ontology_files = glob.glob(f"./ontologies/bbp/*.ttl")

    if environment == "staging":
        endpoint = "https://staging.nexus.ocp.bbp.epfl.ch/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            "Environment argument must be either \"staging\" or \"production\" ")

    BUCKET = "neurosciencegraph/datamodels"

    forge = KnowledgeGraphForge(
        # "https://raw.githubusercontent.com/BlueBrain/nexus-forge/master/examples/notebooks/use-cases/prod-forge-nexus.yml",
        "config/forge-config.yml",
        endpoint=endpoint, bucket=BUCKET, token=token, debug=True)

    # for every ontology files that changed
    for ontology_filename in ontology_files:
        execute_registration(forge, ontology_filename, tag)


if __name__ == "__main__":

    # defines and receives script arguments
    parser = define_arguments()
    received_args, leftovers = parser.parse_known_args()
    # registers the ontologies
    parse_and_register_ontologies(received_args)
