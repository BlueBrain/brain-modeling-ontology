import io
from contextlib import redirect_stdout
from typing import Optional, Tuple

from kgforge.core import KnowledgeGraphForge, Resource


ALREADY_EXISTS_ERROR = " already exists in project"
ALREADY_DEPRECATED_ERROR = "is deprecated"

SHACL_SCHEMA_ID = "https://bluebrain.github.io/nexus/schemas/shacl-20170720.ttl"
ONTOLOGY_SCHEMA_ID = "https://neuroshapes.org/dash/ontology"
CLASS_SCHEMA_ID = "https://neuroshapes.org/dash/ontologyentity"


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


def register_schema(
        forge: KnowledgeGraphForge, schema_filepath: str, schema_resource: Resource, tag: str
) -> Tuple[Optional[Exception], Resource]:
    """Register schema to the store."""
    return _register_update(
        forge, schema_resource, schema_id=SHACL_SCHEMA_ID,
        tag=tag, extra_message=f"from file {schema_filepath}",
        raise_on_fail=False, type_str="Schema"
    )


def register_ontology(
        forge: KnowledgeGraphForge, ontology_filepath: str, ontology_resource: Resource, tag: str
) -> Tuple[Optional[Exception], Resource]:

    return _register_update(
        forge, ontology_resource,
        schema_id=ONTOLOGY_SCHEMA_ID, tag=tag, type_str="Ontology",
        extra_message=f"from file {ontology_filepath}"
    )


def _process_already_existing_resource(forge: KnowledgeGraphForge, resource: Resource):
    resource_json = forge.as_json(resource)
    resource_id = resource_json.pop("@id", resource_json.pop("id", None))
    resource_id = forge._model.context().expand(resource_id)
    # resource_json.pop("@type", resource_json.pop("type", None))
    resource_updated = forge.from_json(resource_json)
    existing_resource = forge.retrieve(resource_id)
    resource_updated.id = existing_resource.id
    if hasattr(resource, "context"):
        resource_updated.context = resource.context
    # resource_updated.type = existing_resource.type
    resource_updated._store_metadata = existing_resource._store_metadata
    return resource_updated


def _handle_failed(act, resource, action_type, extra_message, type_str, raise_on_fail):
    message = f"Failed to {action_type} {type_str.lower()}:{resource.get_identifier()} " \
              f"{extra_message}: {act.message}"
    print(message)
    ex = Exception(message)
    if raise_on_fail:
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
    resource_retrieved = forge.retrieve(resource.get_identifier())

    if resource_retrieved is None:
        print(
            f"{type_str} {resource.get_identifier()} "
            f"cannot be deprecated because it cannot be retrieved"
        )
        return None, resource

    with redirect_stdout(io.StringIO()):
        forge.deprecate(resource_retrieved)

    last_action = resource_retrieved._last_action

    if not last_action:
        print("No deprecation action?")
        return None, resource_retrieved

    if last_action.succeeded:
        print(_successful_action_output(type_str, resource_retrieved, "deprecated"))
        return None, resource_retrieved

    if ALREADY_DEPRECATED_ERROR in last_action.message:
        print(f"{type_str} {resource_retrieved.get_identifier()} already deprecated.")
        return None, resource_retrieved

    return _handle_failed(
        last_action, resource_retrieved, "deprecate", extra_message, type_str, raise_on_fail
    )


def _register_update(
        forge: KnowledgeGraphForge, resource: Resource, schema_id: str, tag: str,
        type_str, extra_message="", raise_on_fail=True
) -> Tuple[Optional[Exception], Resource]:

    with redirect_stdout(io.StringIO()):
        forge.register(resource, schema_id=schema_id)

    last_action = resource._last_action

    if not last_action:
        print("No registration action?")
        return None, resource

    if last_action.succeeded:
        print(_successful_action_output(type_str, resource, "registered"))

        if tag is not None:
            forge.tag(resource, tag)
        return None, resource

    if ALREADY_EXISTS_ERROR not in last_action.message:
        return _handle_failed(
            last_action, resource, "register", extra_message, type_str, raise_on_fail
        )

    print(f"{type_str} {resource.get_identifier()} already exists, updating...")
    resource_updated = _process_already_existing_resource(forge, resource)

    with redirect_stdout(io.StringIO()):
        forge.update(resource_updated)

    updated_last_action = resource_updated._last_action

    if not updated_last_action:
        print("No update action?")
        return None, resource

    if updated_last_action.succeeded:
        print(_successful_action_output(type_str, resource, "updated"))

        if tag is not None:
            forge.tag(resource_updated, tag)
        return None, resource

    return _handle_failed(
        updated_last_action, resource_updated, "update", extra_message, type_str, raise_on_fail
    )
