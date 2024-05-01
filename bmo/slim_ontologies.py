from typing import List, Dict
from rdflib import RDF, Graph, term, RDFS, OWL
from bmo.loading import initialise_graph


SLIM_CLASS_ATTRIBUTES = ['@id', '@type', 'label', 'subClassOf', 'deprecated']
SLIM_GRAPH_PREDICATES = [RDF.type, RDFS.label, RDFS.subClassOf,
                         term.URIRef("https://neuroshapes.org/defines"),
                         term.URIRef("http://purl.obolibrary.org/obo/ncbitaxon#has_rank")]
SLIM_GRAPH_TYPES = [OWL.Ontology, OWL.Class, OWL.NamedIndividual]


def create_slim_ontology_graph(original_graph: Graph,
                               keep_attributes: List[term.URIRef] = SLIM_GRAPH_PREDICATES,
                               keep_types: List[term.URIRef] = SLIM_GRAPH_TYPES) -> Graph:
    """Remove any property from the classes that is not in the provided list of attributes.

    :param source_graph: The original graph to be slim
    :param keep_attributes: a list with predicates to keep in the ontology graph
    """
    slim_graph = initialise_graph()
    # Only copy tripples that are in keep_attributes
    for s, p, o in original_graph:
        # remove blank nodes
        if p in keep_attributes:
            if p == RDF.type:
                if o in keep_types:
                    slim_graph.add((s, p, o))
            elif not isinstance(o, term.BNode):
                # Make them simple literals
                if isinstance(o, term.Literal):
                    o = term.Literal(str(o))
                slim_graph.add((s, p, o))
    return slim_graph


def create_slim_classes(original_classes: List[Dict],
                        keep_attributes: List[str] = SLIM_CLASS_ATTRIBUTES) -> List[Dict]:
    """Remove any property from the classes that is not in the provided list of attributes.

    :param original_classes: the list of classes to be slim
    :param keep_attributes: a list with predicates to keep in the class
    """
    new_classes = [{k: v for k, v in oclass.items() if k in keep_attributes}
                   for oclass in original_classes]
    return new_classes


def get_slim_ontology_id(original_id: term.URIRef) -> term.URIRef:
    """Add '_slim' to the usual name of the ontology id"""
    base_uri = str(original_id) if not str(original_id).endswith("/") else str(original_id)[:-1]
    return term.URIRef(f"{base_uri}_slim")
