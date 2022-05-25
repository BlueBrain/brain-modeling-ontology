"""Utils for processing ontologies."""
import copy
import json
from pyld import jsonld

from collections import OrderedDict

import rdflib
from rdflib import OWL, RDF, RDFS, XSD
from rdflib.paths import OneOrMore

TOO_LARGE_ERROR = "the request payload exceed the maximum configured limit"
ALREADY_EXISTS_ERROR = " already exists in project"


def graph_free_jsonld(jsonld_doc, context=None):
    if "@graph" in jsonld_doc and len(jsonld_doc["@graph"]) > 0:
        graph_free_jsonld_doc = jsonld_doc["@graph"][0]
        if not context:
            context = jsonld_doc["@context"]
        graph_free_jsonld_doc["@context"] = context
        graph_free = OrderedDict(graph_free_jsonld_doc)
        graph_free["@context"] = context
        graph_free.move_to_end("@context", last=False)
        return graph_free
    else:
        return jsonld_doc


def frame_ontology(ontology_graph, context):
    """Frame ontology into a JSON-LD payload."""
    onto_string = ontology_graph.serialize(
        format="json-ld", auto_compact=True, indent=2)
    onto_json = json.loads(onto_string)
    frame_json = {
        "@context": context,
        "@type": str(OWL.Ontology),
        "@embed": True,
        "nsg:defines": [{
            "@type": ["owl:Class", "owl:ObjectProperty"]
        }]
    }
    framed = jsonld.frame(onto_json, frame_json)
    framed_onto_json = graph_free_jsonld(framed)
    return framed_onto_json


def _register_ontology_resource(forge, ontology_json, ontology_path, ontology_graph, class_resources_mapped = None):

    ontology_json = copy.deepcopy(ontology_json)
    del ontology_json["@context"]
    ontology_resource = forge.from_json(ontology_json)
    dirpath = f"./{ontology_path.split('/')[-1].split('.')[0]}"
    dirpath_ttl = f"{dirpath}.ttl"
    ontology_graph.serialize(destination=dirpath_ttl, format="ttl")
    ontology_resource.distribution = [forge.attach(
        dirpath_ttl, content_type="text/turtle")]

    dirpath_json = f"{dirpath}.json"
    with open(dirpath_json, "w") as fp:
        json.dump(ontology_json, fp)
    ontology_resource.distribution.append(forge.attach(dirpath_json, content_type="application/ld+json"))

    if class_resources_mapped is not None:
        defined_types_df = forge.as_dataframe(class_resources_mapped)
        dirpath_csv = f"{dirpath}.csv"
        defined_types_df.to_csv(dirpath_csv)
        ontology_resource.distribution.append(forge.attach(dirpath_csv, content_type="text/csv"))

    forge.register(ontology_resource, schema_id="https://neuroshapes.org/dash/ontology")
    return ontology_resource


def register_ontology(forge, ontology_graph, context, path, tag=None, class_resources_mapped=None):
    """Register ontology resource to the store.


    Try registering ontology to the store of the initialized forge.
    if ontology is too large, remove `defines` relationships from the ontology
    to classes and retry registering. If ontology exists, update it.
    """
    # Frame ontology given the provided context
    ontology_json = frame_ontology(ontology_graph, context)

    # Register ontology as is
    ontology_resource = _register_ontology_resource(forge, ontology_json, path, ontology_graph, class_resources_mapped)

    if not ontology_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR not in ontology_resource._last_action.message:
        print("Ontology registration failed, removing 'defines' relationships...\n")
        # If ontology is too large (too many classes), we need to remove
        # 'defines', relationships otherwise the payload explodes
        remove_defines_relation(ontology_graph)
        # Retry registering after the `define` rels are removed
        ontology_json = frame_ontology(ontology_graph, context)
        print("Retrying registration...\n")
        ontology_resource = _register_ontology_resource(
            forge, ontology_json, path, ontology_graph, class_resources_mapped)

    if not ontology_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR in ontology_resource._last_action.message:
        # Update and tag if 'already exists' error was encountered
        print("Ontology already exists, updating...\n")
        ontology_updated = _process_already_existing_resource(forge, ontology_resource)
        forge.update(ontology_updated)
        if tag:
            forge.tag(ontology_updated, tag)
    
    # Tag if the registration was successful
    if ontology_resource._last_action.succeeded is True and tag:
        print("Registration successful, tagging...\n")
        forge.tag(ontology_resource, tag)

