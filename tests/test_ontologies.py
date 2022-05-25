import pytest
from rdflib import Graph, Namespace
from rdflib.plugins.parsers.notation3 import BadSyntax
import glob

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


def test_validate_ontologies():
    """
    Tests whether the ontology files under /ontologies/bbp are correctly formatted
    """
    for filepath in glob.glob(f"./ontologies/bbp/*.ttl"):
        graph = Graph()
        try:
            for prefix, mapping in PREFIX_MAPPINGS.items():
                graph.bind(prefix, Namespace(mapping))
            graph.parse(filepath, format="turtle")
        except BadSyntax:
            pytest.fail(f"File {filepath} does not validate")