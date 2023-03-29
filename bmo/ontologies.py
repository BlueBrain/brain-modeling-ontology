"""Utils for processing ontologies."""
import copy
import json
from typing import Dict

from pyld import jsonld
from kgforge.core.commons.context import Context
from collections import OrderedDict

import rdflib
from pyshacl.rdfutil import clone_graph
from rdflib import OWL, RDF, RDFS, SKOS, XSD, PROV, Literal, Namespace
from rdflib.paths import OneOrMore, ZeroOrMore, neg_path

from bmo.utils import BMO, BRAIN_REGION_ONTOLOGY_URI, NSG, SCHEMAORG, SHACL, NXV

TOO_LARGE_ERROR = "the request payload exceed the maximum configured limit"
ALREADY_EXISTS_ERROR = " already exists in project"

GENERIC_CELL_TYPES = {
        "https://bbp.epfl.ch/ontologies/core/bmo/GenericInhibitoryNeuronMType":BMO.NeuronMorphologicalType,
        "https://bbp.epfl.ch/ontologies/core/bmo/GenericExcitatoryNeuronMType":BMO.NeuronMorphologicalType,
        "https://bbp.epfl.ch/ontologies/core/bmo/GenericInhibitoryNeuronEType":BMO.NeuronElectricalType,
        "https://bbp.epfl.ch/ontologies/core/bmo/GenericExcitatoryNeuronEType":BMO.NeuronElectricalType
    }

ROOT_BRAIN_REGION = "http://api.brain-map.org/api/v2/data/Structure/997"


BASE_CELL_TYPE_CLASSES = {str(BMO.NeuronMorphologicalType):BMO.NeuronMorphologicalType,
                          str(BMO.NeuronElectricalType):BMO.NeuronElectricalType}

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

def _create_hierarchy_view(uri_having_view, view_uri, view_label, view_description, 
                           parent_hierarchy_property, children_hierarchy_property, leaf_hierarchy_property):
    triples = []
    json_object = {}
    triples.append((rdflib.term.URIRef(uri_having_view), BMO.hasHierarchyView, rdflib.term.URIRef(view_uri)))
    triples.append((rdflib.term.URIRef(view_uri), RDFS.label, Literal(view_label)))
    triples.append((rdflib.term.URIRef(view_uri), SCHEMAORG.description, Literal(view_description)))
    triples.append((rdflib.term.URIRef(view_uri), BMO.hasParentHierarchyProperty, Literal(parent_hierarchy_property)))
    triples.append((rdflib.term.URIRef(view_uri), BMO.hasChildrenHierarchyProperty, Literal(children_hierarchy_property)))
    triples.append((rdflib.term.URIRef(view_uri), BMO.hasLeafHierarchyProperty, Literal(leaf_hierarchy_property)))

    json_object["hasHierarchyView"]={
            "@id":view_uri,
            "label":view_label,
            "description":view_description,
            "hasParentHierarchyProperty":parent_hierarchy_property,
            "hasChildrenHierarchyProperty":children_hierarchy_property,
            "hasLeafHierarchyProperty":leaf_hierarchy_property
    }
    return triples, json_object


def frame_ontology(ontology_graph, context, context_json, class_resources_framed):
    """Frame ontology into a JSON-LD payload."""

    frame_json = {
        "@context": context_json,
        "@type": str(OWL.Ontology),
        "defines": [{
            "@type": ["owl:Class", "owl:ObjectProperty"],
            "subClassOf":[
                {
                    "@embed": False
                }
            ],
            "equivalentClass":[
                {
                    "@embed": False
                }
            ],
            "sameAs": [
                {
                    "@embed": False
                }
            ],
            "hasPart": [
                {
                    "@embed": False
                }
            ],
            "isPartOf": [
                {
                    "@embed": False
                }
            ],
           "@embed": True
        }]
    }
    ontology_uri = find_ontology_resource(ontology_graph)
    if str(ontology_uri) == BRAIN_REGION_ONTOLOGY_URI:
        layer_view_triples, layer_view_json  = _create_hierarchy_view(BRAIN_REGION_ONTOLOGY_URI, str(BMO.BrainLayer), "Layer", "Layer based hierarchy", 
                           "isLayerPartOf", "hasLayerPart", "hasLayerLeafRegionPart")
        
        brain_region_view_triples, brain_region_view_json  = _create_hierarchy_view(BRAIN_REGION_ONTOLOGY_URI, str(NSG.BrainRegion), "BrainRegion", "Atlas default brain region hierarchy", 
                           "isPartOf", "hasPart", "hasLeafRegionPart")
        view_triples = layer_view_triples + brain_region_view_triples

        for t in view_triples:
            ontology_graph.add(t)

    new_ontology_graph = ontology_graph
    # handle OWL.NamedIndividual with blank node type
    for indiv in ontology_graph.subjects(RDF.type, OWL.NamedIndividual):
        _types = ontology_graph.objects(indiv, RDF.type)
        bns = [bn for bn in _types if isinstance(bn, rdflib.term.BNode)]

        if bns:
            new_ontology_graph = clone_graph(ontology_graph)
            for b in bns:
                new_ontology_graph.remove((indiv, RDF.type, b))
    onto_string = new_ontology_graph.serialize(format="json-ld", auto_compact=True, indent=2)
    onto_json = json.loads(onto_string)

    framed = jsonld.frame(onto_json, frame_json,  options={"expandContext": context_json, "pruneBlankNodeIdentifiers":True})
    framed_onto_json = graph_free_jsonld(framed)
    if "skos:prefLabel" in framed_onto_json and framed_onto_json["skos:prefLabel"]:
        framed_onto_json["prefLabel"] = framed_onto_json.pop("skos:prefLabel", None)
    if "rdfs:label" in framed_onto_json and framed_onto_json["rdfs:label"]:
        framed_onto_json["label"] = framed_onto_json.pop("rdfs:label", None)    

    framed_onto_json["defines"]= class_resources_framed
    framed_onto_json["@context"] = context.iri

    if str(ontology_uri) == BRAIN_REGION_ONTOLOGY_URI:
        framed_onto_json["hasHierarchyView"] = [layer_view_json["hasHierarchyView"], brain_region_view_json["hasHierarchyView"]]
    return framed_onto_json