def _process_already_existing_resource(forge, resource):
    resource_json = forge.as_json(resource)
    resource_json.pop("@id", resource_json.pop("id", None))
    resource_json.pop("@type", resource_json.pop("type", None))
    resource_updated = forge.from_json(resource_json)
    existing_resource = forge.retrieve(resource.id)
    resource_updated.id = existing_resource.id
    resource_updated.type = existing_resource.type
    resource_updated._store_metadata = existing_resource._store_metadata
    return resource_updated


def find_ontology_resource(graph):
    """Find the ontology resource by label."""
    for s in graph.subjects(RDF.type, OWL.Ontology):
        return s
    else:
        raise ValueError(
            "Ontology resource with the specified label is not found")


def add_defines_relation(graph):
    """Add defines relationship from the ontology to every class."""
    ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef("https://neuroshapes.org/defines")
    graph.add((defines_rel, RDF.type, OWL.ObjectProperty))
    graph.add((defines_rel, RDFS.label, rdflib.Literal("defines", lang="en")))

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.add((ontology, defines_rel, c))


def remove_defines_relation(graph):
    """Add defines relationship from the ontology to every class."""
    ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef("https://neuroshapes.org/defines")

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.remove((ontology, defines_rel, c))


def _process_blank_nodes(ontology_graph, source, blank_node):
    blank_node_triples = []

    rel = None
    target = None
    for oo in ontology_graph.objects(blank_node, OWL.onProperty):
        rel = oo
    for oo in ontology_graph.objects(blank_node, OWL.someValuesFrom):
        target = oo
    if target is None:
        for oo in ontology_graph.objects(blank_node, OWL.hasValue):
            target = oo
    if target is None:
        for oo in ontology_graph.objects(blank_node, OWL.allValuesFrom):
            target = oo
    blank_node_triples.append((blank_node, rel, target))
    return rel, target, blank_node_triples


def restrictions_to_triples(ontology_graph):
    """Convert restrictions on relationships to simple RDF triples."""
    # Consider keeping restrictions in ontology and remove them in classes
    triples_to_remove = []
    for c in ontology_graph.subjects(RDF.type, OWL.Class):
        if isinstance(c, rdflib.term.BNode):
            for o in ontology_graph.objects(c, RDFS.subClassOf):
                _process_blank_nodes(ontology_graph, c, o, triples_to_remove)
                triples_to_remove.append((c, RDFS.subClassOf, o))

    for individual in ontology_graph.subjects(RDF.type, OWL.NamedIndividual):
        for o in ontology_graph.objects(individual, RDF.type):
            if isinstance(o, rdflib.term.BNode):
                _process_blank_nodes(
                    ontology_graph, individual, o, triples_to_remove)
                triples_to_remove.append((individual, RDF.type, o))

    for n in triples_to_remove:
        ontology_graph.remove(n)


def add_ontology_label(ontology_graph, ontology, label=None):
    """Add label to the ontology resource."""
    if label is None:
        for t in ontology_graph.objects(
                ontology,
                rdflib.URIRef("http://purl.org/dc/elements/1.1/title")):
            label = t.value
            break
    if not label:
        raise ValueError(
            "Ontology label is not provided and ontology does not "
            " have a title, please specify a label")

    ontology_graph.add(
        (ontology, RDFS.label, rdflib.Literal(label, datatype=XSD.string)))


