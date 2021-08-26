"""Utils for querying Reactome and processing the results."""
import requests
import copy
import numpy as np

from collections import defaultdict


REACTOME_ENDPOINT = "https://reactome.org/ContentService"


def query_reactome(record):
    r = requests.get(f"{REACTOME_ENDPOINT}/data/query/{record}")
    return r.json()


def get_elements(data, key):
    elements = []
    if key in data:
        elements = [
            el["stId"] if isinstance(el, dict) else el
            for el in data[key]
        ]
    return elements


def get_orthologs(data):
    return get_elements(data, "orthologousEvent")


def get_subpathways(data):
    subpathways = []
    if "hasEvent" in data:
        subpathways = [
            el["stId"]
            for el in data["hasEvent"]
            if el["className"] == "Pathway"
        ]
    return subpathways


def get_reactions(data):
    reactions = []
    if "hasEvent" in data:
        reactions = [
            el["stId"]
            for el in data["hasEvent"]
            if el["className"] == "Reaction"
        ]
    return reactions


def get_preceding_events(data):
    return get_elements(data, "precedingEvent")


def get_reaction_participants(data):
    return get_elements(data, "input"), get_elements(data, "output")


def get_complex_components(data):
    return get_elements(data, "hasComponent")


def get_set_members(data):
    return get_elements(data, "hasMember")


def process_literature(data):
    return [
        el["pubMedIdentifier"] for el in data
        if "pubMedIdentifier" in el
    ] if not isinstance(data, float) else np.nan


def process_cross_reference(data):
    return [
        f"{el['databaseName']}:{el['identifier']}" for el in data
    ] if not isinstance(data, float) else np.nan


def process_compartment(data):
    return [
        f"{el['databaseName']}:{el['accession']}"
        for el in data
    ] if not isinstance(data, float) else np.nan


def process_summation(data):
    return data[0]["text"] if not isinstance(data, float) else np.nan


def process_species(data):
    if not isinstance(data, float):
        if isinstance(data, list):
            data = data[0]
        return data["displayName"]
    else:
        return np.nan


def clean_reactome_df(df):
    rename = {
        "stId": "reactome_id",
        "stIdVersion": "reactome_id_version",
        "disaplayName": "prefLabel",
        "name": "synonyms"
    }
    remove = [
        "physicalEntity",
        "databaseName",
        "identifier",
        "className",
        "inferredTo",
        "schemaClass",
        "hasComponent",
        "speciesName"
    ]

    if "species" in df.columns:
        df["species"] = df["species"].apply(process_species)
    elif "speciesName" in df.columns:
        df["species"] = df["speciesName"]

    for k, v in rename.items():
        if k in df.columns:
            df = df.rename(columns={k: v})
    for el in remove:
        if el in df.columns:
            df = df.drop(columns=[el])
    if "evidenceType" in df:
        df["evidenceType"] = df["evidenceType"].apply(
            lambda x: x["displayName"] if not isinstance(x, float) else np.nan)
    if "compartment" in df:
        df["compartment"] = df["compartment"].apply(process_compartment)
    if "summation" in df:
        df["summation"] = df["summation"].apply(process_summation)
    if "crossReference" in df:
        df["crossReference"] = df["crossReference"].apply(
            process_cross_reference)
    if "literatureReference" in df:
        df["literatureReference"] = df["literatureReference"].apply(
            process_literature)
    return df


def process_data_record(data):
    data = copy.deepcopy(data)

    data["reactome_page"] = f"https://reactome.org/content/detail/{data['stId']}"

    if "speciesName" in data:
        data["label"] = data["displayName"] + f" ({data['speciesName']})"

    fields_to_remove = [
        "output", "input", "hasEvent",
        "orthologousEvent", "precedingEvent"
    ]
    for f in fields_to_remove:
        if f in data:
            del data[f]

    if "goBiologicalProcess" in data:
        data["goBiologicalProcess"] =\
            f"{data['goBiologicalProcess']['databaseName']}:{data['goBiologicalProcess']['accession']}"

    return data


def get_pathway_data(query):
    edges = defaultdict(set)
    pathways = {}

    data = query_reactome(query)
    props = process_data_record(data)
    props["@type"] = {"PATHWAY"}
    pathways[query] = props

    for o in get_orthologs(data):
        edges[(query, o)].add("hasOrthologue")
    for r in get_reactions(data):
        edges[(r, query)].add("isPartOf")

    for p in get_subpathways(data):
        edges[(p, query)].add("isPartOf")
        new_pathways, new_edges = get_pathway_data(p)
        pathways.update(new_pathways)
        for e, values in new_edges.items():
            edges[e] = edges[e].union(values)

    return pathways, edges


