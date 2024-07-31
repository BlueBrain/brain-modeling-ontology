import requests
import argparse
import json
from bmo.logger import logger
from bmo.argument_parsing import define_arguments
from bmo.utils import get_request_headers, get_obp_projects
from bmo.views import (
    View,
    create_aggregate_es_view,
    create_es_view,
    create_es_view_payload,
    create_aggregate_es_view_payload
)


OBP_RELEASE_CHANGING_VIEWS = {
    "bbp/atlas": {"tag": "{atlas_tag}",
                  "resource_types": [
                      "https://bbp.epfl.ch/ontologies/core/bmo/MTypeDensity",
                      "https://bbp.epfl.ch/ontologies/core/bmo/METypeDensity",
                      "https://neuroshapes.org/CellDensityDataLayer",
                      "https://neuroshapes.org/BrainParcellationMesh",
                      "https://neuroshapes.org/VolumetricDataLayer",
                      "https://neuroshapes.org/CellRecordSeries",
                      "https://neuroshapes.org/AtlasRelease",
                      "https://neuroshapes.org/AtlasSpatialReferenceSystem",
                      "http://www.w3.org/2002/07/owl#Ontology",
                      "https://neuroshapes.org/ParcellationOntology"
                  ]},
    "neurosciencegraph/datamodels": {
        "tag": "{bmo_tag}",
        "resource_types": [
            "http://www.w3.org/2002/07/owl#Class",
            "http://www.w3.org/2002/07/owl#NamedIndividual",
            "http://www.w3.org/2002/07/owl#Ontology"
        ]}
}

DATASET_ES_VIEW_ID = "https://bbp.epfl.ch/neurosciencegraph/data/views/es/dataset"

OBP_RELEASE_FIXED_PROJECTS = [
    "bbp/agents",
    "bbp/licenses",
    "bbp/protocols",
    "bbp/inference-rules"
]


def create_update_view(view_id, endpoint, token, bucket, **kwargs):
    # Get arguments
    payload = kwargs.get('payload', None)
    view_list = kwargs.get('view_list', None)
    is_aggregate = kwargs.get('is_aggregate', False)
    tag = kwargs.get('tag', None)
    mapping = kwargs.get('mapping', None)
    resource_types = kwargs.get('resource_types', None)
    resource_schemas = kwargs.get('resource_schemas', None)
    include_metadata = kwargs.get('include_metadata', True)
    include_deprecated = kwargs.get('include_deprecated', False)

    # Try to retrieve the view
    headers = get_request_headers(token)
    view_response = View.get(endpoint, bucket, headers, view_id)
    view_json = view_response.json()

    # if the view doesn't exist, create it
    if view_json['@type'] == "ResourceNotFound":
        if is_aggregate:
            logger.info(f"- Creating aggregate ES view {view_id}")

            create_response = create_aggregate_es_view(endpoint, bucket, token,
                                                       view_list, view_id)
        else:
            create_response = create_es_view(endpoint,
                                             bucket=bucket,
                                             token=token,
                                             view_id=view_id,
                                             tag=tag,
                                             mapping=mapping,
                                             resource_types=resource_types,
                                             resource_schemas=resource_schemas)

        if _check_status(create_response):
            logger.info("- Successfully created the aggregate ES view for OBP suite projects")
            return True
        else:
            raise ValueError("Stopping the ES view creation.")

    # if the view was fetched
    elif _check_status(view_response):
        logger.info(f"- Found existing aggregate ES view {view_id}")
        if is_aggregate:
            if view_list is None:
                raise ValueError("Aggregate views require `view_list` to be provided")
            payload = create_aggregate_es_view_payload(view_list)
        else:
            payload = create_es_view_payload(tag, mapping, resource_types,
                                             resource_schemas, include_metadata,
                                             include_deprecated)

        # check changes in payload
        changed = False
        for k, v in payload.items():
            if not k.startswith('_') and k != "@context":
                if view_json[k] != v:
                    changed = True
                    break

        if changed:
            logger.info("- View payload has changed! - Updating ES view")
            updated_response = View.update(endpoint, bucket,
                                           payload, headers,
                                           view_id=view_id,
                                           rev=view_json['_rev'])
            if _check_status(updated_response):
                logger.info("- Successfully updated aggregate ES view")
                return True
            else:
                raise ValueError(f"Error updating view {view_id}. Stopping the ES view creation.")
    else:
        raise ValueError(f"Error creating/updating view {view_id}. Stopping the ES view creation.")


