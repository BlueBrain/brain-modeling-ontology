import argparse
import json
import copy
from typing import Dict, Any, List, Tuple, Optional
from rdflib import PROV, Literal, RDF, OWL, RDFS, Graph, term
from kgforge.core.commons import Context
from kgforge.core import KnowledgeGraphForge, Resource
from kgforge.specializations.mappings import DictionaryMapping

import bmo.ontologies as bmo
import bmo.registration as bmo_registration
from bmo.argument_parsing import define_arguments
from bmo.loading import DATA_JSONLD_CONTEXT_PATH, SCHEMA_JSONLD_CONTEXT_PATH, load_ontologies, load_schemas

from bmo.utils import (
    BMO, BRAIN_REGION_ONTOLOGY_URI, MBA, NSG, NXV, SCHEMAORG, SKOS, _get_ontology_annotation_lang_context, CELL_TYPE_ONTOLOGY_URI
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
}

# "urn:webprotege:ontology:b307df0e-232d-4e20-9467-80e0733ecbec/edit/Classes"
# in none of the ontology files

JSONLD_DATA_CONTEXT_IRI = "https://neuroshapes.org"
JSONLD_SCHEMA_CONTEXT_IRI = "https://incf.github.io/neuroshapes/contexts/schema.json"


def _initialize_forge_objects(endpoint, token, input_bucket, atlas_parcellation_ontology_bucket):
    def get_forge_object(config_path, selected_bucket):
        return KnowledgeGraphForge(
            config_path, endpoint=endpoint, bucket=selected_bucket, token=token, debug=True
        )

    forge = get_forge_object("config/forge-config.yml", input_bucket)
    forge_schema = get_forge_object("config/forge-schema-config.yml", input_bucket)
    forge_atlas = get_forge_object("config/forge-config-new.yml",
                                   atlas_parcellation_ontology_bucket)

    return forge, forge_schema, forge_atlas


