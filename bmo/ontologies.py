"""Utils for processing ontologies."""
import json
from typing import Dict, Tuple, Any, List, Set

from pyld import jsonld
from kgforge.core.commons.context import Context
from collections import OrderedDict

from pyshacl.rdfutil import clone_graph
from rdflib import OWL, RDF, RDFS, SKOS, XSD, PROV, Literal, term, Graph, URIRef, namespace
from rdflib.paths import OneOrMore, ZeroOrMore

from bmo.slim_ontologies import get_slim_ontology_id
from bmo.utils import (
    BMO,
    BRAIN_REGION_ONTOLOGY_URI,
    NSG,
    SCHEMAORG,
    SHACL,
    NXV
)

# TOO_LARGE_ERROR = "the request payload exceed the maximum configured limit"

GENERIC_CELL_TYPES = {
    "https://bbp.epfl.ch/ontologies/core/bmo/GenericInhibitoryNeuronMType": BMO.NeuronMorphologicalType,
    "https://bbp.epfl.ch/ontologies/core/bmo/GenericExcitatoryNeuronMType": BMO.NeuronMorphologicalType,
    "https://bbp.epfl.ch/ontologies/core/bmo/GenericInhibitoryNeuronEType": BMO.NeuronElectricalType,
    "https://bbp.epfl.ch/ontologies/core/bmo/GenericExcitatoryNeuronEType": BMO.NeuronElectricalType
}

ROOT_BRAIN_REGION = "http://api.brain-map.org/api/v2/data/Structure/997"


# BASE_CELL_TYPE_CLASSES = {str(BMO.NeuronMorphologicalType): BMO.NeuronMorphologicalType,
#                           str(BMO.NeuronElectricalType): BMO.NeuronElectricalType}


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

    return jsonld_doc


def _create_hierarchy_view(
        uri_having_view: str, view_uri: str, view_label: str, view_description: str,
        parent_hierarchy_property: str, children_hierarchy_property: str,
        leaf_hierarchy_property: str
) -> Tuple[List[Tuple], Dict[str, Dict]]:
    triples = [
        (term.URIRef(uri_having_view), BMO.hasHierarchyView, term.URIRef(view_uri)),
        (term.URIRef(view_uri), RDFS.label, Literal(view_label)),
        (term.URIRef(view_uri), SCHEMAORG.description, Literal(view_description)),
        (term.URIRef(view_uri), BMO.hasParentHierarchyProperty, Literal(parent_hierarchy_property)),
        (term.URIRef(view_uri), BMO.hasChildrenHierarchyProperty, Literal(
            children_hierarchy_property)),
        (term.URIRef(view_uri), BMO.hasLeafHierarchyProperty, Literal(leaf_hierarchy_property))

    ]

    json_object = {
        "hasHierarchyView": {
            "@id": view_uri,
            "label": view_label,
            "description": view_description,
            "hasParentHierarchyProperty": parent_hierarchy_property,
            "hasChildrenHierarchyProperty": children_hierarchy_property,
            "hasLeafHierarchyProperty": leaf_hierarchy_property
        }
    }

    return triples, json_object


