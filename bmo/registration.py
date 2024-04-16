import io
from contextlib import redirect_stdout
from typing import Optional, Tuple

from kgforge.core import KnowledgeGraphForge, Resource, commons
from kgforge.core.commons.exceptions import RetrievalError

from bmo.logger import logger

ALREADY_EXISTS_ERROR = " already exists in project"
ALREADY_DEPRECATED_ERROR = "is deprecated"

SHACL_SCHEMA_ID = "https://bluebrain.github.io/nexus/schemas/shacl-20170720.ttl"
ONTOLOGY_SCHEMA_ID = "https://neuroshapes.org/dash/ontology"
CLASS_SCHEMA_ID = "https://neuroshapes.org/dash/ontologyentity"
NAMEDINDIVIDUAL_SCHEMA_ID = "https://bbp.epfl.ch/shapes/dash/namedindividual"


SYNTHETIC_SENTENCES = {
    "./ontologies/bbp/bmo.ttl": {
        "synthetic": "./texts/synthetic_texts_bmo.json"
    },
    "./ontologies/bbp/data-types.ttl": {
    },
    "./ontologies/bbp/efeatures.ttl": {
        "synthetic": "./texts/synthetic_texts_NeuronElectrophysiologicalFeature.json"
    },
    "./ontologies/bbp/mfeatures.ttl": {
        "synthetic": "./texts/synthetic_texts_NeuronMorphologicalFeature.json"
    },
    "./ontologies/bbp/molecular-systems.ttl": {
        "synthetic": "./texts/synthetic_texts_Molecular_systems.json"
    },
    "./ontologies/bbp/speciestaxonomy.ttl": {
        "synthetic": "./texts/synthetic_texts_Species.json"
    },
    "./ontologies/bbp/stimulustypes.ttl": {
        "synthetic": "./texts/synthetic_texts_ElectricalStimulus.json"
    },
    "./ontologies/bbp/celltypes.ttl": {
        "synthetic": "./texts/synthetic_texts_BrainCellType.json"
    },
    "./ontologies/bbp/brainregion.ttl": {
        "synthetic": "./texts/synthetic_texts_BrainRegion.json",
        "wiki": "./texts/wiki_texts_BrainRegion.json"

    }
}


def register_class(
        forge: KnowledgeGraphForge, class_resource: Resource, tag=None
) -> Tuple[Optional[Exception], Resource]:
    """Register ontology class to the store."""
    return _register_update(
        forge=forge, resource=class_resource,
        schema_id=CLASS_SCHEMA_ID, tag=tag, type_str="Class", raise_on_fail=False
    )


def register_namedindividual(
        forge: KnowledgeGraphForge, resource: Resource, tag=None
) -> Tuple[Optional[Exception], Resource]:
    """Register ontology named individual to the store."""
    return _register_update(
        forge=forge, resource=resource,
        schema_id=NAMEDINDIVIDUAL_SCHEMA_ID, tag=tag, type_str="NamedIndividual", raise_on_fail=False
    )


def register_schema(
        forge: KnowledgeGraphForge, schema_filepath: str, schema_resource: Resource, tag: str
) -> Tuple[Optional[Exception], Resource]:
    """Register schema to the store."""
    return _register_update(
        forge, schema_resource, schema_id=SHACL_SCHEMA_ID,
        tag=tag, extra_message=f"from file {schema_filepath}",
        raise_on_fail=True, type_str="Schema"
    )


def register_ontology(
        forge: KnowledgeGraphForge, ontology_filepath: str, ontology_resource: Resource, tag: str
) -> Tuple[Optional[Exception], Resource]:

    return _register_update(
        forge, ontology_resource,
        schema_id=ONTOLOGY_SCHEMA_ID, tag=tag, type_str="Ontology",
        extra_message=f"from file {ontology_filepath}"
    )


def _handle_failed(
        action_message, resource, action_type, extra_message, type_str, raise_on_fail,
        parent_ex=None
):
    message = f"Failed to {action_type} {type_str.lower()}:{resource.get_identifier()} " \
              f"{extra_message}: {action_message}"
    logger.error(message)
    ex = Exception(message)

    if raise_on_fail:
        if parent_ex:
            raise ex from parent_ex
        raise ex

    return ex, resource


