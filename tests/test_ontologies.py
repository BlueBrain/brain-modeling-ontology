import pytest
from rdflib import Graph
from rdflib.plugins.parsers.notation3 import BadSyntax
import glob


def test_validate_ontologies():
    """
    Tests whether the ontology files under /ontologies/bbp are correctly formatted
    """
    for filepath in glob.glob(f"./ontologies/bbp/*.ttl"):
        graph = Graph()
        try:
            graph.parse(filepath, format="turtle")
        except BadSyntax:
            pytest.fail(f"File {filepath} does not validate")
