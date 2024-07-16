import requests
import argparse
import json
from bmo.logger import logger
from bmo.argument_parsing import define_arguments
from bmo.utils import get_request_headers, get_obp_projects
from bmo.views import View, create_aggregate_es_view, create_es_view


OBP_RELEASE_CHANGING_VIEWS = {
    "bbp/atlas": {"tag": "{atlas_tag}",
                  "resource_types": [
                      "https://bbp.epfl.ch/ontologies/core/bmo/MTypeDensity",
                      "https://bbp.epfl.ch/ontologies/core/bmo/METypeDensity",
                      "https://neuroshapes.org/CellDensityDataLayer",
                      "http://www.w3.org/2002/07/owl#Ontology",
                      "https://neuroshapes.org/ParcellationOntology"
                  ],
                  "resource_schemas": [
                      "https://neuroshapes.org/dash/brainparcellationmesh",
                      "https://neuroshapes.org/dash/atlasrelease",
                      "https://neuroshapes.org/dash/volumetricdatalayer",
                      "https://neuroshapes.org/dash/cellrecordseries",
                      "https://neuroshapes.org/dash/atlasspatialreferencesystem",
                      "https://neuroshapes.org/dash/recordseries"
                  ]},
    "neurosciencegraph/datamodels": {
        "tag": "{bmo_tag}",
        "resource_types": [
            "http://www.w3.org/2002/07/owl#Class",
            "http://www.w3.org/2002/07/owl#Ontology"
        ]}
}

DATASET_ES_VIEW_ID = "https://bbp.epfl.ch/neurosciencegraph/data/views/es/dataset"

OBP_RELEASE_FIXED_PROJECTS = [
    "bbp/agents"
    "bbp/licenses"
    "bbp/protocols",
    "bbp/inference-rules"
]


def _check_status(response: requests.Response):
    response_json = response.json()
    if str(response.status_code).startswith('2'):
        return True
    elif response.status_code == '409':  # Conflict
        logger.info(f"- Conflict registering the ES view. Reason: {response_json['reason']}")
        return True
    logger.info(f"- Error registering the ES view. Reason: {response_json['reason']}")
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
        print(view_args['tag'])
        view_id = f"https://bbp.epfl.ch/data/{view_bucket}/es_view_tag_{view_args['tag']}"
        response = create_es_view(endpoint,
                                  bucket=view_bucket,
                                  token=token,
                                  view_id=view_id,
                                  tag=view_args['tag'],
                                  mapping=mapping,
                                  resource_types=view_args['resource_types'] if 'resource_types' in view_args else None,
                                  resource_schemas=view_args['resource_schemas'] if 'resource_schemas' in view_args else None)
        if _check_status(response):
            logger.info(f"- Successfully created ES view {view_id} in {view_bucket} project")
            views_to_aggregate.append({'@id': view_id,
                                       'project': view_bucket})
        else:
            raise ValueError("Stopping the ES view creation.")

    logger.info(
        "Creating release ES views with tagged data - Finish "
    )

    # Get OBP suite projects
    obp_projects = get_obp_projects(endpoint, token)

    current_view_list = [{'@id': DATASET_ES_VIEW_ID,
                          'project': obp_p} for obp_p in obp_projects]

    # Try to retrieve the view
    aggregate_obp_view_id = f"https://bbp.epfl.ch/data/{atlas_bucket}/es_aggregate_view_obp"
    headers = get_request_headers(token)
    obp_view_response = View.get(endpoint, atlas_bucket, headers, aggregate_obp_view_id)
    obp_view_json = obp_view_response.json()

    # if the view doesn't exist, create it
    if obp_view_json['@type'] == "ResourceNotFound":

        logger.info("- Creating aggregate ES view for OBP suite projects")

        aggregate_response = create_aggregate_es_view(endpoint, atlas_bucket, token,
                                                      current_view_list, aggregate_obp_view_id)
        if _check_status(aggregate_response):
            logger.info("- Successfully created the aggregate ES view for OBP suite projects")
        else:
            raise ValueError("Stopping the ES view creation.")

    # if the view was fetched
    elif _check_status(obp_view_response):

        logger.info("- Found existing aggregate ES view for OBP suite projects")
        obp_view_payload = obp_view_json['_source']

        # check the list of projects in the views
        if set(obp_view_payload['views']) != set(current_view_list):

            logger.info("- Project list changed! - Updating aggregate ES view for OBP suite projects")
            obp_view_payload['views'] = current_view_list
            updated_response = View.update(endpoint, atlas_bucket, headers, obp_view_payload,
                                           view_id=aggregate_obp_view_id,
                                           rev=obp_view_json['_rev'])
            if _check_status(updated_response):
                logger.info("- Successfully updated aggregate ES view for OBP suite projects")
            else:
                raise ValueError("Stopping the ES view creation.")

    views_to_aggregate.append({'@id': aggregate_obp_view_id,
                               'project': atlas_bucket})

    for fixed_project in OBP_RELEASE_FIXED_PROJECTS:
        if fixed_project not in obp_projects:
            views_to_aggregate.append({'@id': DATASET_ES_VIEW_ID,
                                       'project': fixed_project})

    logger.info(
        "Creating release Aggregate ES view - Start "
    )
    aggregate_view_id = f"https://bbp.epfl.ch/data/{atlas_bucket}/es_aggregate_view_tags_{atlas_tag}_{bmo_tag}"
    aggregate_response = create_aggregate_es_view(endpoint,
                                                  bucket=atlas_bucket,
                                                  token=token,
                                                  views=views_to_aggregate,
                                                  view_id=aggregate_view_id)
    if _check_status(aggregate_response):
        logger.info(f"- Successfully created aggregate ES view {aggregate_view_id} in {atlas_bucket} project")
    else:
        raise ValueError(f"Stopping the aggregate ES view creation. Views included: {views_to_aggregate}")

    logger.info(
        "Creating release Aggregate ES view - Finish "
    )


if __name__ == "__main__":
    # defines and receives script arguments
    parser = define_arguments(argparse.ArgumentParser())
    received_args, leftovers = parser.parse_known_args()
    register_release_es_views(received_args)
