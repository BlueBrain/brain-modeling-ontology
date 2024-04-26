import argparse
import json
import copy
import cProfile
import pstats
from collections import defaultdict
from pstats import SortKey
from typing import Dict, Any, List, Tuple, Optional, Set, Union
from rdflib import PROV, Literal, RDF, OWL, RDFS, Graph, term
from kgforge.core.commons import Context
from kgforge.core import KnowledgeGraphForge, Resource
from kgforge.specializations.mappings import DictionaryMapping

import bmo.ontologies as bmo
import bmo.registration as bmo_registration
from bmo.argument_parsing import define_arguments
from bmo.schema_to_type_mapping import create_update_type_to_schema_mapping
from bmo.loading import (
    DATA_JSONLD_CONTEXT_PATH,
    SCHEMA_JSONLD_CONTEXT_PATH,
    load_ontologies,
    load_schemas,
)
from bmo.logger import logger

from bmo.slim_ontologies import (create_slim_ontology_graph,
                                 create_slim_classes,
                                 get_slim_ontology_id
                                 )
from bmo.utils import (
    ATLAS_PROPERTIES_TO_MERGE,
    BMO,
    BRAIN_REGION_ONTOLOGY_URI,
    NSG,
    NXV,
    SCHEMAORG,
    _get_ontology_annotation_lang_context,
    CELL_TYPE_ONTOLOGY_URI,
)

# Target ontology ID's to define
with open("./webprotege_to_nexus.json", "r") as f:
    WEBPROTEGE_TO_NEXUS = json.loads(f.read())

# "urn:webprotege:ontology:b307df0e-232d-4e20-9467-80e0733ecbec/edit/Classes"
# in none of the ontology files

JSONLD_DATA_CONTEXT_IRI = "https://neuroshapes.org"
JSONLD_SCHEMA_CONTEXT_IRI = "https://incf.github.io/neuroshapes/contexts/schema.json"


def _initialize_forge_objects(
    endpoint, token, input_bucket, atlas_parcellation_ontology_bucket
):
    def get_forge_object(config_path, selected_bucket):
        return KnowledgeGraphForge(
            config_path,
            endpoint=endpoint,
            bucket=selected_bucket,
            token=token,
            debug=True,
        )

    forge = get_forge_object("config/forge-config.yml", input_bucket)
    forge_schema = get_forge_object("config/forge-schema-config.yml", input_bucket)
    forge_atlas = get_forge_object(
        "config/forge-config-new.yml", atlas_parcellation_ontology_bucket
    )

    return forge, forge_schema, forge_atlas


