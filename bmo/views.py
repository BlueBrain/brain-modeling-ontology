import requests
from typing import List, Optional, Dict
from urllib.parse import quote

from bmo.utils import get_request_headers


class View:
    """Management class for view-related methods"""

    @staticmethod
    def create(endpoint: str, bucket: str, payload: Dict, headers: Dict, view_id: Optional[str]):
        """Create a view from a given payload.

        :param endpoint: url of nexus API.
        :param bucket: Label of the organization/project the view belongs to.
        :param headers: Proper headers for the HTTPS POST request.
        :param payload: JSON payload oft he view
        :param view_id: (optional) User-defined ID of the view, given as an IRI
            which is not URL encoded.
        :return: The Nexus metadata of the created view.
        """
        path = "/".join([endpoint, "views", bucket])
        if view_id is not None:
            payload["@id"] = view_id

        return requests.post(url=path, headers=headers, json=payload)

    @staticmethod
    def get(endpoint: str, bucket: str, headers: Dict, view_id: str):
        """Retrieve a view from a given id.

        :param endpoint: url of nexus API.
        :param bucket: Label of the organization/project the view belongs to.
        :param headers: Proper headers for the HTTPS POST request.
        :param payload: JSON payload oft he view
        :param view_id: User-defined ID of the view, given as an IRI
            which is not URL encoded.
        :return: The Nexus metadata of the retrieved view.
        """
        path = "/".join([endpoint, "views", bucket, quote(view_id)])

        return requests.get(url=path, headers=headers)

    @staticmethod
    def update(endpoint: str, bucket: str, payload: Dict, headers: Dict, view_id: str, rev: str):
        """Create a view from a given payload.

        :param endpoint: url of nexus API.
        :param bucket: Label of the organization/project the view belongs to.
        :param payload: JSON payload oft he view
        :param headers: Proper headers for the HTTPS POST request.
        :param view_id: User-defined ID of the view, given as an IRI
            which is not URL encoded.
        :return: The Nexus metadata of the updated view.
        """
        path = "/".join([endpoint, "views", bucket, f"{quote(view_id)}" + f"?rev={rev}"])

        return requests.put(url=path, headers=headers, json=payload)

    @staticmethod
    def deprecate(endpoint: str, bucket: str, headers: Dict, view_id: str, rev: str):
        """
        Update a ElasticSearch view. The esview object is most likely the returned value of a
        nexus.views.fetch(), where some fields where modified, added or removed.
        Note that the returned payload only contains the Nexus metadata and not the
        complete view.

        :param endpoint: url of nexus API.
        :param bucket: Label of the organization/project the view belongs to.
        :param headers: Proper headers for the HTTPS POST request.
        :param User-defined ID of the view, given as an IRI
        :param rev: The previous revision you want to update from.
            If not provided, the rev from the view argument will be used.
        :return: A payload containing only the Nexus metadata for this updated view.
        """

        path = "/".join([endpoint, "views", bucket, f"{quote(view_id)}" + f"?rev={rev}"])

        return requests.delete(path, headers=headers)


def create_es_view(endpoint: str,
                   bucket: str,
                   token: str,
                   view_id: Optional[str] = None,
                   tag: Optional[str] = None,
                   mapping: Optional[Dict] = {},
                   resource_types: Optional[List[str]] = None,
                   resource_schemas: Optional[List[str]] = None,
                   include_metadata: Optional[bool] = True,
                   include_deprecated: Optional[bool] = False) -> requests.Response:
    """ Create an ElasticSearch view.

    :param endpoint: url of nexus API.
    :param bucket: Label of the organization/project the view belongs to.
    :param mapping: ElasticSearch mapping
        (see https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping.html for more details).
    :param view_id: (optional) User-defined ID of the view, given as an IRI
        which is not URL encoded.
    :param resource_schemas: (optional) IDs of the schemas which will be used to filter the resources
        indexed in the view.
    :param resource_types: (optional) IDs of the types which will be used to filter the resources
        indexed in the view.
    :param tag: (optional) tag to use for filtering the resources which will be indexed in the view.
    :param include_metadata: whether to include Nexus metadata in the index
    :param include_deprecated: whether to include deprecated resources in the index
    :return: The Nexus metadata of the created view.
    """
    payload = {
        "@type": ["View", "ElasticSearchView"],
        "mapping": mapping,
        "includeMetadata": include_metadata,
        "includeDeprecated": include_deprecated
    }

    if resource_schemas:
        payload["resourceSchemas"] = resource_schemas
    if resource_types:
        payload["resourceTypes"] = resource_types
    if tag is not None:
        payload["resourceTag"] = tag
    payload["sourceAsText"] = False

    headers = get_request_headers(token)

    return View.create(endpoint, bucket, payload, headers, view_id)


def create_aggregate_es_view(endpoint: str,
                             bucket: str,
                             token: str,
                             views: List[Dict],
                             view_id: Optional[str] = None) -> requests.Response:
    views_data = []
    for v in views:
        v_data = {
            "project": v["project"],
            "viewId": v["@id"]
        }

        views_data.append(v_data)

    payload = {
        "@type": [
            "View",
            "AggregateElasticSearchView"
        ],
        "views": views_data
    }

    headers = get_request_headers(token)

    return View.create(endpoint, bucket, payload, headers, view_id)
