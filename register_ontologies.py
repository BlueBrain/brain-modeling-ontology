import argparse
import glob
import json
import os
from copy import deepcopy
from typing import Dict, Any, List, Tuple
from rdflib import PROV, Literal, Namespace, RDF, OWL, RDFS, Graph, term
from kgforge.core.commons import Context
from kgforge.core import KnowledgeGraphForge, Resource
from kgforge.specializations.mappings import DictionaryMapping

import bmo.ontologies as bmo
from bmo.utils import (
    BMO, BRAIN_REGION_ONTOLOGY_URI, MBA, NSG, NXV, SCHEMAORG, PREFIX_MAPPINGS, SKOS
)

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
    parser.add_argument(
        '--environment',
        choices=["production", "staging"],
        help='In which Nexus environment should the script run?',
        required=True
    )
    parser.add_argument(
        "--token", help="The nexus token", type=str, required=True
    )
    parser.add_argument(
        "--tag", help="The tag of the ontology. Defaults to None",
        default=None, type=str
    )

    parser.add_argument(
        "--bucket", help="The Nexus org/project in which to push the ontologies and the schemas.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--ontology_dir", help="The path to load ontologies from.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--schema_dir", help="The path to load schemas from.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--transformed_schema_path",
        help="The path to write and load schemas transformed for use by ontodocs.",
        default="./ontologies/bbp/shapes_jsonld_expanded", type=str
    )

    parser.add_argument(
        "--atlas_parcellation_ontology", help="The atlas parcellation ontology.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--atlas_parcellation_ontology_version", help="The atlas parcellation ontology version.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--atlas_parcellation_ontology_bucket", help="The atlas parcellation ontology bucket.",
        default=None, type=str, required=True
    )

    return parser