def execute_ontology_registration(
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
        data_update: bool,
        tag=None
) -> Tuple[str, Dict]:
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
    :return: A tuple (the ontology id, the framed JSON payload of the regstered ontology)
    """

    print(f"Registering ontology {ontology_path} - Start")

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
        _update_brainregion_graph(ontology_graph, class_resources_framed, all_class_resources_framed_dict, brain_region_generated_classes,
                                  atlas_release_id, atlas_release_version, atlas_parcellation_ontology_id)

    # if ontology is too large, remove `defines` relationships from the ontology

    # the CELL_TYPE_ONTOLOGY_URI ontology is too big for having all its content into metadata
    include_defined_classes = not str(ontology) == CELL_TYPE_ONTOLOGY_URI

    # make list of framed classes
    class_resources_framed = list(class_resources_framed.values())

    # Frame ontology given the provided context
    ontology_json = bmo.frame_ontology(
        ontology_graph, new_forge_context, new_jsonld_context_dict, class_resources_framed,
        include_defined_classes
    )

    register_ontology(
        forge, ontology_json, ontology_path, ontology_graph,
        tag, class_resources_mapped=list(class_resources_mapped.values()), data_update=data_update
    )

    return str(ontology), ontology_json
    # bmo.remove_defines_relation(ontology_graph, ontology)


def _update_brainregion_graph(ontology_graph, class_resources_framed, all_class_resources_framed_dict, 
                              brain_region_generated_classes, atlas_release_id, atlas_release_version,
                              atlas_parcellation_ontology_id):

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
    data_update = not arguments.no_data_update
    exclude_deprecated_from_context = arguments.exclude_deprecated_from_context

    if environment == "staging":
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            "Environment argument must be either \"staging\" or \"production\" ")

    forge, forge_schema, forge_atlas = _initialize_forge_objects(
        endpoint=endpoint, token=token, input_bucket=bucket,
        atlas_parcellation_ontology_bucket=atlas_parcellation_ontology_bucket
    )

    print("Loading ontologies - Start")
    ontology_graphs_dict, all_ontology_graphs = load_ontologies(ontology_dir)

    print(
        f"Loading ontologies - Finished: {len(ontology_graphs_dict)} "
        f"ontologies with {len(all_ontology_graphs)} triples\n"
    )

    print("Preparing schema JSON-LD context - Start ")

    with open(SCHEMA_JSONLD_CONTEXT_PATH, "r") as f:
        new_jsonld_schema_context_document = json.load(f)

    new_jsonld_schema_context_resource = prepare_update_jsonld_context(
        forge_schema,
        new_jsonld_schema_context_document,
        JSONLD_SCHEMA_CONTEXT_IRI
    )

    print("Preparing schema JSON-LD context - Finish\n")

    print("Updating schema JSON-LD context - Start "
          "(because the schemas refer the JSONLD context)")

    if data_update:
        forge_schema.update(new_jsonld_schema_context_resource)

    print(f"Updating schema JSON-LD context - {'Finish' if data_update else 'Ignored'}: "
          f"{new_jsonld_schema_context_document['@id']} \n")

    print("Loading schemas - Start")

    schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs = load_schemas(
        schema_dir,
        transformed_schema_path,
        forge_schema,
        recursive=True,
        save_transformed_schema=True
    )

    print(
        f"Loading schemas - Finish: {len(schema_graphs_dict)} schemas with"
        f" {len(all_schema_graphs)} triples\n")

    print("Collecting JSON-LD data context from all ontologies and from all schemas - Start")

    with open(DATA_JSONLD_CONTEXT_PATH, "r") as f:
        forge_model_context_document = json.load(f)

    forge_model_context = Context(
        document=forge_model_context_document["@context"],
        iri=forge_model_context_document['@id']
    )

    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(
        all_ontology_graphs, forge_model_context, exclude_deprecated=exclude_deprecated_from_context
    )

    new_jsonld_schema_context, schema_errors = bmo.build_context_from_schema(
        all_schema_graphs, new_jsonld_context, exclude_deprecated=exclude_deprecated_from_context
    )

    errors = ontology_errors + schema_errors

    if len(errors) > 0:
        raise ValueError(
            f"Failed to build context from ontologies in {ontology_dir} "
            f"and schemas in {schema_dir}: {errors}"
        )

    print(
        f"Collecting JSON-LD data context from all ontologies and from all schemas - Finish - "
        f"Ontology dir: {ontology_dir}, Schema dir: {schema_dir}.\n"
    )

    new_jsonld_context_document: Dict = new_jsonld_context.document
    new_jsonld_context_document["@id"] = JSONLD_DATA_CONTEXT_IRI
    new_jsonld_context.iri = JSONLD_DATA_CONTEXT_IRI

    print(f"Preparing data JSON-LD context {new_jsonld_context_document['@id']} - Start")

    new_jsonld_context_resource = prepare_update_jsonld_context(
        forge, new_jsonld_context_document, JSONLD_DATA_CONTEXT_IRI
    )

    print(f"Preparing data JSON-LD context {new_jsonld_context_document['@id']} - Finish\n")

    # with open("./new_jsonld_context_resource.json", "w") as f:
    #     json.dump(forge.as_json(new_jsonld_context_resource), f)

    print(f"Updating data JSON-LD context {new_jsonld_context_document['@id']} - Start")

    if data_update:
        forge.update(new_jsonld_context_resource)

    print(f"Updating data JSON-LD context {new_jsonld_context_document['@id']} - "
          f"{'Finish' if data_update else 'Ignored'}\n")

    print("Preparing ontology classes - Start")
    new_jsonld_context_dict = new_jsonld_context_document["@context"]
    new_jsonld_context_dict.update(_get_ontology_annotation_lang_context())

    bmo.replace_is_defined_by_uris(all_ontology_graphs, WEBPROTEGE_TO_NEXUS)

    print("Merging brain region ontology with atlas hierarchy - Start")

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
        f"Merging brain region ontology with atlas hierarchy - Finish -"
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

    all_class_resources_framed_dict = dict(zip(class_ids, class_jsons))

    print(f"Got {len(all_class_resources_framed_dict)} non mapped classes")

    class_resources_mapped = forge.map(
        data=class_jsons,
        mapping=DictionaryMapping.load("./config/mappings/term-to-resource-mapping.hjson"),
        na=None
    )

    all_class_resources_mapped_dict = dict(zip(class_ids, class_resources_mapped))

    print(f"Got {len(class_resources_mapped)} mapped classes")

    print(f"Preparing ontology classes - Finish - Class count: {len(class_resources_mapped)} \n")

    print(f"Registering {len(list(schema_graphs_dict.keys()))} schemas - Start")
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
            already_registered=already_registered,
            data_update=data_update
        )

    print(f"Registering schemas - Finish - Schema count: {len(list(schema_graphs_dict.keys()))}\n")

    print(f"Registering ontologies - Start - Ontology count: {len(ontology_graphs_dict)} ")

    for ontology_path, ontology_graph in ontology_graphs_dict.items():

        execute_ontology_registration(
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
            atlas_parcellation_ontology_id=atlas_parcellation_ontology,
            tag=tag,
            data_update=data_update
        )

    print(f"Registering ontologies - Finish - Ontology count: {len(ontology_graphs_dict)}\n")

    print(f"Registering classes - Start: Class count:  {len(class_jsons)}")

    class_errors = []

    for class_json in class_jsons:
        class_json["@context"] = JSONLD_DATA_CONTEXT_IRI

        class_resource = forge.from_json(class_json)
        deprecated = class_resource.__dict__.get("owl:deprecated", False)

        if data_update:
            print(
                f"""Class {class_resource.get_identifier()} will be
                {'created/updated and tagged if a tag is provided' 
                if not deprecated else 'deprecated'}"""
            )
            if deprecated:
                ex, _ = bmo_registration.deprecate_class(forge=forge, class_resource=class_resource)
            else:
                ex, _ = bmo_registration.register_class(
                    forge=forge, class_resource=class_resource, tag=tag
                )

            if ex is not None:
                class_errors.append(ex)

        else:
            print(f"{'Creation/Update' if not deprecated else 'Deprecation'} of class "
                  f"{class_resource.get_identifier()} - Ignored")

    print(f"Registering classes - Finish - Class count: {len(class_jsons)},"
          f" {len(class_errors)} errors")

    for e in class_errors:
        print(e)


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


def register_ontology(
        forge: KnowledgeGraphForge, ontology_json: Dict, ontology_filepath: str,
        ontology_graph: Graph, tag: Optional[str],
        class_resources_mapped: Optional[List], data_update: bool,
) -> Tuple[Optional[Exception], Resource]:

    ontology_json = copy.deepcopy(ontology_json)
    # del ontology_json["@context"]
    ontology_resource = forge.from_json(ontology_json)
    dirpath = f"./{ontology_filepath.split('/')[-1].split('.')[0]}"
    dirpath_ttl = f"{dirpath}.ttl"
    ontology_graph.serialize(destination=dirpath_ttl, format="ttl")
    ontology_resource.distribution = [forge.attach(dirpath_ttl, content_type="text/turtle")]

    dirpath_json = f"{dirpath}.json"
    with open(dirpath_json, "w") as fp:
        json.dump(ontology_json, fp)
    ontology_resource.distribution.append(
        forge.attach(dirpath_json, content_type="application/ld+json"))

    if class_resources_mapped is not None:
        defined_types_df = forge.as_dataframe(class_resources_mapped)
        dirpath_csv = f"{dirpath}.csv"
        defined_types_df.to_csv(dirpath_csv)
        ontology_resource.distribution.append(forge.attach(dirpath_csv, content_type="text/csv"))

    if ontology_filepath in bmo_registration.SYNTHETIC_SENTENCES:
        synthetic = bmo_registration.SYNTHETIC_SENTENCES[ontology_filepath].get("synthetic", None)
        wiki = bmo_registration.SYNTHETIC_SENTENCES[ontology_filepath].get("wiki", None)
        if synthetic:
            ontology_resource.distribution.append(forge.attach(synthetic, content_type="text/json"))
        if wiki:
            ontology_resource.distribution.append(forge.attach(wiki, content_type="text/json"))

    deprecated = ontology_resource.__dict__.get("owl:deprecated", False)

    if data_update:
        print(
                f"""Ontology {ontology_resource.get_identifier()} will be
                {'created/updated and tagged if a tag is provided' 
                if not deprecated else 'deprecated'}"""
        )
        if deprecated:
            return bmo_registration.deprecate_ontology(
                forge=forge, ontology_resource=ontology_resource,
                ontology_filepath=ontology_filepath
            )

        return bmo_registration.register_ontology(
            forge=forge, ontology_resource=ontology_resource,
            ontology_filepath=ontology_filepath, tag=tag
        )

    print(f"{'Creation/Update' if not deprecated else 'Deprecation'} of ontology "
          f"{ontology_resource.get_identifier()} - Ignored")

    return None, ontology_resource


def register_schemas(
        forge: KnowledgeGraphForge,
        schema_filepath: str,
        schema_content: Dict,
        schema_graphs_dict: Dict[str, Dict],
        schema_id_to_filepath_dict: Dict[str, str],
        all_schema_graph: Graph,
        jsonld_schema_context,
        tag: Optional[str],
        already_registered: List,
        data_update: bool
):

    # TODO should there be a mechanism to raise errors/warn when importing deprecated schemas?

    if schema_content["resource"].id not in already_registered:
        if "imports" in schema_content:
            imported_schemas = [jsonld_schema_context.expand(i) for i in schema_content["imports"]]
            for imported_schema in imported_schemas:
                if imported_schema in schema_id_to_filepath_dict:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                else:
                    raise ValueError(
                        f"The schema {imported_schema} (imported from {schema_content['id']} "
                        f"in {schema_filepath}) was not found."
                    )
                imported_schema_content = schema_graphs_dict[imported_schema_file]

                register_schemas(
                    forge,
                    schema_filepath=imported_schema_file,
                    schema_content=imported_schema_content,
                    schema_graphs_dict=schema_graphs_dict,
                    schema_id_to_filepath_dict=schema_id_to_filepath_dict,
                    all_schema_graph=all_schema_graph,
                    jsonld_schema_context=jsonld_schema_context, tag=tag,
                    already_registered=already_registered,
                    data_update=data_update
                )

                already_registered.extend(imported_schema_content["resource"].id)

        schema_resource = schema_content["resource"]
        deprecated = schema_resource.__dict__.get("owl:deprecated", False)

        if data_update:
            print(
                f"""Schema {schema_resource.get_identifier()} will be
                {'created/updated and tagged if a tag is provided' 
                if not deprecated else 'deprecated'}"""
            )
            if deprecated:
                _, _ = bmo_registration.deprecate_schema(
                    forge, schema_filepath, schema_resource
                )
            else:
                _, _ = bmo_registration.register_schema(
                    forge, schema_filepath, schema_resource, tag
                )
                already_registered.append(schema_resource.get_identifier())
        else:
            print(f"{'Creation/Update' if not deprecated else 'Deprecation'} of schema "
                  f"{schema_resource.get_identifier()} - Ignored")


if __name__ == "__main__":
    # defines and receives script arguments
    parser = define_arguments()
    received_args, leftovers = parser.parse_known_args()
    # registers the ontologies and the schemas
    parse_and_register_ontologies(received_args)
