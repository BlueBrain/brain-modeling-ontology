import argparse
import glob

import rdflib

import bmo_tools.ontologies as bmo

from kgforge.core import KnowledgeGraphForge

from kgforge.specializations.mappings import DictionaryMapping


from ontospy import Ontospy

from rdflib import Namespace

from bmo_tools.utils import remove_non_ascii, PREFIX_MAPPINGS


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


def execute_registration(forge, ontology_path, tag=None):
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param tag: optional tag
    :return:
    """
    print(f"Registering ontology: {ontology_path}")
    ontologyspy = Ontospy(ontology_path, verbose=True)
    for x in ontologyspy.stats(): print(f"{x[0]}: {x[1]}")
    # first remove non-ascii characters from ontology
    remove_non_ascii(ontology_path)
    # read the ontology
    ontology_graph = rdflib.Graph()
    for prefix, mapping in PREFIX_MAPPINGS.items():
        ontology_graph.bind(prefix, Namespace(mapping))
    ontology_graph.parse(ontology_path, format="turtle")

    ontology = bmo.find_ontology_resource(ontology_graph)

    if not ontology_graph.label(ontology):
        bmo.add_ontology_label(ontology_graph, ontology)

    bmo.add_defines_relation(ontology_graph)

    # Consider keeping restrictions in ontology and remove them in classes
    #bmo.restrictions_to_triples(ontology_graph)

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

    bmo.replace_is_defined_by_uris(ontology_graph, WEBPROTEGE_TO_NEXUS, str(ontology))

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
    class_jsons = bmo.frame_classes(forge, ontology_graph, context)

    print(f"Got {len(class_jsons)} non mapped classes")
    class_resources_mapped = forge.map(data=class_jsons,
                                   mapping=DictionaryMapping.load("./mappings/term-to-resource-mapping.hjson"), na="None")

    print(f"Got {len(class_resources_mapped)} mapped classes")
    bmo.register_ontology(forge, ontology_graph, context, ontology_path, tag, class_resources_mapped)
    bmo.remove_defines_relation(ontology_graph)
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
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
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