def execute_registration(
        forge: KnowledgeGraphForge,
        ontology_path: str,
        ontology_graph: Graph,
        all_class_resources_mapped_dict: Dict,
        all_class_resources_framed_dict: Dict,
        new_forge_context: Context,
        new_jsonld_context_dict: Dict,
        brain_region_generated_classes: List[str],
        atlas_release_id: str,
        atlas_release_version: int,
        atlas_parcellation_ontology_id: str,
        tag=None
):
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param ontology_graph: the Graph() of the ontology to register
    :param all_class_resources_mapped_dict: all ontology classes
    :param all_class_resources_framed_dict:
    :param new_forge_context: the newly generated forge context object
    :param new_jsonld_context_dict: the newly generated forge context dictionary
    :param brain_region_generated_classes:
    :param atlas_release_id:
    :param atlas_release_version:
    :param atlas_parcellation_ontology_id:
    :param tag: optional tag
    :return:
    """

    ontology = bmo.find_ontology_resource(ontology_graph)

    # Enforce a label for the ontology
    ontology_labels = list(ontology_graph.objects(ontology, RDFS.label))
    if len(ontology_labels) == 0:
        bmo.add_ontology_label(ontology_graph, ontology)

    # Adds a nsg:defines relationships from the ontology to each of owl:Class
    # it contains. Note that nsg:defines is not a reverse property of RDFS:isDefinedBy.
    bmo.add_defines_relation(ontology_graph, ontology)

    # Consider keeping restrictions in ontology and remove them in classes
    # bmo.restrictions_to_triples(ontology_graph)
    ontology = bmo.replace_is_defined_by_uris(ontology_graph, WEBPROTEGE_TO_NEXUS, str(ontology))

    class_resources_mapped = _get_classes_in_ontology(
        all_class_resources_mapped_dict, ontology_graph.subjects(RDF.type, OWL.Class)
    )
    class_resources_framed = _get_classes_in_ontology(
        all_class_resources_framed_dict, ontology_graph.subjects(RDF.type, OWL.Class)
    )

    if str(ontology) == BRAIN_REGION_ONTOLOGY_URI:
        brain_region_generated_classes_resources_framed = _get_classes_in_ontology(
            all_class_resources_framed_dict, brain_region_generated_classes
        )

        class_resources_framed.update(
            {k: v
             for k, v in brain_region_generated_classes_resources_framed.items()
             if k not in class_resources_framed}
        )
        ontology_graph.add(
            (term.URIRef(BRAIN_REGION_ONTOLOGY_URI), NSG.atlasRelease, term.URIRef(atlas_release_id))
        )
        ontology_graph.add(
            (term.URIRef(atlas_release_id), NXV.rev, Literal(atlas_release_version))
        )
        ontology_graph.add(
            (term.URIRef(atlas_release_id), RDF.type, NSG.BrainAtlasRelease)
        )

        atlas_parcellation_ontology_derivation_bNode, \
            atlas_parcellation_ontology_derivation_triples = _create_bnode_triples_from_value(
            {
                RDF.type: PROV.Derivation,
                PROV.entity: term.URIRef(atlas_parcellation_ontology_id)
            }
        )

        ontology_graph.add(
            (term.URIRef(BRAIN_REGION_ONTOLOGY_URI), NSG.derivation,
             atlas_parcellation_ontology_derivation_bNode)
        )

        ontology_graph.add(
            (term.URIRef(atlas_parcellation_ontology_id), RDF.type, NSG.ParcellationOntology)
        )

        atlasRelease_derivation_bNode, atlasRelease_derivation_triples = _create_bnode_triples_from_value(
            {RDF.type: PROV.Derivation, PROV.entity: term.URIRef(atlas_release_id)}
        )

        ontology_graph.add(
            (term.URIRef(BRAIN_REGION_ONTOLOGY_URI), NSG.derivation, atlasRelease_derivation_bNode)
        )

    bmo.register_ontology(
        forge,
        ontology_graph,
        new_forge_context,
        new_jsonld_context_dict,
        ontology_path,
        list(class_resources_mapped.values()),
        list(class_resources_framed.values()),
        str(ontology),
        tag
    )
    # bmo.remove_defines_relation(ontology_graph, ontology)


def _get_classes_in_ontology(all_class_resources_dict, uriref_iterator):
    return {
        cls: all_class_resources_dict.get(str(cls))
        for cls in uriref_iterator
        if str(cls) in all_class_resources_dict
    }


def prepare_update_jsonld_context(
        forge: KnowledgeGraphForge, new_jsonld_context_json, jsonld_context_iri
):
    new_jsonld_context_resource = forge.from_jsonld(new_jsonld_context_json)
    existing_jsonld_context_resource = forge.retrieve(jsonld_context_iri)
    new_jsonld_context_resource._store_metadata = existing_jsonld_context_resource._store_metadata
    return new_jsonld_context_resource


def parse_and_register_ontologies(arguments: argparse.Namespace):
    """
    Parses the arguments and registers the ontologies and schemas

    :param arguments: The arguments namespace
    :type arguments: argparse.Namespace
    :return:
    """
    environment = arguments.environment
    token = arguments.token
    tag = arguments.tag
    ontology_dir = arguments.ontology_dir
    bucket = arguments.bucket
    schema_dir = arguments.schema_dir
    transformed_schema_path = arguments.transformed_schema_path
    atlas_parcellation_ontology = arguments.atlas_parcellation_ontology
    atlas_parcellation_ontology_version = arguments.atlas_parcellation_ontology_version
    atlas_parcellation_ontology_bucket = arguments.atlas_parcellation_ontology_bucket

    if environment == "staging":
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            "Environment argument must be either \"staging\" or \"production\" ")

    forge = KnowledgeGraphForge(
        "config/forge-config.yml", endpoint=endpoint,
        bucket=bucket, token=token, debug=True
    )

    forge_schema = KnowledgeGraphForge(
        "config/forge-schema-config.yml", endpoint=endpoint,
        bucket=bucket, token=token, debug=True
    )

    print(f"Loading the ontologies")
    all_ontology_graphs: Graph = initialise_graph()
    ontology_graphs_dict = load_ontologies(ontology_dir, all_ontology_graphs)

    print(
        f"Finished loading {len(ontology_graphs_dict)} "
        f"ontologies with {len(all_ontology_graphs)} triples"
    )
    print(f"Loading the schema")
    print(f"\t Updating the schema JSON-LD context because the schemas refer the JSONLD context")

    with open("./jsonldcontext/schema.json", "r") as f:
        new_jsonld_schema_context_document = json.load(f)

    new_jsonld_schema_context_resource = prepare_update_jsonld_context(
        forge_schema,
        new_jsonld_schema_context_document,
        JSONLD_SCHEMA_CONTEXT_IRI
    )

    forge_schema.update(new_jsonld_schema_context_resource)
    print(f"Finished updating JSON-LD schema context {new_jsonld_schema_context_document['@id']}")

    all_schema_graphs: Graph = initialise_graph()
    schema_graphs_dict, schema_id_to_filepath_dict = load_schemas(
        schema_dir,
        transformed_schema_path,
        forge_schema,
        all_schema_graphs,
        recursive=True,
        save_transformed_schema=True
    )

    print(
        f"Finished loading {len(schema_graphs_dict)} schemas with {len(all_schema_graphs)} triples")

    print(f"Collecting JSON-LD data context from all ontologies and from all schemas")

    with open("./jsonldcontext/neuroshapes_org.json", "r") as f:
        forge_model_context_document = json.load(f)

    forge_model_context = Context(
        document=forge_model_context_document["@context"],
        iri=forge_model_context_document['@id']
    )

    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(
        all_ontology_graphs, forge_model_context
    )

    new_jsonld_schema_context, schema_errors = bmo.build_context_from_schema(
        all_schema_graphs, new_jsonld_context
    )

    errors = []
    errors.extend(ontology_errors)
    errors.extend(schema_errors)

    if len(errors) > 0:
        raise ValueError(
            f"Failed to build context from ontologies in {ontology_dir} "
            f"and schemas in {schema_dir}: {errors}"
        )

    print(
        f"Finished collecting JSON-LD data context from ontologies "
        f"in {ontology_dir} and schemas in {schema_dir}."
    )

    new_jsonld_context_document: Dict = new_jsonld_context.document
    new_jsonld_context_document["@id"] = JSONLD_CONTEXT_IRI
    new_jsonld_context.iri = JSONLD_CONTEXT_IRI

    print(f"Updating JSON-LD context {new_jsonld_context_document['@id']}")

    new_jsonld_context_resource = prepare_update_jsonld_context(
        forge, new_jsonld_context_document, JSONLD_CONTEXT_IRI
    )
    with open("./new_jsonld_context_resource.json", "w") as f:
        json.dump(forge.as_json(new_jsonld_context_resource), f)
    forge.update(new_jsonld_context_resource)

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

    print("Merging brain region ontology with atlas hierarchy")

    forge_atlas = KnowledgeGraphForge(
        "config/forge-config-new.yml", endpoint=endpoint,
        bucket=atlas_parcellation_ontology_bucket, token=token, debug=True
    )
    # Waiting for a single version (tag) across all the atlas dataset to be
    # made available, _rev will be used.
    version = int(atlas_parcellation_ontology_version) \
        if atlas_parcellation_ontology_version is not None \
        else atlas_parcellation_ontology_version

    atlas_hierarchy = forge_atlas.retrieve(atlas_parcellation_ontology, version=version)

    atlas_hierarchy_jsonld_distribution = [
        distrib for distrib in atlas_hierarchy.distribution
        if distrib.encodingFormat == "application/ld+json"
    ]

    atlas_hierarchy_jsonld_distribution = atlas_hierarchy_jsonld_distribution[0]

    forge_atlas.download(
        atlas_hierarchy_jsonld_distribution, follow="contentUrl", path=".", overwrite=True
    )

    atlas_hierarchy_ontology_graph = Graph().parse(
        atlas_hierarchy_jsonld_distribution.name, format="json-ld"
    )

    triples_to_add, triples_to_remove = _merge_ontology(
        atlas_hierarchy_ontology_graph,
        ontology_graphs_dict["./ontologies/bbp/brainregion.ttl"],
        all_ontology_graphs,
        [SCHEMAORG.hasPart, SCHEMAORG.isPartOf,
         RDFS.label, SKOS.prefLabel, SKOS.notation, SKOS.altLabel, MBA.atlas_id,
         MBA.color_hex_triplet,
         MBA.graph_order, MBA.hemisphere_id,
         MBA.st_level, SCHEMAORG.identifier,
         BMO.representedInAnnotation,
         BMO.regionVolumeRatioToWholeBrain,
         BMO.regionVolume]
    )

    print(
        f"Finished merging brain region ontology with atlas hierarchy:"
        f" {len(triples_to_add.values())} triples were added to the brain region ontology "
        f"for {len(triples_to_add)} brain regions and from the atlas hierarchy "
        f"while {len(triples_to_remove.values())} triples were removed from the brain "
        f"region ontology for {len(triples_to_remove)} brain regions."
    )

    class_ids, class_jsons, all_blank_node_triples, brain_region_generated_classes =\
        bmo.frame_classes(
            all_ontology_graphs,
            new_jsonld_context,
            new_jsonld_context_dict,
            atlas_hierarchy.atlasRelease.id,
            atlas_hierarchy.atlasRelease._rev
        )
    print(f"Got {len(class_jsons)} non mapped classes")

    all_class_resources_framed_dict = dict(zip(class_ids, class_jsons))

    class_resources_mapped = forge.map(
        data=class_jsons,
        mapping=DictionaryMapping.load("./config/mappings/term-to-resource-mapping.hjson"),
        na=None
    )

    print(f"Got {len(class_resources_mapped)} mapped classes")
    all_class_resources_mapped_dict = dict(zip(class_ids, class_resources_mapped))
    print(f"Finished preparing {len(class_resources_mapped)} ontology classes")

    with open("./class_json.json", "w") as f:
        json.dump(class_jsons, f)

    print(f"Registering {len(list(schema_graphs_dict.keys()))} schemas")
    already_registered = []

    for schema_file, schema_content in schema_graphs_dict.items():
        register_schemas(
            forge_schema,
            schema_file,
            schema_content,
            schema_graphs_dict,
            schema_id_to_filepath_dict,
            all_schema_graphs,
            new_jsonld_schema_context,
            tag=tag,
            already_registered=already_registered
        )

    print(f"Registration finished for all schemas.")

    for ontology_path, ontology_graph in ontology_graphs_dict.items():
        print(f"Registering ontology: {ontology_path}")

        execute_registration(
            forge=forge,
            ontology_path=ontology_path,
            ontology_graph=ontology_graph,
            all_class_resources_mapped_dict=all_class_resources_mapped_dict,
            all_class_resources_framed_dict=all_class_resources_framed_dict,
            new_forge_context=new_jsonld_context,
            new_jsonld_context_dict=new_jsonld_context_dict,
            brain_region_generated_classes=brain_region_generated_classes,
            atlas_release_id=atlas_hierarchy.atlasRelease.id,
            atlas_release_version=atlas_hierarchy.atlasRelease._rev,
            atlas_parcellation_ontology_id=atlas_parcellation_ontology, tag=tag
        )
        print(f"Registration finished for ontology: {ontology_path}")

    print(f"Registering {len(class_jsons)} classes")
    class_errors = bmo.register_classes(forge, class_jsons, tag)
    print(f"Registering finished for all {len(class_jsons)} classes with errors: {class_errors}")


def _merge_ontology(
        from_ontology_graph,
        to_ontology_graph,
        to_another_graph,
        what_property_to_merge
):
    # merge hierarchy from atlas with this brain region:
    # make sure atlas hierarchy, labels, notation, identifier, ... is fully included in bmo

    triples_to_add = {}
    triples_to_remove = {}
    for prop in what_property_to_merge:
        for from_s, from_p, from_o in from_ontology_graph.triples((None, prop, None)):
            if str(from_s) not in triples_to_add:
                triples_to_add[str(from_s)] = set()
            if str(from_s) not in triples_to_remove:
                triples_to_remove[str(from_s)] = set()

            if (from_s, from_p, None) in to_ontology_graph:
                for to_s, to_p, to_o in to_ontology_graph.triples((from_s, from_p, None)):
                    if from_p != SCHEMAORG.identifier:
                        if (
                                from_p == BMO.regionVolume or
                                from_p == BMO.regionVolumeRatioToWholeBrain
                        ) and str(from_o) != "":

                            bNode, triples = _create_bnode_triples_from_value({
                                SCHEMAORG.value: from_o,
                                SCHEMAORG.unitCode: Literal("cubic micrometer")
                            })
                            triples_to_add[str(from_s)].update(triples)
                            triples_to_add[str(from_s)].add((from_s, from_p, bNode))
                            triples_to_remove[str(from_s)].update((to_s, to_p, to_o))
                        elif str(from_o) != "":
                            triples_to_add[str(from_s)].add((from_s, from_p, from_o))
                            triples_to_remove[str(from_s)].add((to_s, to_p, to_o))
            else:
                if (
                        from_p == BMO.regionVolume or
                        from_p == BMO.regionVolumeRatioToWholeBrain
                ) and str(from_o) != "":  # check atlas pipeline value when the brain region
                    # is not in the volume (currently '' is used)

                    bNode, triples = _create_bnode_triples_from_value({
                        SCHEMAORG.value: from_o,
                        SCHEMAORG.unitCode: Literal("cubic micrometer")
                    })
                    triples_to_add[str(from_s)].update(triples)
                    triples_to_add[str(from_s)].add((from_s, from_p, bNode))
                elif str(from_o) != "":
                    triples_to_add[str(from_s)].add((from_s, from_p, from_o))

                if isinstance(from_o, term.URIRef):
                    for from_o_s, from_o_p, from_o_o in \
                            from_ontology_graph.triples((from_o, None, None)):

                        if str(from_o_s) not in triples_to_add:
                            triples_to_add[str(from_o_s)] = set()

                        if from_o_p not in [BMO.layers, BMO.adjacentTo, BMO.continuousWith,
                                            BMO.hasLayerLocationPhenotype] \
                                and from_o_p not in what_property_to_merge:
                            # will be merged once the data format is okay

                            triples_to_add[str(from_o_s)].add((from_o_s, from_o_p, from_o_o))
            triples_to_add[str(from_s)].add((from_s, RDFS.subClassOf, NSG.BrainRegion))
            triples_to_add[str(from_s)].add((from_s, RDF.type, OWL.Class))

    for k, v in triples_to_remove.items():
        for t in v:
            to_ontology_graph.remove(t)
            to_another_graph.remove(t)
    for k, v in triples_to_add.items():
        for t in v:
            to_ontology_graph.add(t)
            to_another_graph.add(t)

    return triples_to_add, triples_to_remove


def _create_bnode_triples_from_value(
        prop_uriref_to_value_dict: Dict
) -> Tuple[term.BNode, List[Tuple[term.BNode, Any, Any]]]:

    triples = []
    bNode = term.BNode()
    for prop_uriref, value in prop_uriref_to_value_dict.items():
        triples.append((bNode, prop_uriref, value))

    return bNode, triples


def register_schemas(
        forge: KnowledgeGraphForge,
        schema_file,
        schema_content,
        schema_graphs_dict,
        schema_id_to_filepath_dict,
        all_schema_graph,
        jsonld_schema_context,
        tag,
        already_registered=[]
):
    if schema_content["resource"].id not in already_registered:
        if "imports" in schema_content:
            imported_schemas = [jsonld_schema_context.expand(i) for i in schema_content["imports"]]
            for imported_schema in imported_schemas:
                if imported_schema in schema_id_to_filepath_dict:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                else:
                    raise ValueError(
                        f"The schema {imported_schema} (imported from {schema_content['id']} "
                        f"in {schema_file}) was not found."
                    )
                imported_schema_content = schema_graphs_dict[imported_schema_file]

                register_schemas(
                    forge,
                    schema_file=imported_schema_file,
                    schema_content=imported_schema_content,
                    schema_graphs_dict=schema_graphs_dict,
                    schema_id_to_filepath_dict=schema_id_to_filepath_dict,
                    all_schema_graph=all_schema_graph,
                    jsonld_schema_context=jsonld_schema_context, tag=tag,
                    already_registered=already_registered
                )

                already_registered.extend(imported_schema_content["resource"].id)

        bmo._register_schema(
            forge, schema_file, schema_content["resource"], all_schema_graph,
            jsonld_schema_context, tag
        )
        already_registered.append(schema_content["resource"].id)


def initialise_graph() -> Graph:
    graph = Graph()
    for prefix, mapping in PREFIX_MAPPINGS.items():
        graph.bind(prefix, Namespace(mapping))
    return graph


def load_schemas(
        schema_dir: str,
        transformed_schema_path: str,
        forge: KnowledgeGraphForge,
        all_schema_graphs: Graph,
        recursive=False,
        save_transformed_schema=False

) -> Tuple[Dict[str, Dict], Dict[str, str]]:

    schemas_files: List[str] = glob.glob(schema_dir, recursive=recursive)

    schema_graphs_dict = {}
    schema_id_to_filepath_dict = {}

    for schema_file in schemas_files:

        with open(schema_file, 'r') as sfr:
            schema_jsonld = json.load(sfr)

        schema_file_path_parts = schema_file.split("/")
        schema_subdir = schema_file_path_parts[-2]
        schema_subdir_parent = schema_file_path_parts[-3]
        schema_name, _ = os.path.splitext(schema_file_path_parts[-1])

        original_schema_context = deepcopy(schema_jsonld["@context"])
        dict_in_schema_context = [d for d in schema_jsonld["@context"] if isinstance(d, dict)]
        schema_context = ["./jsonldcontext/schema.json"]
        schema_context.extend(dict_in_schema_context)
        schema_jsonld["@context"] = schema_context

        schema_resource: Resource = forge.from_jsonld(schema_jsonld)
        schema_jsonld_expanded: Dict = forge.as_jsonld(schema_resource, form="expanded")

        schema_jsonld_expanded_graph = Graph().parse(data=schema_jsonld_expanded, format="json-ld")
        all_schema_graphs.parse(data=schema_jsonld_expanded, format="json-ld")

        # This is needed for ontodocs to be able to generate doc web app
        if save_transformed_schema:
            os.makedirs(transformed_schema_path, exist_ok=True)

            shapes_jsonld_expanded_filename = os.path.join(
                transformed_schema_path,
                schema_subdir_parent if schema_subdir != "commons" else "",
                schema_subdir,
                schema_name + ".ttl"
            )

            schema_jsonld_expanded_graph.serialize(shapes_jsonld_expanded_filename, format="ttl")

        schema_resource.context = original_schema_context
        schema_jsonld["@context"] = original_schema_context

        owl_imports = schema_resource.imports if hasattr(schema_resource, "imports") else []

        schema_graphs_dict[schema_file] = {
            "resource": schema_resource,
            "graph": schema_jsonld_expanded_graph,
            "jsonld": schema_jsonld,
            "imports": owl_imports,
            "id": schema_resource.id
        }
        schema_id_to_filepath_dict[schema_resource.id] = schema_file

    return schema_graphs_dict, schema_id_to_filepath_dict


def load_ontologies(ontology_dir: str, all_ontology_graphs: Graph):
    # ontology_files = glob.glob(ontology_dir)
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
        "./ontologies/bbp/parameters.ttl",
        "./ontologies/bbp/pato.ttl"
    ]
    ontology_graphs_dict = {}
    errors = []
    for ontology_path in ontology_files:
        try:
            # remove_non_ascii(ontology_path)
            # read the ontology
            ontology_graph = Graph()
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
