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


def _register_ontology_resource(forge, ontology_json, ontology_path):
    ontology_json = copy.deepcopy(ontology_json)
    del ontology_json["@context"]
    ontology_resource = forge.from_json(ontology_json)
    ontology_resource.distribution = forge.attach(
        ontology_path, content_type="text/turtle")
    forge.register(ontology_resource, schema_id="datashapes:ontology")
    return ontology_resource


def register_ontology(forge, ontology_graph, context, path, prefix, tag=None):
    """Register ontology resource to the store.

    Try registering ontology to the store of the initialized forge.
    if ontology is too large, remove `defines` relationships from the ontology
    to classes and retry registering. If ontology exisits, update it.
    """
    # Frame ontology given the provided context
    ontology_json = frame_ontology(ontology_graph, context)

    # Register ontology as is
    ontology_resource = _register_ontology_resource(forge, ontology_json, path)

    if ontology_resource._last_action.error == "RegistrationError":
        if TOO_LARGE_ERROR in ontology_resource._last_action.message:
            print("Ontology is too large, removing 'defines' relationships...\n")
            # If ontology is too large (too many classes), we need to remove
            # 'defines', relationships otherwise the payload explodes
            remove_defines_relation(ontology_graph, prefix)
            # Retry registering after the `define` rels are removed
            ontology_json = frame_ontology(ontology_graph, context)
            print("Retrying registration...\n")
            ontology_resource = _register_ontology_resource(
                forge, ontology_json, path)

    # Tag if the registration was successful
    if ontology_resource._last_action.succeeded is True and tag:
        print("Registration successful, tagging...\n")
        forge.tag(ontology_resource, tag)

    if not ontology_resource._last_action.succeeded and ALREADY_EXISTS_ERROR in ontology_resource._last_action.message:
        print("Ontology already exists, updating...\n")
        # Update and tag if 'already exists' error was encountered
        upd_ontology_json = forge.as_json(ontology_resource)
        existing_ontology_resource = forge.retrieve(upd_ontology_json["@id"])
        del upd_ontology_json["@id"] 
        del upd_ontology_json["@type"]
        ontology_resource = forge.from_json(upd_ontology_json)
        ontology_resource.id = existing_ontology_resource.id
        ontology_resource.type = existing_ontology_resource.type
        ontology_resource._store_metadata =\
            existing_ontology_resource._store_metadata
        forge.update(ontology_resource)
        if tag:
            forge.tag(ontology_resource, tag)


def find_ontology_resource(graph):
    """Find the ontology resource by label."""
    for s in graph.subjects(RDF.type, OWL.Ontology):
        return s
    else:
        raise ValueError(
            "Ontology resource with the specified label is not found")


def add_defines_relation(graph, prefix):
    """Add prefix:defines relationship from the ontology to every class."""
    ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef(f"{prefix}defines")
    graph.add((defines_rel, RDF.type, OWL.ObjectProperty))
    graph.add((defines_rel, RDFS.label, rdflib.Literal("defines", lang="en")))

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.add((ontology, defines_rel, c))


def remove_defines_relation(graph, prefix):
    """Add prefix:defines relationship from the ontology to every class."""
    ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef(f"{prefix}defines")
    graph.add((defines_rel, RDF.type, OWL.ObjectProperty))
    graph.add((defines_rel, RDFS.label, rdflib.Literal("defines", lang="en")))

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.remove((ontology, defines_rel, c))


def _process_blank_nodes(ontology_graph, source, blank_node, triples_to_remove):
    if isinstance(blank_node, rdflib.term.BNode):
        for (p, o) in ontology_graph.predicate_objects(blank_node):
            triples_to_remove.append((blank_node, p, o))
        rel = None
        target = None
        for o in ontology_graph.objects(blank_node, OWL.onProperty):
            rel = o
        for o in ontology_graph.objects(blank_node, OWL.someValuesFrom):
            target = o
        if target is None:
            for o in ontology_graph.objects(blank_node, OWL.hasValue):
                target = o
        ontology_graph.add((source, rel, target))


def restrictions_to_triples(ontology_graph):
    """Convert restrictions on relationships to simple RDF triples."""
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


def frame_classes(ontology_graph, context, prefix):
    """Frame ontology classes into JSON-LD payloads."""
    frame_json_class = {
        "@context": context,
        "@type": str(OWL.Class),
        "@embed": True
    }

    ontology = find_ontology_resource(ontology_graph)

    class_jsons = []
    for current_class in ontology_graph.subjects(RDF.type, OWL.Class):
        current_class_graph = rdflib.Graph()
        for (p, o) in ontology_graph.predicate_objects(current_class):
            current_class_graph.add((current_class, p, o))
            current_class_graph.add(
                (current_class, rdflib.URIRef(f"{prefix}isDefinedBy"), ontology))

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


def register_classes(forge, class_jsons, tag=None):
    """Register ontology classes to the store."""
    for class_json in class_jsons:
        resource = forge.from_json(class_json)
        forge.register(resource, schema_id="datashapes:ontologyentity")
        if resource._last_action.succeeded is True and tag is not None:
            forge.tag(resource, tag)
        if resource._last_action.error == "RegistrationError":
            existing_ontology_resource = forge.retrieve(forge.as_json(resource)["@id"])
            resource = forge.as_json(resource)
            del resource["@id"]
            del resource["@type"]
            resource = forge.from_json(resource)
            resource.id = existing_ontology_resource.id
            resource.type = existing_ontology_resource.type
            resource._store_metadata = existing_ontology_resource._store_metadata
            forge.update(resource)
            if tag is not None:
                forge.tag(resource, tag)


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


def replace_is_defined_by_uris(graph, uri_mapping):
    """Replace targets of `isDefinedBy` rel with Nexus URIs."""
    triples_to_add = set()
    triples_to_remove = set()
    for s, p, o in graph.triples((None, RDFS.isDefinedBy, None)):
        is_defined_by = str(o)
        for k in uri_mapping:
            if is_defined_by.startswith(k):
                triples_to_add.add((s, p, rdflib.URIRef(uri_mapping[k])))
                triples_to_remove.add((s, p, o))

    for el in triples_to_remove:
        graph.remove(el)
    for el in triples_to_add:
        graph.add(el)