def execute_ontology_registration(
    forge: KnowledgeGraphForge,
    ontology_path: str,
    slim_ontology_path: str,
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
    tag=None,
) -> Tuple[str, Dict]:
    """
    Executes the registration process

    :param forge: The nexus forge object
    :param ontology_path: relative path to the ontology
    :param slim_ontology_path: relative path to the slim ontology
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

    logger.info(f"Registering ontology {ontology_path} - Start")

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
    ontology = bmo.replace_is_defined_by_uris(
        ontology_graph, WEBPROTEGE_TO_NEXUS, str(ontology)
    )

    class_resources_mapped = _get_classes_in_ontology(
        all_class_resources_mapped_dict, ontology_graph.subjects(RDF.type, OWL.Class)
    )
    class_resources_framed = _get_classes_in_ontology(
        all_class_resources_framed_dict, ontology_graph.subjects(RDF.type, OWL.Class)
    )

    if str(ontology) == BRAIN_REGION_ONTOLOGY_URI:
        _update_brainregion_graph(
            ontology_graph,
            class_resources_framed,
            all_class_resources_framed_dict,
            brain_region_generated_classes,
            atlas_release_id,
            atlas_release_version,
            atlas_parcellation_ontology_id,
        )

    # if ontology is too large, remove `defines` relationships from the ontology
    # the CELL_TYPE_ONTOLOGY_URI ontology is too big for having all its content into metadata
    include_defined_classes = not str(ontology) == CELL_TYPE_ONTOLOGY_URI

    # make list of framed classes
    class_resources_mapped = [forge.as_jsonld(mapped_class) for mapped_class in class_resources_mapped.values()]
    class_resources_framed = list(class_resources_framed.values())

    # Frame ontology given the provided context
    ontology_json = bmo.frame_ontology(
        ontology_graph,
        new_forge_context,
        new_jsonld_context_dict,
        class_resources_framed,
        include_defined_classes,
    )

    register_ontology(
        forge,
        ontology_json,
        ontology_path,
        ontology_graph,
        tag,
        class_resources_mapped=class_resources_mapped,
        data_update=data_update,
    )

    print(
        f"Registration of ontology: {str(ontology)} - Done\n"
    )

    # Standard registration done
    # Create slim version of ontologies
    slim_ontology_graph = create_slim_ontology_graph(ontology_graph)
    slim_ontology = get_slim_ontology_id(ontology)

    # Replace ontology graph id
    bmo.replace_ontology_id(slim_ontology_graph, slim_ontology)
    # Copy ontology label
    bmo.copy_ontology_label(ontology_graph, ontology, slim_ontology_graph, slim_ontology,
                            append_label=" Slim Version")

    slim_classes_mapped = create_slim_classes(class_resources_mapped)
    slim_classes_framed = create_slim_classes(class_resources_framed)

    # frame the slim ontology
    slim_ontology_json = bmo.frame_ontology(
        slim_ontology_graph,
        new_forge_context,
        new_jsonld_context_dict,
        slim_classes_framed,
        True,  # always include defined classes in ontology
    )

    register_ontology(
        forge,
        slim_ontology_json,
        slim_ontology_path,
        slim_ontology_graph,
        tag,
        class_resources_mapped=slim_classes_mapped,
        data_update=data_update,
    )

    print(
        f"Registration of slim ontology version: {str(slim_ontology)} - Done\n"
    )

    return str(ontology), ontology_json
    # bmo.remove_defines_relation(ontology_graph, ontology)


def _update_brainregion_graph(
    ontology_graph,
    class_resources_framed,
    all_class_resources_framed_dict,
    brain_region_generated_classes,
    atlas_release_id,
    atlas_release_version,
    atlas_parcellation_ontology_id,
):

    brain_region_generated_classes_resources_framed = _get_classes_in_ontology(
        all_class_resources_framed_dict, brain_region_generated_classes
    )

    class_resources_framed.update(
        {
            k: v
            for k, v in brain_region_generated_classes_resources_framed.items()
            if k not in class_resources_framed
        }
    )
    ontology_graph.add(
        (
            term.URIRef(BRAIN_REGION_ONTOLOGY_URI),
            NSG.atlasRelease,
            term.URIRef(atlas_release_id),
        )
    )
    ontology_graph.add(
        (term.URIRef(atlas_release_id), NXV.rev, Literal(atlas_release_version))
    )
    ontology_graph.add((term.URIRef(atlas_release_id), RDF.type, NSG.BrainAtlasRelease))

    (
        atlas_parcellation_ontology_derivation_bNode,
        atlas_parcellation_ontology_derivation_triples,
    ) = _create_bnode_triples_from_value(
        {
            RDF.type: PROV.Derivation,
            PROV.entity: term.URIRef(atlas_parcellation_ontology_id),
        }
    )

    ontology_graph.add(
        (
            term.URIRef(BRAIN_REGION_ONTOLOGY_URI),
            NSG.derivation,
            atlas_parcellation_ontology_derivation_bNode,
        )
    )

    ontology_graph.add(
        (
            term.URIRef(atlas_parcellation_ontology_id),
            RDF.type,
            NSG.ParcellationOntology,
        )
    )

    atlasRelease_derivation_bNode, atlasRelease_derivation_triples = (
        _create_bnode_triples_from_value(
            {RDF.type: PROV.Derivation, PROV.entity: term.URIRef(atlas_release_id)}
        )
    )

    ontology_graph.add(
        (
            term.URIRef(BRAIN_REGION_ONTOLOGY_URI),
            NSG.derivation,
            atlasRelease_derivation_bNode,
        )
    )


def _get_classes_in_ontology(all_class_resources_dict, uriref_iterator):
    return {
        cls: all_class_resources_dict.get(str(cls))
        for cls in uriref_iterator
        if str(cls) in all_class_resources_dict
    }


def combine_jsonld_context(all_ontology_graphs, all_schema_graphs,
                           exclude_deprecated_from_context):
    with open(DATA_JSONLD_CONTEXT_PATH, "r") as f:
        local_model_context_document = json.load(f)

    local_model_context = Context(
        document=local_model_context_document["@context"],
        iri=local_model_context_document["@id"],
    )

    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(
        all_ontology_graphs,
        local_model_context,
        exclude_deprecated=exclude_deprecated_from_context,
    )

    new_jsonld_schema_context, schema_errors = bmo.build_context_from_schema(
        all_schema_graphs,
        new_jsonld_context,
        exclude_deprecated=exclude_deprecated_from_context,
    )

    errors = ontology_errors + schema_errors
    return new_jsonld_context, new_jsonld_schema_context, errors


def prepare_update_jsonld_context(
    forge: KnowledgeGraphForge, new_jsonld_context_json, jsonld_context_iri
):
    new_jsonld_context_resource = forge.from_jsonld(new_jsonld_context_json)
    existing_jsonld_context_resource = forge.retrieve(jsonld_context_iri)
    new_jsonld_context_resource._store_metadata = (
        existing_jsonld_context_resource._store_metadata
    )
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
    tag = arguments.tag if arguments.tag != "-" else None
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
            'Environment argument must be either "staging" or "production" '
        )

    forge, forge_schema, forge_atlas = _initialize_forge_objects(
        endpoint=endpoint,
        token=token,
        input_bucket=bucket,
        atlas_parcellation_ontology_bucket=atlas_parcellation_ontology_bucket,
    )

    logger.info("Loading ontologies - Start")
    ontology_graphs_dict, all_ontology_graphs = load_ontologies(ontology_dir)

    logger.info(
        f"Loading ontologies - Finished: {len(ontology_graphs_dict)} "
        f"ontologies with {len(all_ontology_graphs)} triples\n"
    )

    logger.info("Preparing schema JSON-LD context - Start ")

    with open(SCHEMA_JSONLD_CONTEXT_PATH, "r") as f:
        new_jsonld_schema_context_document = json.load(f)

    new_jsonld_schema_context_resource = prepare_update_jsonld_context(
        forge_schema, new_jsonld_schema_context_document, JSONLD_SCHEMA_CONTEXT_IRI
    )

    logger.info("Preparing schema JSON-LD context - Finish\n")

    logger.info(
        "Updating schema JSON-LD context - Start "
        "(because the schemas refer the JSONLD context)"
    )

    if data_update:
        forge_schema.update(new_jsonld_schema_context_resource)

    logger.info(
        f"Updating schema JSON-LD context - {'Finish' if data_update else 'Ignored'}: "
        f"{new_jsonld_schema_context_document['@id']} \n"
    )

    logger.info("Loading schemas - Start")

    schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs = load_schemas(
        schema_dir,
        transformed_schema_path,
        forge_schema,
        recursive=True,
        save_transformed_schema=True,
    )

    logger.info(
        f"Loading schemas - Finish: {len(schema_graphs_dict)} schemas with"
        f" {len(all_schema_graphs)} triples\n"
    )

    logger.info(
        "Collecting JSON-LD data context from all ontologies and from all schemas - Start"
    )

    new_jsonld_context, new_jsonld_schema_context, errors = combine_jsonld_context(
        all_ontology_graphs, all_schema_graphs, exclude_deprecated_from_context
    )

    if len(errors) > 0:
        raise ValueError(
            f"Failed to build context from ontologies in {ontology_dir} "
            f"and schemas in {schema_dir}: {errors}"
        )

    logger.info(
        f"Collecting JSON-LD data context from all ontologies and from all schemas - Finish - "
        f"Ontology dir: {ontology_dir}, Schema dir: {schema_dir}.\n"
    )

    new_jsonld_context_document: Dict = new_jsonld_context.document
    new_jsonld_context_document["@id"] = JSONLD_DATA_CONTEXT_IRI
    new_jsonld_context.iri = JSONLD_DATA_CONTEXT_IRI

    logger.info(
        f"Preparing data JSON-LD context {new_jsonld_context_document['@id']} - Start"
    )

    new_jsonld_context_resource = prepare_update_jsonld_context(
        forge, new_jsonld_context_document, JSONLD_DATA_CONTEXT_IRI
    )

    logger.info(
        f"Preparing data JSON-LD context {new_jsonld_context_document['@id']} - Finish\n"
    )

    # with open("./new_jsonld_context_resource.json", "w") as f:
    #     json.dump(forge.as_json(new_jsonld_context_resource), f)

    logger.info(f"Updating data JSON-LD context {new_jsonld_context_document['@id']} - Start")

    if data_update:
        forge.update(new_jsonld_context_resource)

    logger.info(
        f"Updating data JSON-LD context {new_jsonld_context_document['@id']} - "
        f"{'Finish' if data_update else 'Ignored'}\n"
    )

    logger.info("Preparing ontology classes - Start")
    new_jsonld_context_dict = new_jsonld_context_document["@context"]
    new_jsonld_context_dict.update(_get_ontology_annotation_lang_context())

    bmo.replace_is_defined_by_uris(all_ontology_graphs, WEBPROTEGE_TO_NEXUS)

    logger.info("Merging brain region ontology with atlas hierarchy - Start")

    # Waiting for a single version (tag) across all the atlas dataset to be
    # made available, _rev will be used.
    version = (
        int(atlas_parcellation_ontology_version)
        if atlas_parcellation_ontology_version is not None
        else atlas_parcellation_ontology_version
    )

    atlas_hierarchy = forge_atlas.retrieve(atlas_parcellation_ontology, version=version)

    atlas_hierarchy_jsonld_distribution = [
        distrib
        for distrib in atlas_hierarchy.distribution
        if distrib.encodingFormat == "application/ld+json"
    ]

    atlas_hierarchy_jsonld_distribution = atlas_hierarchy_jsonld_distribution[0]

    forge_atlas.download(
        atlas_hierarchy_jsonld_distribution,
        follow="contentUrl",
        path=".",
        overwrite=True,
    )

    atlas_hierarchy_ontology_graph = Graph().parse(
        atlas_hierarchy_jsonld_distribution.name, format="json-ld"
    )

    triples_to_add, triples_to_remove = _merge_ontology(
        atlas_hierarchy_ontology_graph,
        ontology_graphs_dict["./ontologies/bbp/brainregion.ttl"],
        all_ontology_graphs
    )

    logger.info(
        f"Merging brain region ontology with atlas hierarchy - Finish -"
        f" {len(triples_to_add.values())} triples were added to the brain region ontology "
        f"for {len(triples_to_add)} brain regions and from the atlas hierarchy "
        f"while {len(triples_to_remove.values())} triples were removed from the brain "
        f"region ontology for {len(triples_to_remove)} brain regions."
    )

    logger.info("Framing classes - Start")
    class_ids, class_jsons, all_blank_node_triples, brain_region_generated_classes = (
        bmo.frame_classes(
            all_ontology_graphs,
            new_jsonld_context,
            new_jsonld_context_dict,
            atlas_hierarchy.atlasRelease.id,
            atlas_hierarchy.atlasRelease._rev,
        )
    )
    logger.info("Framing classes - Finish")

    all_class_resources_framed_dict = dict(zip(class_ids, class_jsons))

    logger.info(f"Got {len(all_class_resources_framed_dict)} framed classes")

    class_resources_mapped = forge.map(
        data=class_jsons,
        mapping=DictionaryMapping.load(
            "./config/mappings/term-to-resource-mapping.hjson"
        ),
        na=None,
    )

    all_class_resources_mapped_dict = dict(zip(class_ids, class_resources_mapped))

    logger.info(f"Got {len(class_resources_mapped)} mapped classes")

    # make a list of ontology ids to be used when registering schemas
    all_ontologies_ids = bmo.all_ontologies_ids(ontology_graphs_dict)

    logger.info(
        f"Preparing ontology classes - Finish - Class count: {len(class_resources_mapped)} \n"
    )

    logger.info(
        f"Registering ontologies - Start - Ontology count: {len(ontology_graphs_dict)} "
    )

    for ontology_path, ontology_graph in ontology_graphs_dict.items():

        dirpath = f"./{ontology_path.split('/')[-1].split('.')[0]}"
        slim_ontology_path = f"{dirpath}_slim.ttl"

        execute_ontology_registration(
            forge=forge,
            ontology_path=ontology_path,
            slim_ontology_path=slim_ontology_path,
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
            data_update=data_update,
        )

    logger.info(
        f"Registering ontologies - Finish - Ontology count: {len(ontology_graphs_dict)}\n"
    )

    logger.info(f"Registering ontology terms - Start: Entity count:  {len(class_jsons)}")

    class_errors = []

    for class_json in class_jsons:
        class_json["@context"] = JSONLD_DATA_CONTEXT_IRI

        class_resource = forge.from_json(class_json)
        deprecated = class_resource.__dict__.get("deprecated", False)

        # Classes are only of type Class, but other ontology terms can have multiple types
        class_resource_id = class_resource.get_identifier()
        resource_type = class_resource.get_type() if isinstance(class_resource.get_type(), List) \
            else [class_resource.get_type()]

        if data_update:
            logger.info(
                f"Term {class_resource_id} will be "
                f"{'created/updated and tagged if a tag is provided' if not deprecated else 'deprecated'}"
            )
            if deprecated:
                ex, _ = bmo_registration.deprecate_class(
                    forge=forge, class_resource=class_resource
                )
            else:
                if 'Class' in resource_type:
                    ex, _ = bmo_registration.register_class(
                        forge=forge, class_resource=class_resource, tag=tag
                    )
                elif 'NamedIndividual' in resource_type:
                    ex, _ = bmo_registration.register_namedindividual(
                        forge=forge, resource=class_resource, tag=tag
                    )
                else:
                    raise ValueError(f"Ontology term with id {class_resource_id} "
                                     f"has an unsupported type: {resource_type}.")

            if ex is not None:
                class_errors.append(ex)

        else:
            logger.info(
                f"{'Creation/Update' if not deprecated else 'Deprecation'} of class "
                f"{class_resource_id} - Ignored"
            )

    logger.info(
        f"Registering ontology terms - Finish - Entity count: {len(class_jsons)},"
        f" {len(class_errors)} errors"
    )

    for e in class_errors:
        logger.error(e)

    logger.info(f"Registering {len(list(schema_graphs_dict.keys()))} schemas - Start")
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
            data_update=data_update,
            ontologies_ids=all_ontologies_ids,
        )

    logger.info(
        f"Registering schemas - Finish - Schema count: {len(list(schema_graphs_dict.keys()))}\n"
    )

    create_update_type_to_schema_mapping(
        all_schema_graphs=all_schema_graphs,
        forge=forge,
        data_update=data_update,
        tag=tag,
    )


def _merge_ontology(
    from_ontology_graph,  # in usage, atlas_hierarchy_ontology_graph
    to_ontology_graph,  # in usage, brain_region_graph = brain_region.ttl
    to_another_graph,  # in usage, graph_of_all_ontologies = *.ttl
    what_property_to_merge=ATLAS_PROPERTIES_TO_MERGE
):
    # merge hierarchy from atlas with this brain region:
    # make sure atlas hierarchy, labels, notation, identifier, ... is fully included in bmo

    triples_to_add = defaultdict(set)
    triples_to_remove = defaultdict(set)

    triples_per_prop = [
        e for prop in what_property_to_merge
        for e in from_ontology_graph.triples((None, prop, None))
    ]

    # Adding relevant triples from the atlas hierarchy into the brain region graph (interesting properties)
    for (from_s, from_p, from_o) in triples_per_prop:

        if str(from_o) == "":
            continue

        if from_p in [BMO.regionVolume, BMO.regionVolumeRatioToWholeBrain]:  # Special case

            b_node, triples = _create_bnode_triples_from_value(
                {
                    SCHEMAORG.value: from_o,
                    SCHEMAORG.unitCode: Literal("cubic micrometer"),
                }
            )
            triples_to_add[str(from_s)].update(triples)
            triples_to_add[str(from_s)].add((from_s, from_p, b_node))
        else:
            triples_to_add[str(from_s)].add((from_s, from_p, from_o))  # add triples from atlas hierarchy ontology graph to brain region graph

        # For all s/p of relevant properties, remove from brain region graph the triples with same s/p as those in atlas
        if (from_s, from_p, None) in to_ontology_graph:
            for to_s, to_p, to_o in to_ontology_graph.triples((from_s, from_p, None)):
                triples_to_remove[str(from_s)].add((to_s, to_p, to_o))  # remove triples from brain region graph from brain region graph

        # What to keep from the atlas graph (= uriref tied to an interesting property to merge have other properties that could be interesting)
        if (from_s, from_p, None) not in to_ontology_graph and isinstance(from_o, term.URIRef):

            for from_o_s, from_o_p, from_o_o in from_ontology_graph.triples((from_o, None, None)):

                properties_to_ignore = [
                    BMO.layers,
                    BMO.adjacentTo,
                    BMO.continuousWith,
                    BMO.hasLayerLocationPhenotype,
                ]
                if from_o_p not in properties_to_ignore and from_o_p not in what_property_to_merge:
                    # will be merged once the data format is okay
                    triples_to_add[str(from_o_s)].add((from_o_s, from_o_p, from_o_o))

        triples_to_add[str(from_s)].add((from_s, RDFS.subClassOf, NSG.BrainRegion))
        triples_to_add[str(from_s)].add((from_s, RDF.type, OWL.Class))

    for _, v in triples_to_remove.items():
        for t in v:
            to_ontology_graph.remove(t)
            to_another_graph.remove(t)
    for _, v in triples_to_add.items():
        for t in v:
            to_ontology_graph.add(t)
            to_another_graph.add(t)

    return triples_to_add, triples_to_remove


def _create_bnode_triples_from_value(
    prop_uriref_to_value_dict: Dict,
) -> Tuple[term.BNode, List[Tuple[term.BNode, Any, Any]]]:

    triples = []
    b_node = term.BNode()
    for prop_uriref, value in prop_uriref_to_value_dict.items():
        triples.append((b_node, prop_uriref, value))

    return b_node, triples


def register_ontology(
    forge: KnowledgeGraphForge,
    ontology_json: Dict,
    ontology_filepath: str,
    ontology_graph: Graph,
    tag: Optional[str],
    class_resources_mapped: Optional[List],
    data_update: bool,
) -> Tuple[Optional[Exception], Resource]:

    ontology_json = copy.deepcopy(ontology_json)
    # del ontology_json["@context"]
    ontology_resource = forge.from_json(ontology_json)
    dirpath = f"./{ontology_filepath.split('/')[-1].split('.')[0]}"
    dirpath_ttl = f"{dirpath}.ttl"
    ontology_graph.serialize(destination=dirpath_ttl, format="ttl")
    ontology_resource.distribution = [
        forge.attach(dirpath_ttl, content_type="text/turtle")
    ]

    dirpath_json = f"{dirpath}.json"
    with open(dirpath_json, "w") as fp:
        json.dump(ontology_json, fp)
    ontology_resource.distribution.append(
        forge.attach(dirpath_json, content_type="application/ld+json")
    )

    if class_resources_mapped is not None:
        defined_types_df = forge.as_dataframe(class_resources_mapped)
        dirpath_csv = f"{dirpath}.csv"
        defined_types_df.to_csv(dirpath_csv)
        ontology_resource.distribution.append(
            forge.attach(dirpath_csv, content_type="text/csv")
        )

    if ontology_filepath in bmo_registration.SYNTHETIC_SENTENCES:
        synthetic = bmo_registration.SYNTHETIC_SENTENCES[ontology_filepath].get(
            "synthetic", None
        )
        wiki = bmo_registration.SYNTHETIC_SENTENCES[ontology_filepath].get("wiki", None)
        if synthetic:
            ontology_resource.distribution.append(
                forge.attach(synthetic, content_type="text/json")
            )
        if wiki:
            ontology_resource.distribution.append(
                forge.attach(wiki, content_type="text/json")
            )

    deprecated = ontology_resource.__dict__.get("deprecated", False)

    if data_update:
        logger.info(
            f"Ontology {ontology_resource.get_identifier()} will be "
            f"{'created/updated and tagged if a tag is provided' if not deprecated else 'deprecated'}"
        )
        if deprecated:
            return bmo_registration.deprecate_ontology(
                forge=forge,
                ontology_resource=ontology_resource,
                ontology_filepath=ontology_filepath,
            )

        return bmo_registration.register_ontology(
            forge=forge,
            ontology_resource=ontology_resource,
            ontology_filepath=ontology_filepath,
            tag=tag,
        )

    logger.info(
        f"{'Creation/Update' if not deprecated else 'Deprecation'} of ontology "
        f"{ontology_resource.get_identifier()} - Ignored"
    )

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
    data_update: bool,
    ontologies_ids: Optional[Union[Set, List]] = []
):

    # TODO should there be a mechanism to raise errors/warn when importing deprecated schemas?

    if schema_content["resource"].id not in already_registered:
        if "imports" in schema_content:
            imported_schemas = [
                jsonld_schema_context.expand(i) for i in schema_content["imports"]
            ]
            for imported_schema in imported_schemas:
                if imported_schema in schema_id_to_filepath_dict:
                    imported_schema_file = schema_id_to_filepath_dict[imported_schema]
                elif imported_schema in ontologies_ids:
                    continue
                else:
                    raise ValueError(
                        f"The schema {imported_schema} (imported from {schema_content['id']} "
                        f"in {schema_filepath}) was not found, nor is it an ontology in {ontologies_ids}"
                    )
                imported_schema_content = schema_graphs_dict[imported_schema_file]

                register_schemas(
                    forge,
                    schema_filepath=imported_schema_file,
                    schema_content=imported_schema_content,
                    schema_graphs_dict=schema_graphs_dict,
                    schema_id_to_filepath_dict=schema_id_to_filepath_dict,
                    all_schema_graph=all_schema_graph,
                    jsonld_schema_context=jsonld_schema_context,
                    tag=tag,
                    already_registered=already_registered,
                    data_update=data_update,
                    ontologies_ids=ontologies_ids
                )

                already_registered.extend(imported_schema_content["resource"].id)

        schema_resource = schema_content["resource"]
        deprecated = schema_resource.__dict__.get("owl:deprecated", False)

        if data_update:
            logger.info(
                f"Schema {schema_resource.get_identifier()} will be "
                f"{'created/updated and tagged if a tag is provided' if not deprecated else 'deprecated'}"
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
            logger.info(
                f"{'Creation/Update' if not deprecated else 'Deprecation'} of schema "
                f"{schema_resource.get_identifier()} - Ignored"
            )


if __name__ == "__main__":
    # defines and receives script arguments
    parser = define_arguments(argparse.ArgumentParser())
    received_args, leftovers = parser.parse_known_args()
    # registers the ontologies and the schemas

    with cProfile.Profile() as pr:
        parse_and_register_ontologies(received_args)
        pstats.Stats(pr).sort_stats(SortKey.CUMULATIVE).print_stats(10)