def frame_classes(forge, ontology_graph, context):
    """Frame ontology classes into JSON-LD payloads."""
    frame_json_class = {
        "@context": context,
        "@type": [str(OWL.Class), str(OWL.NamedIndividual)],
        "@embed": True
    }

    ontology = find_ontology_resource(ontology_graph)

    class_jsons = []
    # Consider removing the restrictions
    for current_class in ontology_graph.subjects(RDF.type, OWL.Class):
        current_class_graph = rdflib.Graph()
        for (p, o) in ontology_graph.predicate_objects(current_class):
            if p == RDFS.subClassOf and isinstance(o, rdflib.term.BNode):
                rel, target, blank_node_triples = _process_blank_nodes(ontology_graph, current_class, o)
                current_class_graph.add((current_class, rel, target))
            else:
                current_class_graph.add((current_class, p, o))
        current_class_graph.add(
            (current_class, RDFS.isDefinedBy, ontology))

        current_class_string = current_class_graph.serialize(
            format="json-ld", auto_compact=True, indent=2)
        current_class_framed = jsonld.frame(
            json.loads(current_class_string), frame_json_class)
        current_class_framed = graph_free_jsonld(current_class_framed)

        identifier = str(current_class)
        current_class_framed["@id"] = str(identifier)

        if "subClassOf" in current_class_framed:
            if isinstance(current_class_framed["subClassOf"], list):
                item_list = []
                for item in current_class_framed["subClassOf"]:
                    if isinstance(item, str):
                        item_list.append(item)
                current_class_framed["subClassOf"] = item_list
            elif isinstance(current_class_framed["subClassOf"], dict):
                current_class_framed["subClassOf"] =\
                    current_class_framed["subClassOf"]["@id"]
            else:
                current_class_framed["subClassOf"] =\
                    [current_class_framed["subClassOf"]]

        del current_class_framed["@context"]
        class_jsons.append(current_class_framed)
    return class_jsons


def register_classes(forge, class_resources_mapped, tag=None):
    """Register ontology classes to the store."""
    for resource in class_resources_mapped:
        #resource = forge.from_json(class_json)
        forge.register(resource, schema_id="datashapes:ontologyentity")
        if resource._last_action.succeeded is True and tag is not None:
            forge.tag(resource, tag)
        if resource._last_action.error == "RegistrationError":
            resource_updated = _process_already_existing_resource(forge, resource)
            forge.update(resource_updated)
            if tag is not None:
                forge.tag(resource_updated, tag)


def normalize_uris(filename, prefix, new_filename, format="turtle"):
    """Normalize resource URIs to the provided prefix."""
    reserved_namespaces = [
        "http://www.w3.org/2004/02/skos/core",
        str(RDF), str(RDFS), str(OWL), str(XSD)
    ]

    g = rdflib.Graph()
    g.parse(filename, format=format)
    replacement = {}

    concepts = set()
    for s in g.subjects(RDF.type, OWL.Class):
        concepts.add(s)
    for s in g.subjects(RDF.type, OWL.NamedIndividual):
        concepts.add(s)
    for s in g.subjects(RDF.type, OWL.ObjectProperty):
        concepts.add(s)
    for s in g.subjects(RDF.type, OWL.AnnotationProperty):
        concepts.add(s)

    for s, p, l in g.triples((None, RDFS.label, None)):
        if s in concepts:
            for n in reserved_namespaces:
                if str(s).startswith(n):
                    break
            else:
                # if doesn't start with any of the reserved namespaces
                neuro_id = prefix + l.replace(" ", "")
                if str(s) != neuro_id:
                    replacement[s] = neuro_id

    with open(filename, "r") as f:
        content = f.read()

    for k, v in replacement.items():
        print("Replacing...")
        print("\t", "<" + str(k) + "> to <" + v + ">")
        content = content.replace("<" + str(k) + ">", "<" + v + ">")

    with open(new_filename, "w") as f:
        f.write(content)
    return replacement


