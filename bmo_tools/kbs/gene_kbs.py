"""Utils for fetching gene data and processing the results."""
import requests

ENSEMBL_SERVER = 'http://rest.ensembl.org/'


def query_ensembl(suffix):
    r = requests.get(
        ENSEMBL_SERVER + suffix,
        headers={"Content-Type": "application/json"})
    return r.json()


def get_ensembl_id(species, gene_name):
    """Get Ensembl ID."""
    result = [
        el
        for el in query_ensembl('xrefs/symbol/%s/%s?' % (species, gene_name))
        if el["type"] == "gene"
    ]

    ensembl_id = None
    if len(result) > 0:
        ensembl_id = result[0]["id"]

    return ensembl_id


def get_gene_data(gene_name, species):
    record = {}

    ensembl_id = get_ensembl_id(species, gene_name)

    if ensembl_id:
        record["ensembl_id"] = ensembl_id
        # Get xrefs
        uniprot_ac = None
        xreflist = query_ensembl(f'xrefs/id/{ensembl_id}')
        record["xrefs"] = {}
        for el in xreflist:
            if el["dbname"] == "Uniprot_gn" and len(el["primary_id"]) == 6:
                uniprot_ac = el["primary_id"]
            record["xrefs"][el["dbname"]] = el["primary_id"]

        record["uniprot_ac"] = uniprot_ac

        # Get description and pref label
        result = query_ensembl(f'lookup/id/{ensembl_id}?')
        record["desctiption"] = result["description"]
        record["prefLabel"] = result["display_name"]

        if uniprot_ac:
            # Get related GO terms
            result = requests.get(
                "https://www.ebi.ac.uk/QuickGO/services/annotation/search/",
                params={
                    "geneProductId": f"UniProtKB:{uniprot_ac}"
                }
            )
            record["go_edges"] = []
            for el in result.json()["results"]:
                record["go_edges"].append((el["qualifier"], el["goId"]))
    return record


def get_orthologues(ensembl_id, target_species):
    result = {}
    homs = query_ensembl(f'homology/id/{ensembl_id}')
    if "data" in homs and len(homs["data"]) > 0:
        for el in homs["data"][0]["homologies"]:
            if el["type"] in ["ortholog_one2one", "ortholog_one2many"] and\
               el['target']['species'] in target_species:
                result[el['target']['species']] = el["target"]['id']
    return result