def _check_status(response: requests.Response):
    response_json = response.json()
    if 200 <= response.status_code < 300:
        return True
    elif response.status_code == 409:  # Conflict
        logger.info(f"- Conflict registering the ES view. Reason: {response_json['reason']}")
        if 'already exists in project' in response_json['reason']:
            return True
    else:
        logger.info(f"- Error {response.status_code} registering the ES view. Reason: {response_json['reason']}")
        return False


def register_release_es_views(arguments: argparse.Namespace):
    """
    Parses the arguments and registers the ontologies and schemas

    :param arguments: The arguments namespace
    :type arguments: argparse.Namespace
    :return:
    """
    environment = arguments.environment
    token = arguments.token
    bmo_tag = arguments.tag if arguments.tag != "-" else None
    atlas_tag = arguments.atlas_parcellation_ontology_tag
    atlas_bucket = arguments.atlas_parcellation_ontology_bucket

    if environment == "staging":
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            'Environment argument must be either "staging" or "production" '
        )

    views_to_aggregate = []

    # Create the changing views
    with open("config/views/es_mapping.json") as f:
        mapping = json.load(f)

    tags_dict = {"bmo_tag": bmo_tag,
                 "atlas_tag": atlas_tag}

    logger.info(
        "Creating release ES views with tagged data - Start "
    )

    for view_bucket, view_args in OBP_RELEASE_CHANGING_VIEWS.items():
        view_args['tag'] = view_args['tag'].format(**tags_dict)
        view_id = f"https://bbp.epfl.ch/data/{view_bucket}/es_view_tag_{view_args['tag']}"
        success = create_update_view(view_id=view_id,
                                     endpoint=endpoint,
                                     token=token,
                                     bucket=view_bucket,
                                     tag=view_args['tag'],
                                     mapping=mapping,
                                     resource_types=view_args['resource_types'] if 'resource_types' in view_args else None,
                                     resource_schemas=view_args['resource_schemas'] if 'resource_schemas' in view_args else None)
        if success:
            logger.info(f"- Successfully created/updated ES view {view_id} in {view_bucket} project")
            views_to_aggregate.append({'@id': view_id,
                                       'project': view_bucket})
        else:
            raise ValueError(" Error in release view creation- Stopping the ES view creation.")

    logger.info(
        "Creating release ES views with tagged data - Finish "
    )

    # Add other bbp buckets into the aggregate views of atlas and datamodels
    # First get OBP suite projects
    obp_projects = get_obp_projects(endpoint, token)

    for fixed_project in OBP_RELEASE_FIXED_PROJECTS:
        if fixed_project not in obp_projects:
            views_to_aggregate.append({'@id': DATASET_ES_VIEW_ID,
                                       'project': fixed_project})

    logger.info(
        "Creating BBP release Aggregate ES view - Start "
    )
    aggregate_view_id = f"https://bbp.epfl.ch/data/{atlas_bucket}/es_aggregate_view_tags_{atlas_tag}_{bmo_tag}"
    aggregate_success = create_update_view(view_id=aggregate_view_id,
                                           endpoint=endpoint,
                                           token=token,
                                           bucket=atlas_bucket,
                                           view_list=views_to_aggregate,
                                           is_aggregate=True)
    if aggregate_success:
        logger.info(f"- Successfully created/found aggregate ES view {aggregate_view_id} in {atlas_bucket} project")
    else:
        raise ValueError(f"Stopping the aggregate ES view creation. Views included: {views_to_aggregate}")

    logger.info(
        "Creating BBP release Aggregate ES view - Finish "
    )

    # Finally create the aggregate view of OBP projects, if it doesn't already exists
    view_obp_list = [{'@id': DATASET_ES_VIEW_ID,
                      'project': obp_p} for obp_p in obp_projects]

    aggregate_obp_view_id = f"https://bbp.epfl.ch/data/{atlas_bucket}/es_aggregate_view_obp"
    aggregate_obp_success = create_update_view(view_id=aggregate_obp_view_id,
                                               endpoint=endpoint,
                                               token=token,
                                               bucket=atlas_bucket,
                                               view_list=view_obp_list,
                                               is_aggregate=True)
    if aggregate_obp_success:
        logger.info(f"- Successfully created/found aggregate ES view {aggregate_obp_view_id} in {atlas_bucket} project")
    else:
        raise ValueError(f"Stopping the aggregate ES view creation. Views included: {view_obp_list}")

    logger.info(
        "Creating OBP Aggregate ES view - Finish "
    )


if __name__ == "__main__":
    # defines and receives script arguments
    parser = define_arguments(argparse.ArgumentParser())
    received_args, leftovers = parser.parse_known_args()
    register_release_es_views(received_args)