def subontology_from_term(graph, entry_point, top_down=True, closed=True):
    """Get top/down or down/top subontology for a given term."""
    subgraph = rdflib.Graph()
    subgraph.namespace_manager.bind("owl", OWL)

    if top_down:
        all_terms = list(
            graph.subjects(
                RDFS.subClassOf * OneOrMore, entry_point)) + [entry_point]
    else:
        all_terms = list(
            graph.objects(
                entry_point, RDFS.subClassOf * OneOrMore)) + [entry_point]

    def add_incident_triples(term):
        new_classes = set()
        for p, o in graph.predicate_objects(term):
            if not isinstance(o, rdflib.Literal):
                if p.eq(RDFS.subClassOf):
                    # Add subClassOf triples
                    if isinstance(o, rdflib.URIRef):
                        if o in all_terms:
                            subgraph.add((term, p, o))
                        elif not closed:
                            # Add other terms (not children of the entry point)
                            subgraph.add((term, p, o))
                            new_classes.add(o)
                    else:
                        # Add triples representing other relations (through BNodes)
                        rel_to_add = False
                        for el in graph.objects(o, OWL.someValuesFrom):
                            if el in all_terms:
                                rel_to_add = True
                                break
                            elif not closed:
                                rel_to_add = True
                        if rel_to_add:
                            subgraph.add((term, p, o))
                            for onprop in graph.objects(o, OWL.onProperty):
                                subgraph.add((o, OWL.onProperty, onprop))
                                for onprop_p, onprop_o in graph.predicate_objects(
                                        onprop):
                                    subgraph.add((onprop, onprop_p, onprop_o))
                            for pp, oo in graph.predicate_objects(o):
                                subgraph.add((o, pp, oo))
                                if not closed and oo not in all_terms:
                                    new_classes.add(oo)
                elif not p.eq(RDF.type):
                    if o in all_terms:
                        subgraph.add((term, p, o))
                    elif not closed:
                        subgraph.add((term, p, o))
                        new_classes.add(o)
            else:
                # Add triples with literal objects
                subgraph.add((s, p, o))
                for pp, oo in graph.predicate_objects(p):
                    subgraph.add((p, pp, oo))
        return new_classes

    new_classes = []
    for s in all_terms:
        subgraph.add((s, RDF.type, OWL.Class))
        new_classes += add_incident_triples(s)

    # If we have open-world subontology, we add only the entities (not children
    # of the entry point) that are directly related to any of the children)
    closed = True
    for s in new_classes:
        subgraph.add((s, RDF.type, OWL.Class))
        add_incident_triples(s)
    return subgraph


def replace_is_defined_by_uris(graph, uri_mapping, ontology_uri):
    """
        Replace targets of `isDefinedBy` rel with Nexus URIs.
        Replace WebProtégé generated ontology URIs with mapped ones.
    """

    triples_to_add = set()
    triples_to_remove = set()
    for s, p, o in graph.triples((None, RDFS.isDefinedBy, None)):
        is_defined_by = str(o)
        for k in uri_mapping:
            if is_defined_by.startswith(k):
                triples_to_add.add((s, p, rdflib.URIRef(uri_mapping[k])))
                triples_to_remove.add((s, p, o))
    new_ontology_uri = ontology_uri
    if ontology_uri in uri_mapping:
        new_ontology_uri = uri_mapping[ontology_uri]
    for s, p, o in graph.triples((rdflib.term.URIRef(ontology_uri), None, None)):
        triples_to_add.add((rdflib.term.URIRef(new_ontology_uri), p, o))
        triples_to_remove.add((s, p, o))
    for s, p, o in graph.triples((None, RDF.type, None)):
        if isinstance(o, rdflib.term.BNode):
            triples_to_remove.add((s, p, o))

    for el in triples_to_remove:
        graph.remove(el)
    for el in triples_to_add:
        graph.add(el)