SYNTHETIC_SENTENCES = {
"./ontologies/bbp/bmo.ttl":{
    "synthetic":"./texts/synthetic_texts_bmo.json"
},
        "./ontologies/bbp/data-types.ttl":{
},
        "./ontologies/bbp/efeatures.ttl":{
    "synthetic":"./texts/synthetic_texts_NeuronElectrophysiologicalFeature.json"
},
        "./ontologies/bbp/mfeatures.ttl":{
    "synthetic":"./texts/synthetic_texts_NeuronMorphologicalFeature.json"
},
        "./ontologies/bbp/molecular-systems.ttl":{
    "synthetic":"./texts/synthetic_texts_Molecular_systems.json"
},
        "./ontologies/bbp/speciestaxonomy.ttl":{
    "synthetic":"./texts/synthetic_texts_Species.json"
},
        "./ontologies/bbp/stimulustypes.ttl":{
    "synthetic":"./texts/synthetic_texts_ElectricalStimulus.json"
},
        "./ontologies/bbp/celltypes.ttl":{
    "synthetic":"./texts/synthetic_texts_BrainCellType.json"
},
        "./ontologies/bbp/brainregion.ttl":{
    "synthetic":"./texts/synthetic_texts_BrainRegion.json",
    "wiki":"./texts/wiki_texts_BrainRegion.json"

}
}

def _register_schema(forge, schema_file, schema_resource, all_schema_graph, jsonld_schema_context_resource, tag):

    forge.register(schema_resource, schema_id="https://bluebrain.github.io/nexus/schemas/shacl-20170720.ttl")
    if schema_resource._last_action and not schema_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR not in schema_resource._last_action.message:
        raise Exception(f"Registration of the schema with id '{schema_resource.id}' located in '{schema_file}' failed: {schema_resource._last_action.message}...\n")

    if schema_resource._last_action and not schema_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR in schema_resource._last_action.message:
        # Update and tag if 'already exists' error was encountered
        print("Schema already exists, updating...\n")
        schema_updated = _process_already_existing_resource(forge, schema_resource)
        forge.update(schema_updated, schema_id="https://bluebrain.github.io/nexus/schemas/shacl-20170720.ttl")
        if schema_updated._last_action and schema_updated._last_action.succeeded is True and tag:
            forge.tag(schema_updated, tag)
            pass

    # Tag if the registration was successful
    if schema_resource._last_action and schema_resource._last_action.succeeded is True and tag:
        print("Schema registration successful, tagging...\n")
        forge.tag(schema_resource, tag)
        pass

def _register_ontology_resource(forge, ontology_json, ontology_path, ontology_graph, class_resources_mapped = None):

    ontology_json = copy.deepcopy(ontology_json)
    #del ontology_json["@context"]
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

    if ontology_path in SYNTHETIC_SENTENCES:
        synthetic = SYNTHETIC_SENTENCES[ontology_path].get("synthetic", None)
        wiki = SYNTHETIC_SENTENCES[ontology_path].get("wiki", None)
        if synthetic:
            ontology_resource.distribution.append(forge.attach(synthetic, content_type="text/json"))
        if wiki:
            ontology_resource.distribution.append(forge.attach(wiki, content_type="text/json"))

    forge.register(ontology_resource, schema_id="https://neuroshapes.org/dash/ontology")
    return ontology_resource


def register_ontology(forge, ontology_graph, context, context_json, path,  class_resources_mapped, class_resources_framed, tag=None):
    """Register ontology resource to the store.


    Try registering ontology to the store of the initialized forge.
    if ontology is too large, remove `defines` relationships from the ontology
    to classes and retry registering. If ontology exists, update it.
    """
    # Frame ontology given the provided context
    ontology_json = frame_ontology(ontology_graph, context, context_json, class_resources_framed)

    # Register ontology as is
    ontology_resource = _register_ontology_resource(forge, ontology_json, path, ontology_graph, class_resources_mapped)

    if ontology_resource._last_action and not ontology_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR not in ontology_resource._last_action.message:
        print("Ontology registration failed, removing 'defines' relationships...\n")
        # If ontology is too large (too many classes), we need to remove
        # 'defines', relationships otherwise the payload explodes
        remove_defines_relation(ontology_graph)
        # Retry registering after the `define` rels are removed
        ontology_json = frame_ontology(ontology_graph, context, context_json, class_resources_framed)
        print("Retrying registration...\n")
        ontology_resource = _register_ontology_resource(
            forge, ontology_json, path, ontology_graph, class_resources_mapped)

    if ontology_resource._last_action and not ontology_resource._last_action.succeeded and\
       ALREADY_EXISTS_ERROR in ontology_resource._last_action.message:
        # Update and tag if 'already exists' error was encountered
        print("Ontology already exists, updating...\n")
        ontology_updated = _process_already_existing_resource(forge, ontology_resource)
        forge.update(ontology_updated)
        if tag:
            print("Registration successful, tagging...\n")
            forge.tag(ontology_updated, tag)
            pass
    # Tag if the registration was successful
    if ontology_resource._last_action and ontology_resource._last_action.succeeded is True and tag:
        print("Registration successful, tagging...\n")
        forge.tag(ontology_resource, tag)
        pass

def _process_already_existing_resource(forge, resource):
    resource_json = forge.as_json(resource)
    resource_id = resource_json.pop("@id", resource_json.pop("id", None))
    resource_id = forge._model.context().expand(resource_id)
    #resource_json.pop("@type", resource_json.pop("type", None))
    resource_updated = forge.from_json(resource_json)
    existing_resource = forge.retrieve(resource_id)
    resource_updated.id = existing_resource.id
    if hasattr(resource, "context"):
        resource_updated.context = resource.context
    #resource_updated.type = existing_resource.type
    resource_updated._store_metadata = existing_resource._store_metadata
    return resource_updated


def find_ontology_resource(graph):
    """Find the ontology resource by type. The first one is returned"""
    for s in graph.subjects(RDF.type, OWL.Ontology):
        return s
    else:
        raise ValueError(
            "No Ontology resource was found")


def add_defines_relation(graph, ontology):
    """Add defines relationship from the ontology to every class."""
    #ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef("https://neuroshapes.org/defines")
    graph.add((defines_rel, RDF.type, OWL.ObjectProperty))
    graph.add((defines_rel, RDFS.label, rdflib.Literal("defines", lang="en")))

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.add((ontology, defines_rel, c))


def remove_defines_relation(graph):
    """Add defines relationship from the ontology to every class."""
    #ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = rdflib.URIRef("https://neuroshapes.org/defines")

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.remove((None, defines_rel, c))