def deprecate_schema(
        forge: KnowledgeGraphForge, schema_filepath: str, schema_resource: Resource
) -> Tuple[Optional[Exception], Resource]:
    """Deprecate schema from the store."""
    return _deprecate(forge, schema_resource, raise_on_fail=False, type_str="Schema",
                      extra_message=f"from file {schema_filepath}")


def deprecate_class(
        forge: KnowledgeGraphForge, class_resource: Resource
) -> Tuple[Optional[Exception], Resource]:
    """Deprecate class from the store."""
    return _deprecate(forge, class_resource, raise_on_fail=False, type_str="Class")


def deprecate_ontology(
        forge: KnowledgeGraphForge, ontology_filepath: str, ontology_resource: Resource
) -> Tuple[Optional[Exception], Resource]:
    """Deprecate ontology from the store."""
    return _deprecate(forge, ontology_resource, raise_on_fail=False, type_str="Ontology",
                      extra_message=f"from file {ontology_filepath}")


def _successful_action_output(type_str, resource, action_verb):
    return f"{type_str} {resource.get_identifier()} has been successfully {action_verb}."


def _deprecate(
        forge: KnowledgeGraphForge, resource: Resource,
        type_str, extra_message="", raise_on_fail=True
):
    try:
        resource_retrieved = forge.retrieve(resource.get_identifier())
    except commons.exceptions.RetrievalError:
        resource_retrieved = None

    if resource_retrieved is None:
        logger.error(
            f"{type_str} {resource.get_identifier()} "
            f"cannot be deprecated because it cannot be retrieved"
        )
        return None, resource

    with redirect_stdout(io.StringIO()):
        forge.deprecate(resource_retrieved)

    last_action = resource_retrieved._last_action

    if not last_action:
        logger.info("No deprecation action?")
        return None, resource_retrieved

    if last_action.succeeded:
        logger.info(_successful_action_output(type_str, resource_retrieved, "deprecated"))
        return None, resource_retrieved

    if ALREADY_DEPRECATED_ERROR in last_action.message:
        logger.info(f"{type_str} {resource_retrieved.get_identifier()} already deprecated.")
        return None, resource_retrieved

    return _handle_failed(
        last_action.message, resource_retrieved, "deprecate", extra_message, type_str, raise_on_fail
    )


def _register_update(
        forge: KnowledgeGraphForge, resource: Resource, schema_id: str, tag: str,
        type_str, extra_message="", raise_on_fail=True
) -> Tuple[Optional[Exception], Resource]:

    with redirect_stdout(io.StringIO()):
        forge.register(resource, schema_id=schema_id)

    last_action = resource._last_action

    if not last_action:
        logger.warning("No registration action?")
        return None, resource

    if last_action.succeeded:
        logger.info(_successful_action_output(type_str, resource, "registered"))

        if tag is not None:
            forge.tag(resource, tag)
        return None, resource

    if ALREADY_EXISTS_ERROR not in last_action.message:
        return _handle_failed(
            last_action.message, resource, "register", extra_message, type_str, raise_on_fail
        )

    logger.info(f"{type_str} {resource.get_identifier()} already exists, updating...")

    has_id, id_attrib = resource.has_identifier(return_attribute=True)

    if not has_id:
        return _handle_failed(
            "Could not find identifier for an existing resource "
            f"in local description of the {resource.type}",
            resource, "retrieve", extra_message, type_str, raise_on_fail
        )

    resource_id = forge._model.context().expand(resource.get_identifier())

    resource_updated = resource
    resource_updated.id = resource_id

    try:
        existing_resource = forge.retrieve(resource_id)
    except RetrievalError as e:
        return _handle_failed(
            f"Could not retrieve {id_attrib}",
            resource, "retrieve", extra_message, type_str, raise_on_fail, parent_ex=e
        )

    resource_updated._store_metadata = existing_resource._store_metadata

    with redirect_stdout(io.StringIO()):
        forge.update(resource_updated)

    updated_last_action = resource_updated._last_action

    if not updated_last_action:
        logger.warning("No update action?")
        return None, resource

    if updated_last_action.succeeded:
        logger.info(_successful_action_output(type_str, resource, "updated"))

        if tag is not None:
            forge.tag(resource_updated, tag)
        return None, resource

    return _handle_failed(
        updated_last_action.message, resource_updated, "update", extra_message, type_str, raise_on_fail
    )
