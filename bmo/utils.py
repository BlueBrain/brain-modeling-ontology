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
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
MBA = Namespace("http://api.brain-map.org/api/v2/data/Structure/")

BRAIN_REGION_ONTOLOGY_URI = "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/brainregion"
CELL_TYPE_ONTOLOGY_URI = "http://bbp.epfl.ch/neurosciencegraph/ontologies/core/celltypes"

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