def _process_blank_nodes(ontology_graph, blank_node, process_restriction=True):
    blank_node_triples = []

    rel = None
    target = None
    if process_restriction:
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
    else:
         for t in ontology_graph.triples((blank_node, None, None)):
            blank_node_triples.append(t)

    return rel, target, blank_node_triples


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


def _collect_ancestors_restrictions(ontology_graph, _class, restrictions_property =RDFS.subClassOf, restrictions_only=False):
    rels = []
    all_blank_node_triples = []
    for p, o in ontology_graph.predicate_objects(_class):
        if p == restrictions_property and isinstance(o, rdflib.term.BNode):
            rel, target, blank_node_triples = _process_blank_nodes(ontology_graph, o)
            rels.append((rel, target))
            all_blank_node_triples.extend(blank_node_triples)
        elif not restrictions_only:
            if isinstance(o, rdflib.term.BNode):
                _, _, blank_node_triples = _process_blank_nodes(ontology_graph, o, process_restriction=False)
                all_blank_node_triples.extend(blank_node_triples)
            rels.append((p,o))
    return rels, all_blank_node_triples


def frame_classes(ontology_graph, forge_context, context):
    """Frame ontology classes into JSON-LD payloads."""
    class_jsons = []
    class_ids= []
    all_blank_node_triples = []
    frame_json_class = {
        "@context": context,
        "@type": [str(OWL.Class), str(OWL.NamedIndividual)],
        "@embed": True
    }

    # Consider removing the restrictions
    cls = ontology_graph.subjects(RDF.type, OWL.Class)
    cls_int = [(c, RDFS.subClassOf) for c in cls]

    #add views
    new_classes = []
    for current_class, restrictions_property in cls_int:
        if (current_class, RDFS.subClassOf, NSG.BrainRegion) in ontology_graph:
            ontology_graph.add((current_class, BMO.hasHierarchyView, NSG.BrainRegion))
            if (current_class, NSG.hasLayerLocationPhenotype, None) in ontology_graph:
                current_class_layers = list(ontology_graph.objects(current_class, NSG.hasLayerLocationPhenotype))
                classes_relevant_for_layer = set()
                for layer in current_class_layers:
                    classes_relevant_for_layer = set(ontology_graph.objects(rdflib.term.URIRef(layer), RDFS.subClassOf*OneOrMore/SCHEMAORG.about)) # every group of layers (e.g. the Neorcotex layer class or the hippocampus layer) should link to its brain region scope (i.e the highest brain regions it applies to) through SCHEMAORG.about
                new_layered_classes = _create_property_based_hierarchy(ontology_graph, current_class, current_class_layers, classes_relevant_for_layer, SCHEMAORG.isPartOf)
                for new_c in new_layered_classes:
                    ontology_graph.add((rdflib.term.URIRef(new_c),BMO.representedInAnnotation, Literal(False, datatype=XSD.boolean)))
                new_classes.extend(new_layered_classes)
    cls_int.extend({(rdflib.term.URIRef(c), RDFS.subClassOf) for c in new_classes})

    inst = ontology_graph.subjects(RDF.type, OWL.NamedIndividual)
    cls_int.extend([(i, RDF.type) for i in inst])

    for current_class, restrictions_property in cls_int:
        current_class_graph = rdflib.Graph()
        # consider collecting transitive ancestors' restrictions only for argument provided classes
        rels, blank_node_triples = _collect_ancestors_restrictions(ontology_graph, current_class, restrictions_property=restrictions_property)

        for p, o in rels:
            current_class_graph.add((current_class, p, o))
        for t in blank_node_triples:
            current_class_graph.add(t)

        current_class_string = current_class_graph.serialize(
            format="json-ld", auto_compact=True, indent=2)
        current_class_framed = jsonld.frame(
            json.loads(current_class_string), frame_json_class)
        current_class_framed = graph_free_jsonld(current_class_framed)
        identifier = str(current_class)
        current_class_framed["@id"] = str(identifier)
        del current_class_framed["@context"]
        new_current_class_framed = _frame_class(current_class_framed, forge_context, ontology_graph)
        new_current_class_framed.pop("bmo:canHaveTType", None)
        class_jsons.append(new_current_class_framed)
        class_ids.append(identifier)
        all_blank_node_triples.append(blank_node_triples)
    
    return class_ids, class_jsons, all_blank_node_triples, new_classes

