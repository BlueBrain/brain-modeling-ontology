from rdflib import Namespace

MAPPING = {
    "β": "beta",
    "\xa0": " ",
    "–": "-",
    "\u2013":"?"
}


SH = Namespace("http://www.w3.org/ns/shacl#")
NXV = Namespace("https://bluebrain.github.io/nexus/vocabulary/")
SHACL = Namespace('http://www.w3.org/ns/shacl#')
BMO = Namespace("https://bbp.epfl.ch/ontologies/core/bmo/")
NSG = Namespace("https://neuroshapes.org/")
SCHEMAORG = Namespace("http://schema.org/")

PREFIX_MAPPINGS = {
    "mso": "https://bbp.epfl.ch/ontologies/core/molecular-systems/",
    "GO": "http://purl.obolibrary.org/obo/GO_",
    "dc": "http://purl.org/dc/elements/1.1/",
    "sh": "http://www.w3.org/ns/shacl#",
    "bmo": "https://bbp.epfl.ch/ontologies/core/bmo/",
    "bmc": "https://bbp.epfl.ch/ontologies/core/bmc/",
    "nsg": "https://neuroshapes.org/",
    "nxv": "https://bluebrain.github.io/nexus/vocabulary/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xml": "http://www.w3.org/XML/1998/namespace/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "shsh": "http://www.w3.org/ns/shacl-shacl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "vann": "http://purl.org/vocab/vann/",
    "void": "http://rdfs.org/ns/void#",
    "uberon": "http://purl.obolibrary.org/obo/UBERON_",
    "obo": "http://purl.obolibrary.org/obo/",
    "schema": "http://schema.org/",
    "dcterms": "http://purl.org/dc/terms/",
    "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
    "NCBITaxon_TAXON": "http://purl.obolibrary.org/obo/NCBITaxon#_",
    "stim": "https://bbp.epfl.ch/neurosciencegraph/ontologies/stimulustypes/",
    "datashapes": "https://neuroshapes.org/dash/",
    "commonshapes": "https://neuroshapes.org/commons/",
    "ilx": "http://uri.interlex.org/base/ilx_",
    "efe": "https://bbp.epfl.ch/ontologies/core/efeatures/",
    "et": "http://bbp.epfl.ch/neurosciencegraph/ontologies/etypes/",
    "mt": "http://bbp.epfl.ch/neurosciencegraph/ontologies/mtypes/",
    "tt": "http://bbp.epfl.ch/neurosciencegraph/ontologies/ttypes/",
    "EFO": "http://www.ebi.ac.uk/efo/EFO_",
    "RS": "http://purl.obolibrary.org/obo/RS_",
    "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_"
}

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