def retreive_protein_data(catalyst):
    data = query_reactome(catalyst)

    identifier = catalyst
    props = copy.deepcopy(data)
    if "speciesName" in props:
        props["label"] = props["displayName"] + f" ({props['speciesName']})"
    if "referenceEntity" in data:
        if data["referenceEntity"]["databaseName"] == "UniProt":
            props["gene"] = data['referenceEntity']['identifier']
        elif data["referenceEntity"]["databaseName"] == "ChEBI":
            identifier = f"CHEBI_{data['referenceEntity']['identifier']}"

    if "summation" in data:
        props["description"] = data["summation"][0]["text"]
        del props["summation"]

    remove = [
       "hasMember", "schemaClass", "hasComponent", "referenceEntity"
    ]
    for k in remove:
        if k in props:
            del props[k]
    components = get_complex_components(data)
    members = get_set_members(data)
    return identifier, props, components, members


def get_protein_data(catalyst, reaction_id, all_catalysts, visited=None):
    if visited is None:
        visited = set()

    edges = defaultdict(set)
    edges_to_remove = set()
    catalysts = {}

    if catalyst not in visited:
        visited.add(catalyst)
        identifier, props, components, members = retreive_protein_data(
            catalyst)
        if props["className"] == "Complex":
            props["@type"] = {"COMPLEX"}
            catalysts[identifier] = props
            for c in components:
                edges[(c, identifier)].add("isPartOf")
                new_edges, new_edges_to_remove = get_protein_data(
                    c, reaction_id, all_catalysts, visited)
                edges_to_remove.update(new_edges_to_remove)
                for e, values in new_edges.items():
                    edges[e] = edges[e].union(values)
        elif props["className"] == "Set":
            edges_to_remove.add((reaction_id, identifier))
            for m in members:
                edges[(reaction_id, m)].add("catalyzedBy")
                new_edges, new_edges_to_remove = get_protein_data(
                    m, reaction_id, all_catalysts, visited)
                edges_to_remove.update(new_edges_to_remove)
                for e, values in new_edges.items():
                    edges[e] = edges[e].union(values)
        else:
            props["@type"] = (
                {"PROTEIN"}
                if props["className"] != "Chemical Compound"
                else {"METABOLITE"}
            )
            catalysts[identifier] = props
    all_catalysts.update(catalysts)
    return edges, edges_to_remove


def retreive_reactant_data(reactant):
    data = query_reactome(reactant)
    chebi = None
    edges = {}
    if data["className"] == "Chemical Compound":
        if "referenceEntity" in data:
            data = data["referenceEntity"]
            chebi = f"CHEBI_{data['identifier']}"

        if "crossReference" in data:
            for el in data["crossReference"]:
                if el['databaseName'] == "ChEBI":
                    chebi = f"CHEBI_{el['identifier']}"

        data["chebi_id"] = chebi
        data["@type"] = {"METABOLITE"}
        return {reactant: data}, edges
    else:
        prots = {}
        edges, edges_to_remove = get_protein_data(reactant, None, prots)
        if len(edges_to_remove) > 0:
            print(edges_to_remove)
        return prots, edges


def get_reaction_data(reaction_id, reactant_data):
    data = query_reactome(reaction_id)
    props = process_data_record(data)
    props["@type"] = {"BIOCHEMICAL_REACTION"}
    new_edges = defaultdict(set)
    edge_props = {}
    for e in get_preceding_events(data):
        new_edges[(e, reaction_id)].add("preceeds")

    i, o = get_reaction_participants(data)
    for ii in i:
        if ii not in reactant_data:
            substrate_data, ii_edges = retreive_reactant_data(ii)
            new_edges.update(ii_edges)
            reactant_data.update(substrate_data)
        new_edges[(reaction_id, ii)].add("substrate")
    for oo in o:
        if oo not in reactant_data:
            product_data, oo_edges = retreive_reactant_data(oo)
            new_edges.update(oo_edges)
            reactant_data.update(product_data)
        new_edges[(reaction_id, oo)].add("product")

    if "catalystActivity" in data:
        catalysts = [el['dbId'] for el in data["catalystActivity"]]
        for c in catalysts:
            catalyst_data = query_reactome(c)
            enzyme = catalyst_data["physicalEntity"]["stId"]
            new_edges[(reaction_id, enzyme)].add("catalyzedBy")
            catalyst_props = {}
            if "name" in catalyst_data:
                catalyst_props["activity_name"] = catalyst_data["name"]
            if "databaseName" in catalyst_data and "dbId" in catalyst_data:
                catalyst_props["go_term"] =\
                    f"{catalyst_data['databaseName']}:{catalyst_data['dbId']}"
            if "url" in catalyst_data:
                catalyst_props["url"] = catalyst_data["url"]
            edge_props[(reaction_id, enzyme)] = catalyst_props
    return props, new_edges, edge_props


def get_regulation_relations(regulation, reactant_data):
    data = query_reactome(regulation)
    edge_type = (
        "positivelyRegulates"
        if data["className"] == "PositiveRegulation"
        else "negativelyRegulates"
    )
    if data["regulator"]["stId"] not in reactant_data:
        regulator = data["regulator"]["stId"]
        chebi, reg_data = retreive_reactant_data(regulator)
        reg_data["@type"] = {"METABOLITE"}
        reactant_data[regulator] = reg_data
    else:
        regulator = data["regulator"]["stId"]
    return regulator, edge_type