def _get_leaf_regions(uri, children_hierarchy_property, ontology_graph):

    query = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX schema: <http://schema.org/>
            PREFIX bmo: <https://bbp.epfl.ch/ontologies/core/bmo/>
            
            SELECT DISTINCT ?leaf_region
            WHERE{{
            <{0}> {1}+ ?leaf_region .
            FILTER NOT EXISTS {{?leaf_region {1} ?a}}
            
            }}
            LIMIT 2000
            """.format(uri, children_hierarchy_property)
    leaf_regions = {str(l_br[0]) for l_br in list(ontology_graph.query(query))}

    return leaf_regions


def _frame_class(cls:Dict, context:Context, ontology_graph:rdflib.Graph):

    to_pop = []
    for k, v in cls.items():
        if v is not None and v != {}:
            k_expanded = context.expand(k)
            k_term = context.find_term(k_expanded, "@id")

            if k_term and k_term.type == "@id":
                res = [context.expand(s) if "uberon:" not in s else str(s).replace("uberon:", context.expand('uberon'))
                    for s in v] if isinstance(v, list) \
                    else ([context.expand(v) if "uberon:" not in v else str(v).replace("uberon:", context.expand(
                    'uberon'))] if isinstance(v, str) else [context.expand(v["@id"])])
                ns, fragment = rdflib.namespace.split_uri(k_expanded)

                if fragment in cls and fragment != k:
                    if isinstance(cls[fragment], list):
                        cls[fragment].extend(res)
                    elif isinstance(cls[fragment], Dict):
                        cls[fragment] = [cls[fragment]]
                        cls[fragment].extend(res)
                    elif isinstance(cls[fragment], str):
                        cls[fragment] = [cls[fragment]]
                        cls[fragment].extend(res)

                    to_pop.append(k)
                else:
                    cls[k] = res
        else:
            to_pop.append(k)
    for c in to_pop:
        cls.pop(c)
    cls.pop("bmo:canHaveTType", None)
    if "@id" in cls:
        cls["@id"] = context.expand(cls["@id"])
    if "subClassOf" in cls and cls["subClassOf"] and cls["subClassOf"] != {}:
        cls["subClassOf"] = list(context.expand(s) for s in cls["subClassOf"] if s != {}) if isinstance(
            cls["subClassOf"], list) \
            else ([context.expand(cls["subClassOf"])] if isinstance(cls["subClassOf"], str) else [
            context.expand(cls["subClassOf"]["@id"])])
        for sub_c in cls["subClassOf"]: # bring in cls["subClassOf"] some parent classes for quick look up
            
            if str(BMO.NeuronMorphologicalType) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, BMO.NeuronMorphologicalType) in ontology_graph:
                cls["subClassOf"].append(str(BMO.NeuronMorphologicalType))

            if str(BMO.NeuronElectricalType) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, BMO.NeuronElectricalType) in ontology_graph:
                cls["subClassOf"].append(str(BMO.NeuronElectricalType))

            if  str(NSG.MType) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, NSG.MType) in ontology_graph:
                cls["subClassOf"].append(str(NSG.MType))

            if str(NSG.EType) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, NSG.EType) in ontology_graph:
                cls["subClassOf"].append(str(NSG.EType))
            if str(NSG.BrainRegion) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, NSG.BrainRegion) in ontology_graph:
                cls["subClassOf"].append(str(NSG.BrainRegion))
                
            if str(NSG.BrainLayer) not in cls["subClassOf"] and (rdflib.term.URIRef(sub_c), RDFS.subClassOf*OneOrMore, NSG.BrainLayer) in ontology_graph:
                cls["subClassOf"].append(str(NSG.BrainLayer))

        if str(NSG.BrainRegion) in cls["subClassOf"]: # this is a brain region, then collect all of it's leaf brain regions (to move out of here). Find a rdflib.Path to replace sparql
            leaf_regions = _get_leaf_regions(cls["@id"], "schema:hasPart", ontology_graph)
            if len(leaf_regions) > 0: 
                cls["hasLeafRegionPart"] = list(leaf_regions)

            layer_leaf_regions = _get_leaf_regions(cls["@id"], "bmo:hasLayerPart", ontology_graph)
            if len(layer_leaf_regions) > 0: 
                cls["hasLayerLeafRegionPart"] = list(layer_leaf_regions)

    rels, _ = _collect_ancestors_restrictions(ontology_graph, rdflib.term.URIRef(cls["@id"]), restrictions_only=True)

    for p, o in rels:
        p_symbol = context.to_symbol(p)
        if p_symbol not in cls:
            cls[p_symbol] = []
        else:
            if isinstance(cls[p_symbol], Dict) or isinstance(cls[p_symbol], str):
                cls[p_symbol] = [cls[p_symbol]]
        cls[p_symbol].append(context.expand(str(o)))

    if "hasPart" in cls and cls["hasPart"] and cls["hasPart"] != {}:
        cls["hasPart"] = list(context.expand(s) for s in cls["hasPart"]) if isinstance(cls["hasPart"], list) \
            else ([context.expand(cls["hasPart"])] if isinstance(cls["hasPart"], str) else [
            context.expand(cls["hasPart"]["@id"])])
    if "isPartOf" in cls and cls["isPartOf"] and cls["isPartOf"] != {}:
        cls["isPartOf"] = list(context.expand(s) for s in cls["isPartOf"]) if isinstance(cls["isPartOf"], list) \
            else ([context.expand(cls["isPartOf"])] if isinstance(cls["isPartOf"], str) else [
            context.expand(cls["isPartOf"]["@id"])])

    if "contribution" in cls and cls["contribution"] and cls["contribution"] != {}:
        cls["contribution"] = list({context.expand(s) if isinstance(s, str) else context.expand(s["@id"]) for s in cls["contribution"]}) if isinstance(cls["contribution"], list) \
            else ([context.expand(cls["contribution"])] if isinstance(cls["contribution"], str) else [
            context.expand(cls["contribution"]["@id"])])
        contribution_with_agent = []
        for i, contrib_uri in enumerate(cls["contribution"]):
            contribution_agent = ontology_graph.objects(rdflib.term.URIRef(contrib_uri), PROV.agent)
            if contribution_agent:
                contribution_agent = list(contribution_agent)[0]
                contribution_agent_type = list(ontology_graph.objects(rdflib.term.URIRef(contribution_agent), RDF.type))
                contribution_agent_type  = [context.to_symbol(t) for t in contribution_agent_type]
                contribution_with_agent.insert(i, {"agent":{"@id":contribution_agent, "@type":contribution_agent_type}})
            else:
                contribution_with_agent.insert(i, contrib_uri)
        cls["contribution"] = contribution_with_agent


    if "schema:isPartOf" in cls and cls["schema:isPartOf"]:
        ip = cls.pop("schema:isPartOf", None)
        if ip:
            cls["isPartOf"] = ip if isinstance(ip, list) else [ip]
    if "rdfs:seeAlso" in cls and cls["rdfs:seeAlso"]:
        sa = cls.pop("rdfs:seeAlso", None)
        if sa:
            cls["seeAlso"] = sa if isinstance(sa, list) else [sa]
    if "schema:about" in cls and cls["schema:about"]:
        ab = cls.pop("schema:about", None)
        if ab:
            cls["about"] = ab if isinstance(ab, list) else [ab]

    if "bmo:usesCircuitWithProperty" in cls and cls["bmo:usesCircuitWithProperty"]:
        uc = cls.pop("bmo:usesCircuitWithProperty", None)
        if uc:
            cls["usesCircuitWithProperty"] = uc if isinstance(uc, list) else [uc]

    if "bmo:generatesCircuitWithProperty" in cls and cls["bmo:generatesCircuitWithProperty"]:
        gc = cls.pop("bmo:generatesCircuitWithProperty", None)
        if gc:
            cls["generatesCircuitWithProperty"] = gc if isinstance(gc, list) else [gc]

    if "bmo:canHaveTType" in cls and cls["bmo:canHaveTType"]:
        ct = cls.pop("bmo:canHaveTType", None)
        if ct:
            cls["canHaveTType"] = ct if isinstance(ct, list) else [ct]
    if "bmo:canHaveBrainRegion" in cls and cls["bmo:canHaveBrainRegion"]:
        ct = cls.pop("bmo:canHaveBrainRegion", None)
        if ct:
            cls["canHaveBrainRegion"] = ct if isinstance(ct, list) else [ct]
    if "bmo:hasParameter" in cls and cls["bmo:hasParameter"]:
        ct = cls.pop("bmo:hasParameter", None)
        if ct:
            cls["hasParameter"] = ct if isinstance(ct, list) else [ct]
    if "bmo:isAssociatedWith" in cls and cls["bmo:isAssociatedWith"]:
        ct = cls.pop("bmo:isAssociatedWith", None)
        if ct:
            cls["isAssociatedWith"] = ct if isinstance(ct, list) else [ct]
    if "bmo:expressionProfile" in cls and cls["bmo:expressionProfile"]:
        ct = cls.pop("bmo:expressionProfile", None)
        if ct:
            cls["expressionProfile"] = ct if isinstance(ct, list) else [ct]
    if "bmo:isBasedOn" in cls and cls["bmo:isBasedOn"]:
        ct = cls.pop("bmo:isBasedOn", None)
        if ct:
            cls["isBasedOn"] = ct if isinstance(ct, list) else [ct]
    if "bmo:molecule" in cls and cls["bmo:molecule"]:
        ct = cls.pop("bmo:molecule", None)
        if ct:
            cls["molecule"] = ct if isinstance(ct, list) else [ct]
    if "bmo:postsynapticNeuron" in cls and cls["bmo:postsynapticNeuron"]:
        ct = cls.pop("bmo:postsynapticNeuron", None)
        if ct:
            cls["postsynapticNeuron"] = ct if isinstance(ct, list) else [ct]
    if "bmo:presynapticNeuron" in cls and cls["bmo:presynapticNeuron"]:
        ct = cls.pop("bmo:presynapticNeuron", None)
        if ct:
            cls["presynapticNeuron"] = ct if isinstance(ct, list) else [ct]
    if "nsg:hasFeature" in cls and cls["nsg:hasFeature"]:
        ct = cls.pop("nsg:hasFeature", None)
        if ct:
            cls["hasFeature"] = ct if isinstance(ct, list) else [ct]
    if "bmo:hasWorkflowDefinition" in cls and cls["bmo:hasWorkflowDefinition"]:
        ct = cls.pop("bmo:hasWorkflowDefinition", None)
        if ct:
            cls["hasWorkflowDefinition"] = ct if isinstance(ct, list) else [ct]

    if "bmo:hasLayerLocationPhenotype" in cls and cls["bmo:hasLayerLocationPhenotype"]:
        ct = cls.pop("bmo:hasLayerLocationPhenotype", None)
        if ct:
            cls["hasLayerLocationPhenotype"] = ct if isinstance(ct, list) else [ct]

    if "nsg:hasLayerLocationPhenotype" in cls and cls["nsg:hasLayerLocationPhenotype"]:
        ct = cls.pop("nsg:hasLayerLocationPhenotype", None)
        if ct:
            cls["hasLayerLocationPhenotype"] = ct if isinstance(ct, list) else [ct]

    if "bmo:hasMorphologicalPhenotype" in cls and cls["bmo:hasMorphologicalPhenotype"]:
        ct = cls.pop("bmo:hasMorphologicalPhenotype", None)
        if ct:
            cls["hasMorphologicalPhenotype"] = ct if isinstance(ct, list) else [ct]

    if "nsg:hasMorphologicalPhenotype" in cls and cls["nsg:hasMorphologicalPhenotype"]:
        ct = cls.pop("nsg:hasMorphologicalPhenotype", None)
        if ct:
            cls["hasMorphologicalPhenotype"] = ct if isinstance(ct, list) else [ct]

    if "bmo:hasType" in cls and cls["bmo:hasType"]:
        ct = cls.pop("bmo:hasType", None)
        if ct:
            cls["hasType"] = ct if isinstance(ct, list) else [ct]
    if "bmo:hasMType" in cls and cls["bmo:hasMType"]:
        ct = cls.pop("bmo:hasMType", None)
        if ct:
            cls["hasMType"] = ct if isinstance(ct, list) else [ct]
    if "bmo:canHaveBrainRegion" in cls and cls["bmo:canHaveBrainRegion"]:
        ct = cls.pop("bmo:canHaveBrainRegion", None)
        if ct:
            cls["canHaveBrainRegion"] = ct if isinstance(ct, list) else [ct]
    if "bmo:canBeLocatedInBrainRegion" in cls and cls["bmo:canBeLocatedInBrainRegion"]:
        ct = cls.pop("bmo:canBeLocatedInBrainRegion", None)
        if ct:
            cls["canBeLocatedInBrainRegion"] = ct if isinstance(ct, list) else [ct]

    if "bmo:canHaveMType" in cls and cls["bmo:canHaveMType"]:
        ct = cls.pop("bmo:canHaveMType", None)
        if ct:
            cls["canHaveMType"] = ct if isinstance(ct, list) else [ct]
    if "bmo:exposesParameter" in cls and cls["bmo:exposesParameter"]:
        ct = cls.pop("bmo:exposesParameter", None)
        if ct:
            cls["exposesParameter"] = ct if isinstance(ct, list) else [ct]
    if "bmo:sourceType" in cls and cls["bmo:sourceType"]:
        ct = cls.pop("bmo:sourceType", None)
        if ct:
            cls["sourceType"] = ct if isinstance(ct, list) else [ct]

    if "nsg:hasInstanceInSpecies" in cls and cls["nsg:hasInstanceInSpecies"]:
        ct = cls.pop("nsg:hasInstanceInSpecies", None)
        if ct:
            cls["hasInstanceInSpecies"] = ct if isinstance(ct, list) else [ct]
    
    if "hasHierarchyView" in cls:
        ct = cls.pop("hasHierarchyView", None)
        if ct:
            cls["hasHierarchyView"] = ct if isinstance(ct, list) else [ct]

    if "bmo:targetType" in cls and cls["bmo:targetType"]:
        ct = cls.pop("bmo:targetType", None)
        if ct:
            cls["targetType"] = ct if isinstance(ct, list) else [ct]
    if "bmo:constraints" in cls and cls["bmo:constraints"]:
        ct = cls.pop("bmo:constraints", None)
        if ct:
            cls["constraints"] = ct if isinstance(ct, list) else [ct]
    if "owl:equivalentClass" in cls and cls["owl:equivalentClass"]:
        ct = cls.pop("owl:equivalentClass", None)
        if ct:
            cls["equivalentClass"] = ct if isinstance(ct, list) else [ct]

    if "skos:prefLabel" in cls and cls["skos:prefLabel"]:
        cls["prefLabel"] = cls.pop("skos:prefLabel", None)
    if "rdfs:label" in cls and cls["rdfs:label"]:
        cls["label"] = cls.pop("rdfs:label", None)

    if "skos:definition" in cls and cls["skos:definition"]:
        cls["definition"] = cls.pop("skos:definition", None)
    if "skos:notation" in cls and cls["skos:notation"]:
        cls["notation"] = cls.pop("skos:notation", None)
    if "skos:definition" in cls and cls["skos:definition"]:
        cls["definition"] = cls.pop("skos:definition", None)
    if "skos:altLabel" in cls and cls["skos:altLabel"]:
        cls["altLabel"] = cls.pop("skos:altLabel", None)

    if "isDefinedBy" in cls and cls["isDefinedBy"] and isinstance(cls["isDefinedBy"], list):
        cls["isDefinedBy"] = cls["isDefinedBy"][0]

    if "canBeLocatedInBrainRegion" in cls:
        propagated_brain_regions=[]
        if cls["@id"] in GENERIC_CELL_TYPES:
            propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(ontology_graph, ROOT_BRAIN_REGION, GENERIC_CELL_TYPES[cls["@id"]])
        elif "subClassOf" in cls and str(BMO.NeuronMorphologicalType) in cls["subClassOf"]:
            for sr in cls["canBeLocatedInBrainRegion"]:
                propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(ontology_graph, sr, BMO.NeuronMorphologicalType)
        elif "subClassOf" in cls and str(BMO.NeuronElectricalType) in cls["subClassOf"]:
            for sr in cls["canBeLocatedInBrainRegion"]:
                propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(ontology_graph,  sr, BMO.NeuronElectricalType)
        if len(propagated_brain_regions) > 0:
            cls["canBeLocatedInBrainRegion"] = [cls["canBeLocatedInBrainRegion"]] if isinstance(cls["canBeLocatedInBrainRegion"], str) else cls["canBeLocatedInBrainRegion"]
            cls["canBeLocatedInBrainRegion"].extend(propagated_brain_regions)        

    if "atlas_id" in cls and cls["atlas_id"] == "None":
        cls["atlas_id"]=None

    return cls

def _create_property_based_hierarchy(ontology_graph, cls_uriref, layer_urirefs, classes_relevant_for_layer, isPartOf_property_uriref):
    new_classes = []
    grand_parents = list(ontology_graph.objects(cls_uriref, isPartOf_property_uriref/SCHEMAORG.isPartOf))
    relevant_grand_parents = set()
    for c in classes_relevant_for_layer:
        s= {grand_parent for grand_parent in grand_parents if (grand_parent, SCHEMAORG.isPartOf*ZeroOrMore, c) in ontology_graph}
        relevant_grand_parents.update(s)
    
    next_cls_urirefs = []
    for grand_parent in relevant_grand_parents:
        grandParent_uncle_without_layer = []
        uncle_with_layer = []
        grand_parent_layers = list(ontology_graph.objects(grand_parent, NSG.hasLayerLocationPhenotype))
        uncles = list(ontology_graph.objects(grand_parent, SCHEMAORG.hasPart))
        uncle_layers = {}
        for uncle in uncles:
            uncle_layers[uncle] = list(ontology_graph.objects(uncle, NSG.hasLayerLocationPhenotype))
        for layer in layer_urirefs:
            grandParent_uncle_without_layer.extend([(grand_parent, NSG.hasLayerLocationPhenotype, layer) not in ontology_graph,
                                                    (grand_parent, SCHEMAORG.hasPart/NSG.hasLayerLocationPhenotype, layer) not in ontology_graph])
            
            uncle_with_layer.extend([(grand_parent, SCHEMAORG.hasPart/NSG.hasLayerLocationPhenotype, layer) in ontology_graph])
        
        if (all(uncle_with_layer)): # current class should be part of the uncle with same layers if the uncle is not a leaf node with data. No need to create a new one
            next_cls_urirefs = []
            for uncle in uncles:                
                if set(layer_urirefs) == set(uncle_layers):
                    ontology_graph.add((uncle, BMO.hasLayerPart, cls_uriref))
                    ontology_graph.add((cls_uriref, BMO.isLayerPartOf, uncle))
                    ontology_graph.add((uncle, BMO.hasHierarchyView, BMO.BrainLayer))
                    new_isPartOf_property_uriref = SCHEMAORG.isPartOf
                    next_cls_urirefs.append(uncle)
        elif set(grand_parent_layers) == set(layer_urirefs):#(grand_parent, NSG.hasLayerLocationPhenotype, rdflib.term.URIRef(layer)) in ontology_graph:
            ontology_graph.add((grand_parent, BMO.hasLayerPart, cls_uriref))
            ontology_graph.add((cls_uriref, BMO.isLayerPartOf, grand_parent))
            ontology_graph.add((grand_parent, BMO.hasHierarchyView, BMO.BrainLayer))
            next_cls_urirefs = [grand_parent]
            new_isPartOf_property_uriref = BMO.isLayerPartOf

        else:#if all(grandParent_uncle_without_layer) or set(layer_urirefs).issubset(set(grand_parent_layers)): # if the grand parent class does not have a layer and uncle does not have the layer
            # then create a corresponding layer location class with 
            # label == the grand parent label, layer altLabel, 
            # is part of (isLayerPartOf) of the grand parent which (contains it - hasLayerPart),
            # add the newly created class is parent of current class which contains it 

            grand_parent_label = ontology_graph.value(subject=grand_parent, predicate=RDFS.label)
            grand_parent_notation = ontology_graph.value(subject=grand_parent, predicate=SKOS.notation)
            layer_altLabels = [grand_parent_label]
            layer_notations = [grand_parent_notation]
            for layer in layer_urirefs: 
                layer_altLabel = ontology_graph.value(subject=layer, predicate=SKOS.altLabel)
                layer_notation = ontology_graph.value(subject=layer, predicate=SKOS.notation)
                layer_altLabels.append(layer_altLabel)
                layer_notations.append(layer_notation)

            new_class_label    = ", ".join(layer_altLabels)
            new_class_notation = "_".join(layer_notations)

            new_class_uri = "/".join([BRAIN_REGION_ONTOLOGY_URI, new_class_notation])
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), RDF.type, OWL.Class))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), RDFS.subClassOf, NSG.BrainRegion))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), RDFS.label, Literal(new_class_label, lang= "en")))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), SKOS.prefLabel, Literal(new_class_label, lang= "en")))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), SKOS.notation, Literal(new_class_notation)))
            
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), BMO.isLayerPartOf, grand_parent))
            ontology_graph.add((grand_parent, BMO.hasLayerPart, rdflib.term.URIRef(new_class_uri)))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), BMO.hasLayerPart, cls_uriref))
            ontology_graph.add((cls_uriref, BMO.isLayerPartOf, rdflib.term.URIRef(new_class_uri)))
            ontology_graph.add((grand_parent, BMO.hasHierarchyView, BMO.BrainLayer))
            ontology_graph.add((rdflib.term.URIRef(new_class_uri), BMO.hasHierarchyView, BMO.BrainLayer))
            for layer in layer_urirefs: 
                ontology_graph.add((rdflib.term.URIRef(new_class_uri), NSG.hasLayerLocationPhenotype, layer))
            new_classes.append(new_class_uri)
            next_cls_urirefs = [rdflib.term.URIRef(new_class_uri)]
            new_isPartOf_property_uriref = BMO.isLayerPartOf
        for next_cls_uriref in next_cls_urirefs:       
            new_classes.extend(_create_property_based_hierarchy(ontology_graph, next_cls_uriref, layer_urirefs, classes_relevant_for_layer, new_isPartOf_property_uriref))   
    return new_classes


def _get_sub_regions_to_propagate_metype_to(ontology_graph, from_brain_region, cell_type):
    propagated_brain_regions = []
    sub_brain_regions = ontology_graph.objects(rdflib.term.URIRef(from_brain_region), SCHEMAORG.hasPart)
    for sub_brain_region in sub_brain_regions:
        if not ((sub_brain_region, ~OWL.someValuesFrom/~RDFS.subClassOf/RDFS.subClassOf/OWL.someValuesFrom, BMO.BBP_contribution) in ontology_graph and \
                (sub_brain_region, ~OWL.someValuesFrom/~RDFS.subClassOf/RDFS.subClassOf*ZeroOrMore, cell_type) in ontology_graph): # missing the canBeLocatedInBrainRegion
            propagated_brain_regions.append(str(sub_brain_region))
            propagated_brain_regions.extend(_get_sub_regions_to_propagate_metype_to( ontology_graph, str(sub_brain_region), cell_type))
    return propagated_brain_regions


def register_classes(forge, class_resources_jsons, tag=None):
    """Register ontology classes to the store."""
    errors = []
    for class_json in class_resources_jsons:
        class_json["@context"] = "https://neuroshapes.org"
        try:
            resource = forge.from_json(class_json)
            forge.register(resource, schema_id="datashapes:ontologyentity")
            if resource._last_action and resource._last_action.succeeded is True and tag is not None:
                forge.tag(resource, tag)

            """
            if resource._last_action and resource._last_action.error == "RegistrationError":
                resource_updated = _process_already_existing_resource(forge, resource)
                forge.update(resource_updated)
                if tag is not None:
                    forge.tag(resource_updated, tag)
            """
            if resource._last_action and not resource._last_action.succeeded and \
                    ALREADY_EXISTS_ERROR in resource._last_action.message:
                resource_updated = _process_already_existing_resource(forge, resource)
                forge._debug = True
                forge.update(resource_updated)
                if tag is not None:
                    forge.tag(resource_updated, tag)
                if not resource_updated._last_action.succeeded:
                    raise Exception(
                        f"Failed to register or update class:{json.dumps(class_json)}: {resource_updated._last_action.message}")

            if resource._last_action and not resource._last_action.succeeded and \
                    ALREADY_EXISTS_ERROR not in resource._last_action.message:
                print(f"Failed to register or update class:{resource.id}: {resource._last_action.message}")
                raise Exception(f"Failed to register or update class:{json.dumps(class_json)}: {resource._last_action.message}")
        except Exception as e:
            errors.append(e)
            pass
    return errors

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


def build_context_from_ontology(ontology_graph, forge_context, vocab=None, binding=None):
    """
    Build a jsonld context object.
    """
    # Check whether a term is already defined in the context
    # excludes brain region (https://neuroshapes.org/BrainRegion) values
    new_forge_context = _initialise_new_context(forge_context, vocab, binding)
    errors = []
    for cls in ontology_graph.subjects(RDF.type, OWL.Class):
        try:
            brain_region_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://neuroshapes.org/BrainRegion"))))
            species_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://neuroshapes.org/Species"))))
            taxonomic_rank_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*ZeroOrMore, rdflib.term.URIRef("http://purl.obolibrary.org/obo/NCBITaxon#_taxonomic_rank"))))
            pato_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*ZeroOrMore, rdflib.term.URIRef("http://purl.obolibrary.org/obo/PATO_0000001"))))
            bmo_mapping_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/Mapping"))))
            braincell_types_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/BrainCellTranscriptomeType"))))
            etypes_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/NeuronElectricalType"))))
            mtypes_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/NeuronMorphologicalType"))))
            nt_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/NeurotransmitterType"))))
            nnt_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/NewNeuronType"))))
            glia_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/GliaType"))))
            ion_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/Ion"))))
            ioncurrent_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/IonCurrent"))))
            potassium_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://neuroshapes.org/PotassiumChannel"))))
            brain_area_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/BrainArea"))))
            brainlayer_triples = list(ontology_graph.triples((cls, RDFS.subClassOf*OneOrMore, rdflib.term.URIRef("https://bbp.epfl.ch/ontologies/core/bmo/BrainLayer"))))

            name, idref = _build_context_item(cls, new_forge_context)

            if name is not None and idref is not None and not str(idref).startswith("http://purl.obolibrary.org/obo/UBERON_")\
                    and len(brain_region_triples) == 0 and len(species_triples) == 0 \
                            and len(taxonomic_rank_triples) == 0 and len(pato_triples) == 0 \
                            and len(bmo_mapping_triples) == 0 and len(braincell_types_triples) == 0 \
                            and len(mtypes_triples) == 0 and len(nt_triples) == 0 \
                            and len(ion_triples) == 0 and len(ioncurrent_triples) == 0 \
                            and len(potassium_triples) == 0 and len(brain_area_triples) == 0 \
                            and len(brainlayer_triples) == 0 and len(etypes_triples) == 0\
                    and len(nnt_triples) == 0 and len(glia_triples) == 0:
                new_forge_context.add_term(name, idref)
                new_forge_context.document["@context"][name] = {"@id": idref}

        except Exception as e:
            defining_ontology = ontology_graph.objects(cls, RDFS.isDefinedBy)
            errors.append(f"Failed to build context from {cls} defined in the ontology {str(list(defining_ontology))}: {e}")

    for obj_prop in ontology_graph.subjects(RDF.type, OWL.ObjectProperty):
        try:
            name, idref = _build_context_item(obj_prop, new_forge_context)
            if name is not None and idref is not None and _is_property_to_include_in_context(idref):
                new_forge_context.add_term(name, idref, "@id")
                new_forge_context.document["@context"][name] = {"@id": idref, "@type":"@id"}

        except Exception as e:
            defining_ontology = ontology_graph.objects(obj_prop, RDFS.isDefinedBy)
            errors.append(f"Failed to build context from {obj_prop} defined in the ontology {str(list(defining_ontology))}: {e}")

    for annot_prop in ontology_graph.subjects(RDF.type, OWL.AnnotationProperty):
        try:
            name, idref = _build_context_item(annot_prop, new_forge_context)
            if name is not None and idref is not None and _is_property_to_include_in_context(idref):
                new_forge_context.add_term(name, idref)
                new_forge_context.document["@context"][name] = {"@id": idref}
        except Exception as e:
            defining_ontology = ontology_graph.objects(annot_prop, RDFS.isDefinedBy)
            errors.append(
                f"Failed to build context from {annot_prop} defined in the ontology {str(list(defining_ontology))}: {e}")
    return new_forge_context, errors


def _is_property_to_include_in_context(uri_ref):
    ns, fragment = _split_uri(str(uri_ref))
    return  str(ns) not in ["http://www.geneontology.org/formats/oboInOwl#", "http://purl.obolibrary.org/obo/pato#","http://purl.obolibrary.org/obo/ro/subsets#", "http://purl.obolibrary.org/obo/go#"] \
                and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/IAO_") \
                and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/RO_") \
                and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/BFO_")


def build_context_from_schema(schema_graph, forge_context, vocab=None, binding=None):
    new_forge_context = _initialise_new_context(forge_context, vocab, binding)
    errors = []

    for shape in schema_graph.subjects(RDF.type, SHACL.NodeShape):
        defining_schema = schema_graph.subjects(NXV.shapes, shape)
        for targetClass in schema_graph.objects(shape, SHACL.targetClass):
            try:
                name, idref = _build_context_item(targetClass, new_forge_context)
                if name is not None and idref is not None:
                    new_forge_context.add_term(name, idref)
                    new_forge_context.document["@context"][name] = {"@id": idref}
            except Exception as e:
                errors.append(
                    f"Failed to build context from {targetClass} targeted by the shape {shape} in the schema {str(list(defining_schema))}: {e}")

        for targetObjects in schema_graph.objects(shape, SHACL.targetObjectsOf):
            try:
                name, idref = _build_context_item(targetObjects, new_forge_context)
                if name is not None and idref is not None:
                    new_forge_context.add_term(name, idref)
                    new_forge_context.document["@context"][name] = {"@id": idref}
            except Exception as e:
                errors.append(
                    f"Failed to build context from {targetObjects} targeted by the shape {shape} in the schema {str(list(defining_schema))}: {e}")

        for targetSubjects in schema_graph.objects(shape, SHACL.targetSubjectsOf):
            try:
                name, idref = _build_context_item(targetSubjects, new_forge_context)
                if name is not None and idref is not None:
                    new_forge_context.add_term(name, idref)
                    new_forge_context.document["@context"][name] = {"@id": idref}
            except Exception as e:
                errors.append(
                    f"Failed to build context from {targetSubjects} targeted by the shape {shape} in the schema {str(list(defining_schema))}: {e}")

    return new_forge_context, errors


def _initialise_new_context(forge_context, vocab, binding):
    new_forge_context = Context(forge_context.document, forge_context.iri)
    if vocab:
        new_forge_context.vocab = vocab
    if binding:
        for b in binding:
            new_forge_context.add_term(name=b[0], idref=b[1], prefix=True)
    return new_forge_context


def _build_context_item(uri_ref, forge_context):

    try:
        ns, fragment = _split_uri(str(uri_ref))
    except ValueError as ve:
        raise ValueError(f"Error splitting URI {uri_ref}: {ve}")

    name, idref = None, None
    found_uri_ref = forge_context.find_term(str(uri_ref))
    if found_uri_ref:  # uri_ref in context
        if found_uri_ref.name == fragment:  # uri_ref in context, with same fragment
            pass  # nothing to do
        else:  # uri_ref in context, with different fragments
            raise ValueError(f"The URI {str(uri_ref)} is present in the context under a name {found_uri_ref.name} different of its fragment {fragment}")
    else:  # uri_ref not in context
        if fragment in forge_context.terms:  # uri_ref not in context, fragment in
            if str(uri_ref) != forge_context.terms[fragment].id:  # uri_ref not in context, fragment in but under different ns
                raise ValueError(f"The fragment {fragment} of the term {str(uri_ref)} is present in the context under a different namespace {forge_context.terms[fragment].id}")
        else:  # uri_ref not in context, fragment not in
            name, idref = fragment, str(uri_ref) # a new context term can be created
    return name, idref

def _split_uri(uri):
    try:
        ns, fragment = rdflib.namespace.split_uri(uri)
        return ns, fragment
    except ValueError as ve:
        raise ValueError(f"Error splitting URI {uri}: {ve}") 

def replace_is_defined_by_uris(graph, uri_mapping, ontology_uri=None):
    """
        Replace targets of `isDefinedBy` rel with Nexus URIs.
        Replace WebProtégé generated ontology URIs with mapped ones.
    """

    triples_to_add = set()
    triples_to_remove = set()
    for s, p, o in graph.triples((None, None, None)):
        new_s = uri_mapping.get(str(s), str(s))
        new_p = uri_mapping.get(str(p), str(p))
        new_o = uri_mapping.get(str(o), str(o))
        if new_s != str(s) or new_p != str(p) or new_o != str(o):
            if not isinstance(o, rdflib.term.Literal):
                new_o = rdflib.URIRef(new_o)
            else:
                new_o = rdflib.Literal(new_o, o.language, o.datatype)
            triples_to_add.add((rdflib.URIRef(new_s), rdflib.URIRef(new_p), new_o))
            triples_to_remove.add((s, p, o))


    for el in triples_to_remove:
        graph.remove(el)
    for el in triples_to_add:
        graph.add(el)
    if ontology_uri:
        new_ontology_uri = uri_mapping.get(ontology_uri, ontology_uri)
        return rdflib.term.URIRef(new_ontology_uri)
    return None

