#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jan 23 17:05:45 2024

@author: ricardi
"""
import os
import json
import requests
from typing import Dict, List

from bmo.utils import select_resource, get_request_headers

from kgforge.core import KnowledgeGraphForge


def save_resource(dirpath: str, class_name: str, resource_json: str) -> None:
    """Save a resource into json format"""
    path = f"{dirpath}/{class_name}.json"
    with open(path, 'w') as ofile:
        json.dump(resource_json, ofile, indent=4)


def fetch_multiple_resources(token: str,
                             endpoint: str,
                             to_fetch: List[Dict]) -> Dict:
    headers = get_request_headers(token)
    url = f"{endpoint}/multi-fetch/resources"
    resource_format = 'source'
    resources = [r for r in to_fetch.values()]
    data = {'format': resource_format, 'resources': resources}
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    response_json = response.json()
    return response_json['resources']


if __name__ == "__main__":
    # Get example resources from OBP projects, one resource per class
    token = os.environ['token']  # provide in terminal doing `export token=mytoken`
    bucket = "neurosciencegraph/datamodels"
    config_path = "config/forge-config.yml"
    endpoint = "https://bbp.epfl.ch/nexus/v1"
    # Add the example resource to the tests directory to be included in the unit tests
    examples_directory = "./tests/data/example_resources/"
    forge = KnowledgeGraphForge(config_path, bucket=bucket, token=token, endpoint=endpoint, debug=True)
    context = forge.get_model_context()

    class_names = [""]  # for example "EModelWorkflow" or a list
    to_fetch = []
    file_names = []
    for class_name in class_names:
        class_expanded = context.expand(class_name)
        result = select_resource(endpoint, token, class_expanded)
        if result:
            file_names.append(class_name.lower())
            to_fetch.append({'id': result['id'], 'project': result['project']})
    # Finally fetch resources
    resources = fetch_multiple_resources(token=token, endpoint=endpoint, to_fetch=to_fetch)
    for file_name, response_resource in zip(file_names, resources):
        example_resource = response_resource['value']
        if not hasattr(example_resource, '@context'):
            example_resource['@context'] = "https://neuroshapes.org"
        save_resource(examples_directory, file_name, example_resource)
