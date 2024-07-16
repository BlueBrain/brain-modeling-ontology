from rdflib import RDFS, Namespace
from typing import Dict, List, Optional
import pandas as pd
import cachetools
import requests
from kgforge.core import KnowledgeGraphForge

MAPPING = {"β": "beta", "\xa0": " ", "–": "-", "\u2753": "?"}


SH = Namespace("http://www.w3.org/ns/shacl#")
NXV = Namespace("https://bluebrain.github.io/nexus/vocabulary/")
SHACL = Namespace("http://www.w3.org/ns/shacl#")
BMO = Namespace("https://bbp.epfl.ch/ontologies/core/bmo/")
NSG = Namespace("https://neuroshapes.org/")
SCHEMAORG = Namespace("http://schema.org/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
MBA = Namespace("http://api.brain-map.org/api/v2/data/Structure/")
NCBITAXON = Namespace("http://purl.obolibrary.org/obo/ncbitaxon#")

BRAIN_REGION_ONTOLOGY_URI = (
    "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/brainregion"
)
CELL_TYPE_ONTOLOGY_URI = (
    "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/celltypes"
)

ATLAS_PROPERTIES_TO_MERGE = [
    SCHEMAORG.hasPart,
    SCHEMAORG.isPartOf,
    RDFS.label,
    SKOS.prefLabel,
    SKOS.notation,
    SKOS.altLabel,
    MBA.color_hex_triplet,
    MBA.hemisphere_id,
    SCHEMAORG.identifier,
    BMO.representedInAnnotation,
    BMO.regionVolumeRatioToWholeBrain,
    BMO.regionVolume,
]

DEFAULT_PROJECTS = [['public', 'forge'],
                    ['public', 'hippocampus'],
                    ['public', 'multi-vesicular-release'],
                    ['public', 'ngv'],
                    ['public', 'ngv-anatomy'],
                    ['public', 'nvg'],
                    ['public', 'sscx'],
                    ['public', 'thalamus'],
                    ['public', 'topological-sampling'],
                    ['bbp', 'lnmce'],
                    ['bbp-external', 'seu'],
                    ['bbp', 'mouselight'],
                    ['bbp', 'mmb-point-neuron-framework-model'],
                    ['neurosciencegraph', 'datamodels']]


def get_request_headers(token):
    return {"Authorization": "Bearer {}".format(token),
            "mode": "cors",
            "Content-Type": "application/json",
            "Accept": "application/ld+json, application/json"}


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


def remove_non_ascii(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    if not is_ascii(content):
        for k, v in MAPPING.items():
            content = content.replace(k, v)

        for c in content:
            if ord(c) >= 128:
                content = content.replace(c, "")

        with open(filepath, "w") as f:
            f.write(content)


def _get_ontology_annotation_lang_context():
    context_dict = {}
    context_dict["label"] = {"@id": "rdfs:label", "@language": "en"}

    context_dict["prefLabel"] = {"@id": "skos:prefLabel", "@language": "en"}

    context_dict["altLabel"] = {"@id": "skos:altLabel", "@language": "en"}

    context_dict["definition"] = {"@id": "skos:definition", "@language": "en"}

    context_dict["notation"] = {"@id": "skos:notation", "@language": "en"}

    return context_dict


@cachetools.cached(cache=cachetools.LRUCache(maxsize=100))
def get_types_one(endpoint: str, token: str, org: str, project: str) -> List[str]:
    """
    Parameters
    ----------
    endpoint : str
        the nexus deployment url.
    token : str
        the nexus token.
    org : str
        the organization.
    project : str
        the project.

    Returns
    -------
    List[str]
        the list of types present in org/project.

    """
    headers = get_request_headers(token)
    agg_response = requests.get(f'{endpoint}/resources/{org}/{project}/_/?aggregations=true&deprecated=false',
                                headers=headers)
    assert agg_response.ok
    json_response = agg_response.json()
    return [i['key'] for i in json_response['aggregations']['types']['buckets']]


@cachetools.cached(cache=cachetools.LRUCache(maxsize=100))
def sorted_resources_one(endpoint: str, token: str, org: str, project: str,
                         type_: str) -> pd.DataFrame:
    config_path = "config/forge-config.yml"
    forge = KnowledgeGraphForge(config_path, bucket=f"{org}/{project}",
                                endpoint=endpoint,
                                token=token)
    q = f"""
        SELECT  ?id  ?author ?date WHERE {{
            GRAPH ?g {{
                ?id a <{type_}>;
                _deprecated false;
                _createdBy ?author;
                _createdAt ?date.
            }}
        }} GROUP BY ?id ?author ?date
        ORDER BY DESC(?date)
    """
    r = forge.sparql(q)
    return forge.as_dataframe(r)


def get_types_many(endpoint: str, token: str, projects: Optional[List[List[str]]] = None) -> Dict[str, List[str]]:
    """

    Parameters
    ----------
    endpoint : str
        the nexus deployment url.
    token : str
        the nexus token.
    projects : Optional[List[str]], optional
        List of [org, proj], see DEFAULT_PROJECTS as example. The default is to use DEFAULT_PROJECTS.

    Returns
    -------
    Dict[str, List[str]]
        a dictionary of {project: [types present]}.

    """
    if projects is None:
        projects = DEFAULT_PROJECTS
    return {f'{"/".join(p)}': get_types_one(endpoint, token, *p) for p in projects}


def projects_present(endpoint: str, token: str,
                     type_: str, projects: Optional[List[List[str]]] = None) -> List[str]:
    """

    Parameters
    ----------
    endpoint : str
        the nexus deployment url.
    token : str
        the nexus token.
    type_ : str
        a user-chosen type (full uri).
    projects : Optional[List[List[str]]], optional
        List of [org, proj], see DEFAULT_PROJECTS as example. The default is to use DEFAULT_PROJECTS.

    Returns
    -------
    List[str]
        The projects where type_ is present.

    """
    if projects is None:
        projects = DEFAULT_PROJECTS
    d = get_types_many(endpoint, token, projects)
    return [k for k, v in d.items() if type_ in v]


def sorted_resources_many(endpoint: str, token: str, type_: str,
                          projects: Optional[List[List[str]]] = None) -> pd.DataFrame:
    """

    Parameters
    ----------
    endpoint : str
        the nexus deployment url.
    token : str
        the nexus token.
    type_ : str
        a user-chosen type (full uri).
    projects : Optional[List[List[str]]], optional
        List of [org, proj], see DEFAULT_PROJECTS as example. The default is to use DEFAULT_PROJECTS.

    Returns
    -------
    pd.DataFrame
        DataFrame with project, id, author, and creation date for resources of type type_

    """
    if projects is None:
        projects = projects_present(endpoint, token, type_, DEFAULT_PROJECTS)
    return (pd.concat([sorted_resources_one(endpoint, token, *p.split('/'), type_) for p in projects],
                      keys=projects)
            .reset_index(names=['project', 'drop'])
            .drop('drop', axis=1)
            )


def select_single_from_df(df: pd.DataFrame) -> Dict[str, str]:
    """

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with project, id, author, and creation date for resources of type type_ (see sourted_resources_many).

    Returns
    -------
    Dict[str, str]
        Selects the most recent resource from the author with most resources across projects,
        returns its info(project, id, author, creation date) as a dictionary.

    """
    main_author = df.groupby('author').count().project.idxmax()
    by_main_author = df[df['author'] == main_author]
    maxdate = by_main_author['date'].max()  # NB. idxmax does not work with dates. pd.to_numeric fails to parse
    return by_main_author[by_main_author['date'] == maxdate].iloc[0].to_dict()


def select_resource(endpoint: str, token: str, type_: str,
                    projects: Optional[List[List[str]]] = None) -> Dict[str, str]:
    """

    Parameters
    ----------
    endpoint : str
        the nexus deployment url.
    token : str
        the nexus token.
    type_ : str
        a user-chosen type (full uri).
    projects : Optional[List[List[str]]], optional
        List of [org, proj], see DEFAULT_PROJECTS as example. The default is to use DEFAULT_PROJECTS.

    Returns
    -------
    Dict[str, str]
        Selects the most recent resource from the author with most resources across projects,
        returns its info(project, id, author, creation date) as a dictionary.

    """
    return select_single_from_df(sorted_resources_many(endpoint, token, type_, projects))


def delta_get(endpoint: str, relative_url: str, token):

    headers = {
        "mode": "cors",
        "Content-Type": "application/json",
        "Accept": "application/ld+json, application/json",
        "Authorization": "Bearer " + token
    }

    return requests.get(f'{endpoint}{relative_url}', headers=headers)


def get_obp_projects(endpoint: str, token: str) -> List[str]:
    res = delta_get(endpoint, "/search/suites/sbo", token=token).json()["projects"]

    return res