def frame_ontology(
        ontology_graph, context, context_json, class_resources_framed,
        include_defined_classes=True
):
    """Frame ontology into a JSON-LD payload."""

    frame_json = {
        "@context": context_json,
        "@type": str(OWL.Ontology),
        "defines": [{
            "@type": ["owl:Class", "owl:ObjectProperty"],
            "subClassOf": [
                {
                    "@embed": False
                }
            ],
            "equivalentClass": [
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
        layer_view_triples, layer_view_json = _create_hierarchy_view(
            BRAIN_REGION_ONTOLOGY_URI,
            str(BMO.BrainLayer),
            "Layer",
            "Layer based hierarchy",
            "isLayerPartOf",
            "hasLayerPart",
            "hasLayerLeafRegionPart"
        )

        brain_region_view_triples, brain_region_view_json = _create_hierarchy_view(
            BRAIN_REGION_ONTOLOGY_URI, str(NSG.BrainRegion), "BrainRegion",
            "Atlas default brain region hierarchy",
            "isPartOf", "hasPart", "hasLeafRegionPart"
        )
        view_triples = layer_view_triples + brain_region_view_triples

        for t in view_triples:
            ontology_graph.add(t)

    new_ontology_graph = ontology_graph
    # handle OWL.NamedIndividual with blank node type
    for indiv in ontology_graph.subjects(RDF.type, OWL.NamedIndividual):
        _types = ontology_graph.objects(indiv, RDF.type)
        bns = [bn for bn in _types if isinstance(bn, term.BNode)]

        if bns:
            new_ontology_graph = clone_graph(ontology_graph)
            for b in bns:
                new_ontology_graph.remove((indiv, RDF.type, b))

    onto_string = new_ontology_graph.serialize(format="json-ld", auto_compact=True, indent=2)
    onto_json = json.loads(onto_string)

    framed = jsonld.frame(
        onto_json, frame_json,
        options={"expandContext": context_json, "pruneBlankNodeIdentifiers": True}
    )

    framed_onto_json = graph_free_jsonld(framed)

    if "@id" in framed_onto_json:
        framed_onto_json["@id"] = context.expand(framed_onto_json["@id"])
    if "skos:prefLabel" in framed_onto_json and framed_onto_json["skos:prefLabel"]:
        framed_onto_json["prefLabel"] = framed_onto_json.pop("skos:prefLabel", None)
    if "rdfs:label" in framed_onto_json and framed_onto_json["rdfs:label"]:
        framed_onto_json["label"] = framed_onto_json.pop("rdfs:label", None)
    if include_defined_classes:
        framed_onto_json["defines"] = class_resources_framed
    elif "defines" in frame_json:
        framed_onto_json.pop("defines")
    framed_onto_json["@context"] = context.iri

    if str(ontology_uri) == BRAIN_REGION_ONTOLOGY_URI:
        framed_onto_json["hasHierarchyView"] = [
            layer_view_json["hasHierarchyView"],
            brain_region_view_json["hasHierarchyView"]
        ]

    return framed_onto_json


def find_ontology_resource(graph):
    """Find the ontology resource by type. The first one is returned"""
    for s in graph.subjects(RDF.type, OWL.Ontology):
        return s

    raise ValueError("No Ontology resource was found")


def add_defines_relation(graph, ontology):
    """Add defines relationship from the ontology to every class."""
    # ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = URIRef("https://neuroshapes.org/defines")
    graph.add((defines_rel, RDF.type, OWL.ObjectProperty))
    graph.add((defines_rel, RDFS.label, Literal("defines", lang="en")))

    # Add 'defines' rels to all the classes
    for c in graph.subjects(RDF.type, OWL.Class):
        graph.add((ontology, defines_rel, c))


def remove_defines_relation(graph):
    """Add defines relationship from the ontology to every class."""
    # ontology = find_ontology_resource(graph)

    # Create 'defines' rel
    defines_rel = URIRef("https://neuroshapes.org/defines")

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
        for t in ontology_graph.objects(ontology, URIRef("http://purl.org/dc/elements/1.1/title")):
            label = t.value
            break
    if not label:
        raise ValueError(
            "Ontology label is not provided and ontology does not "
            " have a title, please specify a label"
        )

    ontology_graph.add((ontology, RDFS.label, Literal(label, datatype=XSD.string)))


def _collect_ancestors_restrictions(
        ontology_graph: Graph, _class,
        restrictions_property=RDFS.subClassOf,
        restrictions_only=False
):
    rels = []
    all_blank_node_triples = []
    for p, o in ontology_graph.predicate_objects(_class):
        if p == restrictions_property and isinstance(o, term.BNode):
            rel, target, blank_node_triples = _process_blank_nodes(ontology_graph, o)
            rels.append((rel, target))
            all_blank_node_triples.extend(blank_node_triples)
        elif not restrictions_only:
            if isinstance(o, term.BNode):
                _, _, blank_node_triples = _process_blank_nodes(ontology_graph, o,
                                                                process_restriction=False)
                all_blank_node_triples.extend(blank_node_triples)
            rels.append((p, o))
    return rels, all_blank_node_triples


def _frame_brain_regions(ontology_graph, cls_int):
    # add views

    new_layered_classes_all = []

    all_br = [
        current_class for current_class, _ in cls_int
        if (current_class, RDFS.subClassOf, NSG.BrainRegion) in ontology_graph
    ]

    for current_class in all_br:
        ontology_graph.add((current_class, BMO.hasHierarchyView, NSG.BrainRegion))
        if (current_class, NSG.hasLayerLocationPhenotype, None) in ontology_graph:
            current_class_layers = list(
                ontology_graph.objects(current_class, NSG.hasLayerLocationPhenotype)
            )
            classes_relevant_for_layer = set()
            for layer in current_class_layers:
                classes_relevant_for_layer = set(
                    ontology_graph.objects(
                        term.URIRef(layer), RDFS.subClassOf * OneOrMore / SCHEMAORG.about
                    )
                )  # every group of layers
                # (e.g. the Neorcotex layer class or the hippocampus layer)
                # should link to its brain region scope
                # (i.e the highest brain regions it applies to) through SCHEMAORG.about
            new_layered_classes = _create_property_based_hierarchy(
                ontology_graph,
                current_class,
                current_class_layers,
                classes_relevant_for_layer,
                SCHEMAORG.isPartOf
            )
            for new_c in new_layered_classes:
                ontology_graph.add(
                    (term.URIRef(new_c), BMO.representedInAnnotation,
                     Literal(False, datatype=XSD.boolean))
                )
            new_layered_classes_all.extend(new_layered_classes)

    return new_layered_classes_all


def _is_deprecated(class_: URIRef, graph_to_check: Graph) -> bool:
    return (class_, OWL.deprecated, Literal(True, datatype=XSD.boolean)) in graph_to_check


def frame_classes(
        ontology_graph: Graph,
        forge_context,
        context,
        atlas_release_id: str,
        atlas_release_version: int
) -> Tuple[List[str], List[dict], Any, List[str]]:
    """Frame ontology classes into JSON-LD payloads."""
    class_jsons = []
    class_ids = []
    all_blank_node_triples = []
    new_classes = []

    frame_json_class = {
        "@context": context,
        "@type": [str(OWL.Class), str(OWL.NamedIndividual)],
        "@embed": True
    }

    # Consider removing the restrictions
    cls = ontology_graph.subjects(RDF.type, OWL.Class)
    cls_int = [(c, RDFS.subClassOf) for c in cls]

    new_layered_classes = _frame_brain_regions(ontology_graph, cls_int)
    new_classes.extend(new_layered_classes)

    cls_int.extend({(term.URIRef(c), RDFS.subClassOf) for c in new_classes})

    inst = ontology_graph.subjects(RDF.type, OWL.NamedIndividual)
    cls_int.extend([(i, RDF.type) for i in inst])

    for current_class, restrictions_property in cls_int:
        current_class_graph = Graph()
        # consider collecting transitive ancestors' restrictions only for argument provided classes
        rels, blank_node_triples = _collect_ancestors_restrictions(
            ontology_graph, current_class, restrictions_property=restrictions_property
        )

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
        current_class_framed["@id"] = identifier
        del current_class_framed["@context"]
        new_current_class_framed = _frame_class(
            current_class_framed, forge_context, ontology_graph,
            atlas_release_id, atlas_release_version
        )

        new_current_class_framed.pop("bmo:canHaveTType", None)
        class_jsons.append(new_current_class_framed)
        class_ids.append(identifier)
        all_blank_node_triples.append(blank_node_triples)

    return class_ids, class_jsons, all_blank_node_triples, new_classes


def _to_list(e):
    return e if isinstance(e, list) else [e]


def _id_if_dict(e):
    return e["@id"] if isinstance(e, dict) else e


def _get_leaf_regions(uri, children_hierarchy_property, ontology_graph) -> Set[str]:
    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX schema: <http://schema.org/>
        PREFIX bmo: <https://bbp.epfl.ch/ontologies/core/bmo/>

        SELECT DISTINCT ?leaf_region
        WHERE {{
            <{uri}> {children_hierarchy_property}+ ?leaf_region .
            FILTER NOT EXISTS {{?leaf_region {children_hierarchy_property} ?a}}
        }}
        LIMIT 2000
        """

    leaf_regions = {str(l_br[0]) for l_br in list(ontology_graph.query(query))}

    return leaf_regions


def _frame_class(cls: Dict, context: Context, ontology_graph: Graph, atlas_release_id: str,
                 atlas_release_version: int):
    to_pop = []
    for k, v in cls.items():
        if v is not None and v != {}:
            k_expanded = context.expand(k)
            k_term = context.find_term(k_expanded, "@id")

            if k_term and k_term.type == "@id":
                res = [
                    context.expand(s)
                    if "uberon:" not in s else str(s).replace("uberon:", context.expand('uberon'))
                    for s in _to_list(v)
                ] if not isinstance(v, dict) else [context.expand(v["@id"])]

                ns, fragment = namespace.split_uri(k_expanded)

                if fragment in cls and fragment != k:
                    cls[fragment].extend(_to_list(cls[fragment]))
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

        cls["subClassOf"] = list(
            context.expand(_id_if_dict(s)) for s in _to_list(cls["subClassOf"]) if s != {}
        )

        for sub_c in cls["subClassOf"]:
            # bring in cls["subClassOf"] some parent classes for quick look up

            parents_to_add_to_subclass = [
                BMO.NeuronMorphologicalType,
                BMO.NeuronElectricalType,
                NSG.MType,
                NSG.EType,
                NSG.BrainRegion,
                NSG.BrainLayer,
                BMO.BrainCellType
            ]

            for parent_to_check in parents_to_add_to_subclass:
                if str(parent_to_check) not in cls["subClassOf"] and \
                        (term.URIRef(sub_c), RDFS.subClassOf * OneOrMore, parent_to_check) \
                        in ontology_graph:
                    cls["subClassOf"].append(str(parent_to_check))

        if str(NSG.BrainRegion) in cls["subClassOf"]:
            # this is a brain region, then collect all of it's leaf brain regions
            # (to move out of here). Find a rdflib.Path to replace sparql

            leaf_regions = _get_leaf_regions(cls["@id"], "schema:hasPart", ontology_graph)

            if len(leaf_regions) > 0:
                cls["hasLeafRegionPart"] = list(leaf_regions)

            layer_leaf_regions = _get_leaf_regions(cls["@id"], "bmo:hasLayerPart", ontology_graph)
            if len(layer_leaf_regions) > 0:
                cls["hasLayerLeafRegionPart"] = list(layer_leaf_regions)

    rels, _ = _collect_ancestors_restrictions(
        ontology_graph, term.URIRef(cls["@id"]), restrictions_only=True
    )

    for p, o in rels:
        p_symbol = context.to_symbol(p)
        if p_symbol not in cls:
            cls[p_symbol] = []
        else:
            cls[p_symbol] = _to_list(cls[p_symbol])
        cls[p_symbol].append(context.expand(str(o)))

    if "hasPart" in cls and cls["hasPart"] and cls["hasPart"] != {}:
        cls["hasPart"] = [context.expand(_id_if_dict(s)) for s in _to_list(cls["hasPart"])]

    if "isPartOf" in cls and cls["isPartOf"] and cls["isPartOf"] != {}:
        cls["isPartOf"] = [context.expand(_id_if_dict(s)) for s in _to_list(cls["isPartOf"])]

    if "contribution" in cls and cls["contribution"] and cls["contribution"] != {}:
        cls["contribution"] = list(
            {context.expand(_id_if_dict(s)) for s in _to_list(cls["contribution"])}
        )

        contribution_with_agent = []
        for i, contrib_uri in enumerate(cls["contribution"]):
            contribution_agent = ontology_graph.objects(term.URIRef(contrib_uri), PROV.agent)
            if contribution_agent:
                contribution_agent = list(contribution_agent)[0]
                contribution_agent_type = list(
                    ontology_graph.objects(term.URIRef(contribution_agent), RDF.type))
                contribution_agent_type = [context.to_symbol(t) for t in contribution_agent_type]
                contribution_with_agent.insert(i, {
                    "agent": {"@id": contribution_agent, "@type": contribution_agent_type}})
            else:
                contribution_with_agent.insert(i, contrib_uri)
        cls["contribution"] = contribution_with_agent

    def add_without_prefix(key, as_list: bool):
        ignore_same = True

        if key in cls and cls[key]:
            value = cls.pop(key, None)
            key_without_prefix = key.split(":")[1]
            if value:
                if key_without_prefix in cls and cls[key_without_prefix]:
                    if cls[key_without_prefix] != value or not ignore_same:
                        print(
                            f"Warning - {cls['@id']} - {key_without_prefix} - "
                            f" {cls[key_without_prefix]} will be overwritten by {value}"
                        )

                cls[key_without_prefix] = _to_list(value) if as_list else value

    to_add_as_list = [
        "schema:isPartOf",
        "rdfs:seeAlso",
        "schema:about",
        "bmo:usesCircuitWithProperty",
        "bmo:generatesCircuitWithProperty",
        "bmo:canHaveTType",
        "bmo:canHaveBrainRegion",
        "bmo:hasParameter",
        "bmo:isAssociatedWith",
        "bmo:expressionProfile",
        "bmo:isBasedOn",
        "bmo:molecule",
        "bmo:postsynapticNeuron",
        "bmo:presynapticNeuron",
        "nsg:hasFeature",
        "bmo:hasWorkflowDefinition",
        "bmo:hasLayerLocationPhenotype",
        "bmo:hasMorphologicalPhenotype",
        "nsg:hasLayerLocationPhenotype",
        "nsg:hasMorphologicalPhenotype",
        "bmo:hasType",
        "bmo:hasMType",
        "bmo:canBeLocatedInBrainRegion",
        "bmo:canHaveMType",
        "bmo:exposesParameter",
        "bmo:sourceType",
        "nsg:hasInstanceInSpecies",
        "bmo:targetType",
        "bmo:constraints",
        "owl:equivalentClass",
    ]

    for key in to_add_as_list:
        add_without_prefix(key, as_list=True)

    if "hasHierarchyView" in cls:
        # TODO unsure this is what is intended, it doesn't seem to do anything
        ct = cls.pop("hasHierarchyView", None)
        if ct:
            cls["hasHierarchyView"] = _to_list(ct)

    to_add_as_is = [
        "skos:prefLabel",
        "rdfs:label",
        "skos:definition",
        "skos:notation",
        "skos:altLabel"
    ]

    for key in to_add_as_is:
        add_without_prefix(key, as_list=False)

    if "isDefinedBy" in cls and cls["isDefinedBy"] and isinstance(cls["isDefinedBy"], list):
        cls["isDefinedBy"] = cls["isDefinedBy"][0]

    if "canBeLocatedInBrainRegion" in cls:
        propagated_brain_regions = []
        if cls["@id"] in GENERIC_CELL_TYPES:
            propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(
                ontology_graph, ROOT_BRAIN_REGION, GENERIC_CELL_TYPES[cls["@id"]]
            )
        elif "subClassOf" in cls and str(BMO.NeuronMorphologicalType) in cls["subClassOf"]:
            for sr in cls["canBeLocatedInBrainRegion"]:
                propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(
                    ontology_graph, sr, BMO.NeuronMorphologicalType
                )
        elif "subClassOf" in cls and str(BMO.NeuronElectricalType) in cls["subClassOf"]:
            for sr in cls["canBeLocatedInBrainRegion"]:
                propagated_brain_regions = _get_sub_regions_to_propagate_metype_to(
                    ontology_graph, sr, BMO.NeuronElectricalType
                )
        if len(propagated_brain_regions) > 0:
            cls["canBeLocatedInBrainRegion"] = [cls["canBeLocatedInBrainRegion"]] if isinstance(
                cls["canBeLocatedInBrainRegion"], str) else cls["canBeLocatedInBrainRegion"]
            # can it be a dict?
            cls["canBeLocatedInBrainRegion"].extend(propagated_brain_regions)

    if "atlas_id" in cls and cls["atlas_id"] == "None":
        cls["atlas_id"] = None
    if atlas_release_id and atlas_release_version:
        cls["atlasRelease"] = {"@id": atlas_release_id, "@type": "BrainAtlasRelease", "_rev": atlas_release_version}
    return cls


def _create_property_based_hierarchy(
        ontology_graph, cls_uriref, layer_urirefs,
        classes_relevant_for_layer, isPartOf_property_uriref
) -> List[str]:
    new_classes = []
    grand_parents = list(
        ontology_graph.objects(cls_uriref, isPartOf_property_uriref / SCHEMAORG.isPartOf))
    relevant_grand_parents = set()
    for c in classes_relevant_for_layer:
        s = {grand_parent for grand_parent in grand_parents if
             (grand_parent, SCHEMAORG.isPartOf * ZeroOrMore, c) in ontology_graph}
        relevant_grand_parents.update(s)

    next_cls_urirefs = []
    for grand_parent in relevant_grand_parents:
        grandParent_uncle_without_layer = []
        uncle_with_layer = []
        grand_parent_layers = list(
            ontology_graph.objects(grand_parent, NSG.hasLayerLocationPhenotype))
        uncles = list(ontology_graph.objects(grand_parent, SCHEMAORG.hasPart))
        uncle_layers = {}
        for uncle in uncles:
            uncle_layers[uncle] = list(ontology_graph.objects(uncle, NSG.hasLayerLocationPhenotype))
        for layer in layer_urirefs:
            grandParent_uncle_without_layer.extend(
                [(grand_parent, NSG.hasLayerLocationPhenotype, layer) not in ontology_graph,
                 (grand_parent, SCHEMAORG.hasPart / NSG.hasLayerLocationPhenotype,
                  layer) not in ontology_graph])

            uncle_with_layer.extend([(grand_parent,
                                      SCHEMAORG.hasPart / NSG.hasLayerLocationPhenotype,
                                      layer) in ontology_graph])

        if all(uncle_with_layer):
            # current class should be part of the uncle with same layers
            # if the uncle is not a leaf node with data. No need to create a new one
            next_cls_urirefs = []
            for uncle in uncles:
                if set(layer_urirefs) == set(uncle_layers):
                    ontology_graph.add((uncle, BMO.hasLayerPart, cls_uriref))
                    ontology_graph.add((cls_uriref, BMO.isLayerPartOf, uncle))
                    ontology_graph.add((uncle, BMO.hasHierarchyView, BMO.BrainLayer))
                    new_isPartOf_property_uriref = SCHEMAORG.isPartOf
                    next_cls_urirefs.append(uncle)
        elif set(grand_parent_layers) == set(layer_urirefs):
            # (grand_parent, NSG.hasLayerLocationPhenotype, term.URIRef(layer)) in ontology_graph:
            ontology_graph.add((grand_parent, BMO.hasLayerPart, cls_uriref))
            ontology_graph.add((cls_uriref, BMO.isLayerPartOf, grand_parent))
            ontology_graph.add((grand_parent, BMO.hasHierarchyView, BMO.BrainLayer))
            next_cls_urirefs = [grand_parent]
            new_isPartOf_property_uriref = BMO.isLayerPartOf

        else:  # if all(grandParent_uncle_without_layer) or set(layer_urirefs).issubset(set(grand_parent_layers)):
            # if the grand parent class does not have a layer and uncle does not have the layer
            # then create a corresponding layer location class with
            # label == the grand parent label, layer altLabel,
            # is part of (isLayerPartOf) of the grand parent which (contains it - hasLayerPart),
            # add the newly created class is parent of current class which contains it

            grand_parent_label = ontology_graph.value(subject=grand_parent, predicate=RDFS.label)
            grand_parent_notation = ontology_graph.value(subject=grand_parent,
                                                         predicate=SKOS.notation)
            layer_altLabels = [grand_parent_label]
            layer_notations = [grand_parent_notation]
            for layer in layer_urirefs:
                layer_altLabel = ontology_graph.value(subject=layer, predicate=SKOS.altLabel)
                layer_notation = ontology_graph.value(subject=layer, predicate=SKOS.notation)
                layer_altLabels.append(layer_altLabel)
                layer_notations.append(layer_notation)

            new_class_label = ", ".join(layer_altLabels)
            new_class_notation = "_".join(layer_notations)

            new_class_uri = "/".join([BRAIN_REGION_ONTOLOGY_URI, new_class_notation])
            ontology_graph.add((term.URIRef(new_class_uri), RDF.type, OWL.Class))
            ontology_graph.add(
                (term.URIRef(new_class_uri), RDFS.subClassOf, NSG.BrainRegion))
            ontology_graph.add((term.URIRef(new_class_uri), RDFS.label,
                                Literal(new_class_label, lang="en")))
            ontology_graph.add((term.URIRef(new_class_uri), SKOS.prefLabel,
                                Literal(new_class_label, lang="en")))
            ontology_graph.add(
                (term.URIRef(new_class_uri), SKOS.notation, Literal(new_class_notation)))

            ontology_graph.add((term.URIRef(new_class_uri), BMO.isLayerPartOf, grand_parent))
            ontology_graph.add((grand_parent, BMO.hasLayerPart, term.URIRef(new_class_uri)))
            ontology_graph.add((term.URIRef(new_class_uri), BMO.hasLayerPart, cls_uriref))
            ontology_graph.add((cls_uriref, BMO.isLayerPartOf, term.URIRef(new_class_uri)))
            ontology_graph.add((grand_parent, BMO.hasHierarchyView, BMO.BrainLayer))
            ontology_graph.add(
                (term.URIRef(new_class_uri), BMO.hasHierarchyView, BMO.BrainLayer))
            for layer in layer_urirefs:
                ontology_graph.add(
                    (term.URIRef(new_class_uri), NSG.hasLayerLocationPhenotype, layer))
            new_classes.append(new_class_uri)
            next_cls_urirefs = [term.URIRef(new_class_uri)]
            new_isPartOf_property_uriref = BMO.isLayerPartOf

        for next_cls_uriref in next_cls_urirefs:
            new_classes.extend(
                _create_property_based_hierarchy(
                    ontology_graph, next_cls_uriref, layer_urirefs,
                    classes_relevant_for_layer,
                    new_isPartOf_property_uriref)
            )
    return new_classes


def _get_sub_regions_to_propagate_metype_to(
        ontology_graph: Graph, from_brain_region, cell_type
) -> List[str]:
    propagated_brain_regions = []
    sub_brain_regions = ontology_graph.objects(term.URIRef(from_brain_region),
                                               SCHEMAORG.hasPart)
    for sub_brain_region in sub_brain_regions:
        if not ((sub_brain_region,
                 ~OWL.someValuesFrom / ~RDFS.subClassOf / RDFS.subClassOf / OWL.someValuesFrom,
                 BMO.BBP_contribution) in ontology_graph and
                (sub_brain_region,
                 ~OWL.someValuesFrom / ~RDFS.subClassOf / RDFS.subClassOf * ZeroOrMore,
                 cell_type) in ontology_graph):  # missing the canBeLocatedInBrainRegion
            propagated_brain_regions.append(str(sub_brain_region))
            propagated_brain_regions.extend(
                _get_sub_regions_to_propagate_metype_to(
                    ontology_graph, str(sub_brain_region), cell_type)
            )
    return propagated_brain_regions


def normalize_uris(filename, prefix, new_filename, format="turtle"):
    """Normalize resource URIs to the provided prefix."""
    reserved_namespaces = [
        "http://www.w3.org/2004/02/skos/core",
        str(RDF), str(RDFS), str(OWL), str(XSD)
    ]

    g = Graph()
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


def subontology_from_term(graph: Graph, entry_point, top_down=True, closed=True):
    """Get top/down or down/top subontology for a given term."""
    subgraph = Graph()
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
            if not isinstance(o, Literal):
                if p.eq(RDFS.subClassOf):
                    # Add subClassOf triples
                    if isinstance(o, URIRef):
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


def build_context_from_ontology(
        ontology_graph, forge_context, vocab=None, binding=None, exclude_deprecated=False
) -> Tuple[Context, List[str]]:
    """
    Build a jsonld context object.
    """
    # Check whether a term is already defined in the context
    # excludes brain region (https://neuroshapes.org/BrainRegion) values
    new_forge_context = _initialise_new_context(forge_context, vocab, binding)
    errors = []

    def is_deprecated(subject):
        t = list(ontology_graph.objects(subject, OWL.deprecated))
        return t[0] == Literal('true', datatype=XSD.boolean) if len(t) > 0 else False

    def on_failure(failed_subject, exc):
        defining_ontology = ontology_graph.objects(failed_subject, RDFS.isDefinedBy)
        errors.append(
            f"Failed to build context from {failed_subject} "
            f"defined in the ontology {str(list(defining_ontology))}: {exc}"
        )

    for cls in ontology_graph.subjects(RDF.type, OWL.Class):
        if not (not exclude_deprecated and is_deprecated(cls)):
            try:

                name, idref = _build_context_item(cls, new_forge_context)
                if name is not None and idref is not None and _is_class_to_include_in_context(cls, idref, ontology_graph):
                    new_forge_context.add_term(name, idref)
                    new_forge_context.document["@context"][name] = {"@id": idref}
            except Exception as e:
                on_failure(cls, e)

    for obj_prop in ontology_graph.subjects(RDF.type, OWL.ObjectProperty):
        if not (not exclude_deprecated and is_deprecated(obj_prop)):
            try:
                name, idref = _build_context_item(obj_prop, new_forge_context)
                if name is not None and idref is not None and _is_property_to_include_in_context(idref):
                    new_forge_context.add_term(name, idref, "@id")
                    new_forge_context.document["@context"][name] = {"@id": idref, "@type": "@id"}

            except Exception as e:
                on_failure(obj_prop, e)

    for annot_prop in ontology_graph.subjects(RDF.type, OWL.AnnotationProperty):
        if not (not exclude_deprecated and is_deprecated(annot_prop)):
            try:
                name, idref = _build_context_item(annot_prop, new_forge_context)
                if name is not None and idref is not None and _is_property_to_include_in_context(idref):
                    new_forge_context.add_term(name, idref)
                    new_forge_context.document["@context"][name] = {"@id": idref}
            except Exception as e:
                on_failure(annot_prop, e)

    return new_forge_context, errors


def _is_class_to_include_in_context(class_item: URIRef, uri_ref, ontology_graph: Graph):
    predicate_objects = [
        (
            RDFS.subClassOf * OneOrMore, [
                NSG.BrainRegion, NSG.Species, BMO.Mapping, BMO.BrainCellTranscriptomeType,
                BMO.NeuronElectricalType, BMO.NeuronMorphologicalType,
                BMO.NeurotransmitterType, BMO.NewNeuronType, BMO.GliaType,
                BMO.Ion, BMO.IonCurrent, NSG.PotassiumChannel, BMO.BrainArea, BMO.BrainLayer
            ]
        ),
        (
            RDFS.subClassOf * ZeroOrMore, [
                term.URIRef("http://purl.obolibrary.org/obo/NCBITaxon#_taxonomic_rank"),
                term.URIRef("http://purl.obolibrary.org/obo/PATO_0000001")
            ]
        )
    ]

    list_of_list_of_triples = [
        list(ontology_graph.triples((class_item, predicate, object_)))
        for predicate, list_objects in predicate_objects
        for object_ in list_objects
    ]

    return all(len(i) == 0 for i in list_of_list_of_triples) \
        and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/UBERON_")


def _is_property_to_include_in_context(uri_ref):
    ns, fragment = _split_uri(str(uri_ref))
    return str(ns) not in ["http://www.geneontology.org/formats/oboInOwl#",
                           "http://purl.obolibrary.org/obo/pato#",
                           "http://purl.obolibrary.org/obo/ro/subsets#",
                           "http://purl.obolibrary.org/obo/go#"] \
        and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/IAO_") \
        and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/RO_") \
        and not str(uri_ref).startswith("http://purl.obolibrary.org/obo/BFO_")


def build_context_from_schema(
        schema_graph: Graph, forge_context: Context, vocab=None,
        binding=None, exclude_deprecated=False
):
    new_forge_context = _initialise_new_context(forge_context, vocab, binding)
    errors = []

    if exclude_deprecated:
        t = list(schema_graph.subject_objects(OWL.deprecated))

        if len(t) > 0:
            deprecated = t[0][1] == Literal('true', datatype=XSD.boolean)
            if deprecated:
                return new_forge_context, errors

    # TODO this should be changed if we want to declare NodeShape not as direct children of shapes
    #  as found in some of the deprecated schemas
    for shape in schema_graph.subjects(RDF.type, SHACL.NodeShape):

        defining_schema = list(schema_graph.subjects(NXV.shapes, shape))

        for predicate in [SHACL.targetClass, SHACL.targetObjectsOf, SHACL.targetSubjectsOf]:
            for obj_value in schema_graph.objects(shape, predicate):
                try:
                    name, idref = _build_context_item(obj_value, new_forge_context)
                    if name is not None and idref is not None:
                        new_forge_context.add_term(name, idref)
                        new_forge_context.document["@context"][name] = {"@id": idref}
                except Exception as e:
                    errors.append(
                        f"Failed to build context from {obj_value} targeted by the shape {shape}"
                        f" in the schema {str(defining_schema)}: {e}"
                    )

    return new_forge_context, errors


def _initialise_new_context(forge_context, vocab, binding) -> Context:
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
            raise ValueError(
                f"The URI {str(uri_ref)} is present in the context under a name "
                f"{found_uri_ref.name} different of its fragment {fragment}"
            )
    else:  # uri_ref not in context
        if fragment in forge_context.terms:  # uri_ref not in context, fragment in
            if str(uri_ref) != forge_context.terms[fragment].id:
                # uri_ref not in context, fragment in but under different ns
                raise ValueError(
                    f"The fragment {fragment} of the term {str(uri_ref)} is present in the context "
                    f"under a different namespace {forge_context.terms[fragment].id}"
                )
        else:  # uri_ref not in context, fragment not in
            name, idref = fragment, str(uri_ref)  # a new context term can be created
    return name, idref


def _split_uri(uri):
    try:
        ns, fragment = namespace.split_uri(uri)
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
            if not isinstance(o, term.Literal):
                new_o = URIRef(new_o)
            else:
                new_o = Literal(new_o, o.language, o.datatype)

            triples_to_add.add((URIRef(new_s), URIRef(new_p), new_o))
            triples_to_remove.add((s, p, o))

    for el in triples_to_remove:
        graph.remove(el)
    for el in triples_to_add:
        graph.add(el)
    if ontology_uri:
        new_ontology_uri = uri_mapping.get(ontology_uri, ontology_uri)
        return term.URIRef(new_ontology_uri)
    return None


def replace_ontology_id(ontology_graph: Graph, new_id: term.URIRef) -> None:
    original_id = find_ontology_resource(ontology_graph)
    for s, p, o in ontology_graph:
        if s == original_id:
            ontology_graph.remove((s, p, o))
            if isinstance(o, term.Literal):
                o = term.Literal(str(o))
            ontology_graph.add((new_id, p, o))
        elif p == original_id:
            ontology_graph.remove((s, p, o))
            if isinstance(o, term.Literal):
                o = term.Literal(str(o))
            ontology_graph.add((s, new_id, o))
        elif o == original_id:
            ontology_graph.remove((s, p, o))
            ontology_graph.add((s, p, new_id))


def copy_ontology_label(ontology_graph, ontology_id,
                        other_ontology_graph, other_ontology_id,
                        append_label=None) -> None:
    """Copy the label from one ontology to another."""
    for o in ontology_graph.objects(ontology_id, RDFS.label):
        ontology_label = o
    if append_label:
        ontology_label = term.Literal(str(o) + append_label)
    other_ontology_graph.add((other_ontology_id, RDFS.label, ontology_label))


def all_ontologies_ids(ontology_graphs_dict: Dict[str, Graph]) -> Set[str]:
    all_ontologies_ids = set()
    for _, ontology_graph in ontology_graphs_dict.items():
        ontology = find_ontology_resource(ontology_graph)
        all_ontologies_ids.add(str(ontology))
        slim_id = get_slim_ontology_id(ontology)
        all_ontologies_ids.add(str(slim_id))
    return all_ontologies_ids
