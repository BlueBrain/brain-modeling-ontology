import pytest

import json
import re
from rdflib import term
from bmo.loading import DATA_JSONLD_CONTEXT_PATH
from bmo.slim_ontologies import SLIM_GRAPH_PREDICATES
from bmo.utils import (
    ATLAS_PROPERTIES_TO_MERGE,
    BMO,
    BRAIN_REGION_ONTOLOGY_URI,
    CELL_TYPE_ONTOLOGY_URI,
    NSG,
    SCHEMAORG,
    MBA,
)

import rdflib
from kgforge.core.commons import Context
from rdflib import RDFS, XSD, Literal, RDF, OWL, SH, Graph
from rdflib.paths import OneOrMore, ZeroOrMore
from rdflib.term import URIRef
from typing import List, Optional, Type

import bmo.ontologies as bmo
from bmo.slim_ontologies import create_slim_ontology_graph, create_slim_classes


@pytest.fixture
def example_ontology_json(data_jsonld_context):
    jsonld_context, _ = data_jsonld_context
    context = jsonld_context.document["@context"]
    return {
              "@context": context,
              "@type": "Ontology",
              "defines": [
                  {"@id": "http://purl.obolibrary.org/obo/GO_0005575",
                   "@type": "Class",
                   "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"],
                   "equivalentClass": ["https://bbp.epfl.ch/ontologies/core/bmo/SubcellularPart"],
                   "label": "Cellular Component",
                   "definition": "A location, relative to cellular compartments and structures.",
                   "altLabel": ["cell or subcellular entity", "cellular component"],
                   "atlasRelease": {
                       "@id": "https://bbp.epfl.ch/neurosciencegraph/data/4906ab85-694f-469d-962f-c0174e901885",
                       "_rev": 3}},
                  {"@id": "http://purl.obolibrary.org/obo/GO_0005739",
                   "@type": "Class",
                   "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"],
                   "equivalentClass": ["https://bbp.epfl.ch/ontologies/core/bmo/Mitochondrion"],
                   "atlasRelease": {
                       "@id": "https://bbp.epfl.ch/neurosciencegraph/data/4906ab85-694f-469d-962f-c0174e901885",
                       "_rev": 3}},
                  {"@id": "http://purl.obolibrary.org/obo/GO_0005783",
                   "@type": "Class",
                   "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"],
                   "equivalentClass": ["https://bbp.epfl.ch/ontologies/core/bmo/EndoplasmicReticulum"],
                   "atlasRelease": {
                       "@id": "https://bbp.epfl.ch/neurosciencegraph/data/4906ab85-694f-469d-962f-c0174e901885",
                       "_rev": 3}},
                  {"@id": "http://purl.obolibrary.org/obo/GO_0005829",
                   "@type": "Class",
                   "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"],
                   "equivalentClass": ["https://bbp.epfl.ch/ontologies/core/bmo/Cytosol"],
                   "atlasRelease": {
                       "@id": "https://bbp.epfl.ch/neurosciencegraph/data/4906ab85-694f-469d-962f-c0174e901885",
                       "_rev": 3}},
                  {"@id": "http://purl.obolibrary.org/obo/GO_0030424",
                   "@type": "Class",
                   "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"],
                   "equivalentClass": ["https://neuroshapes.org/Axon"],
                   "atlasRelease": {
                       "@id": "https://bbp.epfl.ch/neurosciencegraph/data/4906ab85-694f-469d-962f-c0174e901885",
                       "_rev": 3}},
              ],
              "label": "Example Ontology"
            }


@pytest.fixture
def example_ontology_graph(example_ontology_json):
    return Graph().parse(
        data=json.dumps(example_ontology_json),
        format="json-ld"
    )


def test_slim_ontology_graph(example_ontology_graph):
    keep_attributes = SLIM_GRAPH_PREDICATES
    keep_types = [OWL.Ontology, OWL.Class]
    slim_graph = create_slim_ontology_graph(example_ontology_graph,
                                            keep_attributes, keep_types)

    # Check the keep attributes are actually kept
    for p in keep_attributes:
        for s, o in example_ontology_graph.subject_objects(p):
            if p == RDF.type:
                if o not in keep_types:
                    continue
            elif isinstance(o, term.Literal):
                o = term.Literal(str(o))
            if (s, p, o) not in slim_graph:
                raise ValueError(f'The tripe {(s, p, o)} was not found in the slim_graph')


@pytest.mark.parametrize(
    "keep_attributes,expected",
    [
        pytest.param((['@id']),
                     ([{"@id": "http://purl.obolibrary.org/obo/GO_0005575"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005739"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005783"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005829"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0030424"}]),
                     id='only_ids'),
        pytest.param((['@id', 'label']),
                     ([{"@id": "http://purl.obolibrary.org/obo/GO_0005575",
                        "label": "Cellular Component"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005739"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005783"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005829"},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0030424"}]),
                     id='ids_labels'),
        pytest.param((['@id', 'subClassOf']),
                     ([{"@id": "http://purl.obolibrary.org/obo/GO_0005575",
                        "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"]},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005739",
                        "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"]},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005783",
                        "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"]},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0005829",
                        "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"]},
                       {"@id": "http://purl.obolibrary.org/obo/GO_0030424",
                        "subClassOf": ["https://bbp.epfl.ch/ontologies/core/bmo/Mapping"]}]
                      ),
                     id='ids_labels')
    ]
)
def test_reduce_classes(example_ontology_json, keep_attributes, expected):
    classes = example_ontology_json['defines']
    slim_classes = create_slim_classes(classes, keep_attributes)
    assert slim_classes == expected


def test_terms_aligned_with_context(all_ontology_graphs, all_schema_graphs):

    with open(DATA_JSONLD_CONTEXT_PATH, "r") as f:
        previous_forge_context_json = json.load(f)
    graph_of_all_ontologies = all_ontology_graphs[0]
    graph_of_all_schemas = all_schema_graphs[0]
    forge_context = Context(
        previous_forge_context_json["@context"], previous_forge_context_json["@id"]
    )
    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(
        graph_of_all_ontologies, forge_context
    )
    new_jsonld_context, schema_errors = bmo.build_context_from_schema(
        graph_of_all_schemas, new_jsonld_context
    )
    errors = []
    errors.extend(ontology_errors)
    errors.extend(schema_errors)
    assert len(errors) == 0
    assert new_jsonld_context.iri == forge_context.iri
    assert set(forge_context.document.keys()).issubset(
        new_jsonld_context.document.keys()
    )


def test_ontologies_classes_conform_schemas(forge, all_ontology_graphs):
    pass
    # Tests that all:
    #  - ontologies conform to the schema https://neuroshapes.org/dash/ontology
    #  - classes conform to the schema https://neuroshapes.org/dash/ontologyentity

    # ontologies = forge.from_graph(all_ontology_graphs[0], type="Ontology", use_model_context=True)
    # forge.validate(ontologies, _type="Ontology")
    # classes = forge.from_graph(all_ontology_graphs[0], type="Class", use_model_context=True)
    # forge.validate(classes, _type="Class")


def test_classes_have_only_class_type(all_ontology_graphs):
    classes_with_multiple_types = []
    ontology_graphs, _ = all_ontology_graphs
    for cls in ontology_graphs.subjects(RDF.type, OWL.Class):
        for obj in ontology_graphs.objects(cls, RDF.type):
            if obj != OWL.Class:
                classes_with_multiple_types.append(cls)
    assert len(classes_with_multiple_types) == 0


def test_classes_object_annotation_properties_are_disjoint(all_ontology_graphs):
    obj_prop_instances = []
    class_prop_instances = []
    graph_of_all_ontologies = all_ontology_graphs[0]  # rdflib.Graph() with all ontologies
    for obj_prop in graph_of_all_ontologies.subjects(RDF.type, OWL.ObjectProperty):
        if (obj_prop, RDF.type, OWL.AnnotationProperty) in graph_of_all_ontologies:
            obj_prop_instances.append(obj_prop)
        if (obj_prop, RDF.type, OWL.Class) in graph_of_all_ontologies:
            class_prop_instances.append(obj_prop)
    for annotation_prop in graph_of_all_ontologies.subjects(
        RDF.type, OWL.AnnotationProperty
    ):
        if (annotation_prop, RDF.type, OWL.Class) in graph_of_all_ontologies:
            class_prop_instances.append(annotation_prop)

    assert len(obj_prop_instances) == 0
    assert len(class_prop_instances) == 0


def test_no_topObjectProperty_instances(all_ontology_graphs):
    graph_of_all_ontologies = all_ontology_graphs[0]
    topobj_prop_instances = graph_of_all_ontologies.subjects(
        RDF.type, OWL.topObjectProperty
    )
    assert len(list(topobj_prop_instances)) == 0


def test_atlas_hierarchy_brainregions_merge_ontology(
    forge,
    atlas_hierarchy_ontology_graph_classes,
    brain_region_ontologygraph_classes,
    all_ontology_graph_merged_brain_region_atlas_hierarchy,
    atlas_hierarchy_ontology_graph,
    framed_class_json_dict,
):
    brain_region_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[1]

    for atlas_hierarchy_class in atlas_hierarchy_ontology_graph_classes:
        assert (
            str(atlas_hierarchy_class) in framed_class_json_dict
        ), f"{str(atlas_hierarchy_class)} should be present in the framed classes."
        # the types of bmo.utils.ATLAS_PROPERTIES_TO_MERGE with indice to indice matching
        properties_to_merge_types = [
            list,
            list,
            str,
            str,
            str,
            str,
            str,
            int,
            str,
            bool,
            dict,
            dict,
        ]
        errors = []
        for i, prop in enumerate(ATLAS_PROPERTIES_TO_MERGE):
            atlas_hierarchy_class_prop_val = list(
                atlas_hierarchy_ontology_graph.objects(atlas_hierarchy_class, prop)
            )
            brain_region_graph_class_prop_val = list(
                brain_region_graph.objects(atlas_hierarchy_class, prop)
            )
            assert len(atlas_hierarchy_class_prop_val) == len(
                brain_region_graph_class_prop_val
            ), (
                f"{str(atlas_hierarchy_class)}"
                f" should have the same number of values for the property {str(prop)} in atlas ({atlas_hierarchy_class_prop_val})"
                f"and in the brain region ontologies {brain_region_graph_class_prop_val}."
            )
            if properties_to_merge_types[i] not in [list, dict]:
                assert len(atlas_hierarchy_class_prop_val) <= 1, (
                    f"{str(atlas_hierarchy_class)} should have one or no value for the property {str(prop)}."
                    f"Found {atlas_hierarchy_class_prop_val}."
                )
                if len(atlas_hierarchy_class_prop_val) == 1:
                    atlas_hierarchy_class_prop_val = atlas_hierarchy_class_prop_val[
                        0
                    ].value
                    brain_region_graph_class_prop_val = (
                        brain_region_graph_class_prop_val[0].value
                    )
            else:
                atlas_hierarchy_class_prop_val = sorted(
                    [
                        (
                            str(prop_val)
                            if isinstance(prop_val, rdflib.term.URIRef)
                            else prop_val
                        )
                        for prop_val in atlas_hierarchy_class_prop_val
                    ]
                )
                brain_region_graph_class_prop_val = sorted(
                    [
                        (
                            str(prop_val)
                            if isinstance(prop_val, rdflib.term.URIRef)
                            else prop_val
                        )
                        for prop_val in brain_region_graph_class_prop_val
                    ]
                )
            if (
                prop == BMO.regionVolume or prop == BMO.regionVolumeRatioToWholeBrain
            ) and _is_represented_in_annotation(
                atlas_hierarchy_ontology_graph, atlas_hierarchy_class
            ):
                assert len(atlas_hierarchy_class_prop_val) == 1, (
                    f"{str(atlas_hierarchy_class)},"
                    f"represented in the annotation should have exactly one value for the property {str(prop)}. Found {atlas_hierarchy_class_prop_val}."
                )
                brain_region_graph_class_prop_val = brain_region_graph_class_prop_val[0]
                atlas_hierarchy_class_prop_val = atlas_hierarchy_class_prop_val[0]
                assert isinstance(brain_region_graph_class_prop_val, rdflib.term.BNode)
                _, _, blank_node_triples = bmo._process_blank_nodes(
                    brain_region_graph,
                    brain_region_graph_class_prop_val,
                    process_restriction=False,
                )
                assert len(blank_node_triples) == 2
                assert (
                    brain_region_graph_class_prop_val,
                    SCHEMAORG.value,
                    atlas_hierarchy_class_prop_val,
                ) in blank_node_triples
                assert (
                    brain_region_graph_class_prop_val,
                    SCHEMAORG.unitCode,
                    Literal("cubic micrometer"),
                ) in blank_node_triples
                expected_prop_json_val = {
                    "value": atlas_hierarchy_class_prop_val.value,
                    "unitCode": "cubic micrometer",
                }
            else:
                assert (
                    atlas_hierarchy_class_prop_val == brain_region_graph_class_prop_val
                ), (
                    f"{str(prop)} should have the value "
                    f"{atlas_hierarchy_class_prop_val} in the brain region ontology. Found: {brain_region_graph_class_prop_val}"
                )
                expected_prop_json_val = atlas_hierarchy_class_prop_val
            prop_symbol = forge._model.context().to_symbol(prop)
            prop_fragment = forge._model.context()._prep_expand(prop_symbol)[2]
            if (
                atlas_hierarchy_class != MBA["997"] or prop != SCHEMAORG.isPartOf
            ):  # MBA["997"] is the root so is not part of another class
                if expected_prop_json_val:
                    errors.extend(
                        _check_dict_for_property_type_value(
                            framed_class_json_dict[str(atlas_hierarchy_class)],
                            [prop_fragment],
                            [properties_to_merge_types[i]],
                            [expected_prop_json_val],
                            sort_values=True,
                        )
                    )
        assert len(errors) == 0, f"The followings errors were found: {errors}"


def test_all_classes_are_extracted(
    framed_classes, all_ontology_graph_merged_brain_region_atlas_hierarchy
):

    class_ids, class_jsons, _ = framed_classes

    all_ontology_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[0]

    assert len(class_ids) == len(class_jsons)

    classes = [str(e) for e in all_ontology_graph.subjects(RDF.type, OWL.Class)]
    instances = [str(e) for e in all_ontology_graph.subjects(RDF.type, OWL.NamedIndividual)]

    cls_int = classes + instances

    assert len(cls_int) > 0
    assert len(cls_int) == len(class_jsons)


"""
def test_all_jsonld_classes_have_same_triples_then_in_ttl(data_jsonld_context, forge, all_ontology_graphs):
    #forge_context = forge._model.context()
    new_jsonld_context, errors = data_jsonld_context[0], data_jsonld_context[1] #bmo.build_context_from_ontology(all_ontology_graphs[0], forge_context)

    class_ids, class_jsons, all_blank_node_triples = bmo.frame_classes(all_ontology_graphs[0], new_jsonld_context,
                                                                       new_jsonld_context.document)

    #for cls in class_jsons:
    #    cls["@context"] = new_jsonld_context.document
    #    cls_graph_jsonld = rdflib.Graph().parse(data=json.dumps(cls), format="json-ld")
    #    cls_triples_all = all_ontology_graphs[0].triples((URIRef(cls.get("@id")), None, None))
    #    #assert len(list(cls_triples_all)) == len(list(cls_graph_jsonld.triples((URIRef(cls.get("@id")), None, None))))
"""


def test_one_type_one_schema(all_schema_graphs):
    schema_graphs, schema_graphs_dict, schema_id_to_filepath_dict = all_schema_graphs
    targeted_class_triples = set(schema_graphs.triples((None, SH.targetClass, None)))
    targeted_classes = {}
    for t in targeted_class_triples:
        if t[0] not in targeted_classes:
            targeted_classes[str(t[0])] = [t[2]]
        else:
            targeted_classes[str(t[0])].append(str(t[2]))
    all_t = [len(v) == 1 for k, v in targeted_classes.items()]
    assert all(all_t)


def test_metype_correctedly_propagated(all_ontology_graphs, forge):
    ontology_graph = all_ontology_graphs[0]
    forge._debug = True
    brain_region = "http://api.brain-map.org/api/v2/data/Structure/315"
    # Try forge.resolve("Isocortex", scope="ontology", target="terms", strategy=ResolvingStrategy.EXACT_MATCH)
    propagated_brain_regions = bmo._get_sub_regions_to_propagate_metype_to(
        ontology_graph, brain_region, bmo.BMO.NeuronMorphologicalType
    )
    expected_propagated_brain_regions = ontology_graph.objects(
        URIRef(brain_region), bmo.SCHEMAORG.hasPart * OneOrMore
    )
    expected_propagated_brain_regions = {
        str(br) for br in expected_propagated_brain_regions
    }
    assert set(propagated_brain_regions) == expected_propagated_brain_regions


def test_brain_region_same_leaves_in_all_hierarchy(all_ontology_graphs):
    ontology_graph = all_ontology_graphs[0]

    isocortex_brain_region_uri = "http://api.brain-map.org/api/v2/data/Structure/315"
    ammons_horn_brain_region_uri = "http://api.brain-map.org/api/v2/data/Structure/375"
    anterior_cingulate_area_dorsal_part_layer_6b = (
        "http://api.brain-map.org/api/v2/data/Structure/927"
    )

    current_class_layers = list(
        ontology_graph.objects(
            URIRef(anterior_cingulate_area_dorsal_part_layer_6b),
            NSG.hasLayerLocationPhenotype,
        )
    )
    classes_relevant_for_layer = set()
    for layer in current_class_layers:
        classes_relevant_for_layer = set(
            ontology_graph.objects(
                URIRef(layer), RDFS.subClassOf * OneOrMore / SCHEMAORG.about
            )
        )

    new_classes = bmo._create_property_based_hierarchy(
        ontology_graph,
        URIRef(anterior_cingulate_area_dorsal_part_layer_6b),
        current_class_layers,
        classes_relevant_for_layer,
        SCHEMAORG.isPartOf,
    )
    assert len(new_classes) == 0

    ammons_horn_brain_region_layer_leaves = set(
        ontology_graph.objects(
            URIRef(ammons_horn_brain_region_uri), BMO.hasLayerLeafRegionPart
        )
    )
    ammons_horn_brain_region_default_leaves = set(
        ontology_graph.objects(
            URIRef(ammons_horn_brain_region_uri), BMO.hasLeafRegionPart
        )
    )
    assert (
        ammons_horn_brain_region_layer_leaves == ammons_horn_brain_region_default_leaves
    )

    isocortex_brain_region_layer_in_annotation_leaves = _get_in_annotation_leaves(
        isocortex_brain_region_uri, ontology_graph, BMO.hasLayerLeafRegionPart
    )
    isocortex_brain_region_default_in_annotation_leaves = _get_in_annotation_leaves(
        isocortex_brain_region_uri, ontology_graph, BMO.hasLeafRegionPart
    )
    assert (
        isocortex_brain_region_layer_in_annotation_leaves
        == isocortex_brain_region_default_in_annotation_leaves
    )


def test_multitype_entities_are_namedindividuals(framed_classes):
    classes_json = framed_classes[1]
    errors = []
    for class_json in classes_json:
        if isinstance(class_json['@type'], list):
            if 'Class' in class_json['@type']:
                errors.append(f"{class_json['@id']} - class should only have type `Class`")
            elif 'NamedIndividual' not in class_json['@type']:
                errors.append(f"{class_json['@id']} - non-class term is expected to be a `NamedIndividual`")

    assert len(errors) == 0, errors


def test_all_classes_have_label_notation_not_plus(framed_classes):
    class_jsons = [e for e in framed_classes[1] if not e.get("deprecated", False)]

    errors = []
    for class_json in class_jsons:
        regexp = re.compile(r"[+]")
        if regexp.search(class_json["@id"]):
            errors.append(
                f"Class URIs should not have '+' character: {class_json['@id']}"
            )
        errors.extend(
            _check_dict_for_property_type_value(class_json, ["label"], [str], None)
        )
        if "notation" in class_json:
            errors.extend(
                _check_dict_for_property_type_value(
                    class_json, ["notation"], [str], None
                )
            )
    assert len(errors) == 0, errors


def test_musmusculus_rat_labels(framed_class_json_dict):
    mus_musculus_class_json = framed_class_json_dict[
        "http://purl.obolibrary.org/obo/NCBITaxon_10090"
    ]
    rattus_class_json = framed_class_json_dict[
        "http://purl.obolibrary.org/obo/NCBITaxon_10116"
    ]
    errors = _check_dict_for_property_type_value(
        mus_musculus_class_json, ["label"], [str], ["Mus musculus"]
    )
    errors.extend(
        _check_dict_for_property_type_value(
            rattus_class_json, ["label"], [str], ["Rattus norvegicus"]
        )
    )
    assert len(errors) == 0, errors


@pytest.mark.skip(reason="To be used when information is complete")
def test_all_etypes_have_definition(framed_class_json_dict, all_ontology_graphs):
    ontology_graph = all_ontology_graphs[0]
    all_etypes = ontology_graph.subjects(RDFS.subClassOf, BMO.NeuronElectricalType)
    errors = []
    for etype in all_etypes:
        etype_class_json = framed_class_json_dict[str(etype)]
        errors.extend(
            _check_dict_for_property_type_value(etype_class_json, ["definition"], [str])
        )
    assert len(errors) == 0, errors


@pytest.fixture(scope="session")
def non_deprecated_brain_regions_in_ontology_graph(all_ontology_graph_merged_brain_region_atlas_hierarchy):
    graph_of_all_ontologies, _ = all_ontology_graph_merged_brain_region_atlas_hierarchy
    non_deprecated_br = [
        e for e in list(graph_of_all_ontologies.subjects(RDFS.subClassOf, NSG.BrainRegion))
        if not bmo._is_deprecated(e, graph_of_all_ontologies)
    ]
    return non_deprecated_br


def test_all_brain_regions_have_annotations(
    framed_class_json_dict,
    atlas_release_prop,
    non_deprecated_brain_regions_in_ontology_graph,
    atlas_release_version,
):
    properties_to_check = ["label", "notation", "prefLabel"]
    errors = []
    for cls in non_deprecated_brain_regions_in_ontology_graph:
        assert str(cls) in framed_class_json_dict
        cls_json = framed_class_json_dict[str(cls)]
        cls_properties = properties_to_check + ["atlasRelease"]
        e = _check_dict_for_property_type_value(
            cls_json,
            cls_properties,
            [str, str, str, dict],
            [None, None, None, atlas_release_prop],
        )
        errors.extend(e)
        assert atlas_release_version >= 1
    assert len(errors) == 0, errors


def test_all_non_layer_brain_regions_have_representedInAnnotation(
    framed_class_json_dict, non_deprecated_brain_regions_in_ontology_graph, all_ontology_graph_merged_brain_region_atlas_hierarchy
):
    ontology_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[0]
    errors = []
    for cls in non_deprecated_brain_regions_in_ontology_graph:
        cls_json = framed_class_json_dict[str(cls)]
        if (cls, RDFS.subClassOf * ZeroOrMore, BMO.BrainLayer) not in ontology_graph:
            e = _check_dict_for_property_type_value(
                cls_json, ["hasHierarchyView"], [list], None
            )
            errors.extend(e)
            assert (cls, BMO.representedInAnnotation, None) in ontology_graph
            assert "representedInAnnotation" in cls_json
            is_represented_in_annotation = _is_represented_in_annotation(
                ontology_graph, cls
            )
            assert isinstance(is_represented_in_annotation, Literal)
            assert isinstance(cls_json["representedInAnnotation"], bool)
            assert str(is_represented_in_annotation) in ["true", "false"]
            assert cls_json["representedInAnnotation"] in [True, False]
            if cls_json["representedInAnnotation"]:
                assert (cls, BMO.regionVolume, None) in ontology_graph
                assert (cls, BMO.regionVolumeRatioToWholeBrain, None) in ontology_graph
                assert "regionVolume" in cls_json
                assert "regionVolumeRatioToWholeBrain" in cls_json
                assert cls_json["regionVolume"]["unitCode"] == "cubic micrometer"
                assert (
                    cls_json["regionVolumeRatioToWholeBrain"]["unitCode"]
                    == "cubic micrometer"
                )
                assert isinstance(cls_json["regionVolume"]["value"], float)
                assert isinstance(
                    cls_json["regionVolumeRatioToWholeBrain"]["value"], float
                )
            else:
                assert (cls, BMO.regionVolume, None) not in ontology_graph
                assert (
                    cls,
                    BMO.regionVolumeRatioToWholeBrain,
                    None,
                ) not in ontology_graph
                assert "regionVolume" not in cls_json
                assert "regionVolumeRatioToWholeBrain" not in cls_json
    assert len(errors) == 0, errors


def _is_represented_in_annotation(ontology_graph, cls):
    is_represented_in_annotation = list(
        ontology_graph.objects(cls, BMO.representedInAnnotation)
    )
    assert len(is_represented_in_annotation) == 1
    return is_represented_in_annotation[0]


def test_layered_child_has_same_layer_as_parent(
    non_deprecated_brain_regions_in_ontology_graph,
    all_ontology_graph_merged_brain_region_atlas_hierarchy
):
    ontology_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[0]

    for cls in non_deprecated_brain_regions_in_ontology_graph:
        if (cls, RDFS.subClassOf * ZeroOrMore, BMO.BrainLayer) not in ontology_graph:
            # all non layer brain regions (i.e classes that are layers are not wanted)
            if (cls, NSG.hasLayerLocationPhenotype, None) in ontology_graph:
                # if they have a layer associated (e.g Primary auditory area, layer 6b)
                current_class_layers = list(
                    ontology_graph.objects(cls, NSG.hasLayerLocationPhenotype)
                )  # the layers of the current class
                grand_parents = list(
                    ontology_graph.objects(cls, BMO.isLayerPartOf / SCHEMAORG.isPartOf)
                )  # the grand parents through a layer hierarchy
                for layer in current_class_layers:
                    # The highest class to which descendants the layer is relevant
                    # (e.g layer 2 is only relevant for Isocortex descendants. So layer 2 is about Isocortex)
                    classes_relevant_for_layer = set(
                        ontology_graph.objects(
                            layer, RDFS.subClassOf * OneOrMore / SCHEMAORG.about
                        )
                    )
                    assert (
                        len(classes_relevant_for_layer) > 0
                    ), f"Layer '{layer}' does not apply to a class"
                    relevant_grand_parents = set()
                    for c in classes_relevant_for_layer:
                        # collect all grand parents that are layer descendants of one of the classes_relevant_for_layer
                        s = {
                            grand_parent
                            for grand_parent in grand_parents
                            if (grand_parent, BMO.isLayerPartOf * OneOrMore, c)
                            in ontology_graph
                        }
                        relevant_grand_parents.update(s)

                    for rg in relevant_grand_parents:
                        assert (
                            rg,
                            NSG.hasLayerLocationPhenotype,
                            layer,
                        ) in ontology_graph, (
                            f"Class {str(cls)} is a layer descendant of the class '{str(rg)} but "
                            f"has a layer '{layer}' not associated with the grandparents"
                        )

            # is_layer_part_ofs = set(ontology_graph.objects(cls, BMO.isLayerPartOf))
            # waiting to clarify if to enforce at most a single parent for layer based hierarchy
            # assert len (is_layer_part_ofs) in [0,1]
            is_part_ofs = set(ontology_graph.objects(cls, SCHEMAORG.isPartOf))
            assert len(is_part_ofs) in [0, 1], (
                f"Class {str(cls)} should have at most 1 value for isPartOf property "
                f"instead of {len(is_part_ofs)}."
                f"The following values were found: {is_part_ofs}."
            )


def _check_dict_for_property_type_value(
    cls_json: dict,
    properties: List[str],
    expected_types: Optional[List[Type]] = None,
    expected_values: Optional[List[str]] = None,
    sort_values=False,
):
    assert not expected_types or len(properties) == len(expected_types)
    assert not expected_values or len(properties) == len(expected_values)
    errors = []
    for i, p in enumerate(properties):
        if p not in cls_json:
            errors.append(f"Property {p} not present in {cls_json}")
        else:
            message = f"Value '{cls_json[p]}' of property '{p}' in resource '{cls_json['@id']}' does not have "
            if expected_types and not isinstance(cls_json[p], expected_types[i]):
                errors.append(message + f"the expected type '{expected_types[i]}' ")
            if expected_values and expected_values[i]:
                if sort_values and expected_types[i] in [dict, list]:
                    value, expected_value = sorted(cls_json[p]), sorted(
                        expected_values[i]
                    )
                else:
                    value, expected_value = cls_json[p], expected_values[i]
                if value != expected_value:
                    errors.append(
                        message + f"the expected value '{expected_values[i]}' "
                    )
    return errors


def test_frame_ontologies(framed_ontologies, atlas_release_prop):
    errors = []

    for ontology_uri, (ontology_json, _) in framed_ontologies.items():

        annotation_properties = ["@context", "@id", "@type", "label"]
        expected_annotation_properties_values = [
            "https://neuroshapes.org",
            ontology_uri,
            "Ontology",
            None,
        ]
        e = _check_dict_for_property_type_value(
            ontology_json,
            annotation_properties,
            [str, str, str, str],
            expected_annotation_properties_values,
        )
        errors.extend(e)
        if ontology_uri == BRAIN_REGION_ONTOLOGY_URI:
            hasHierarchyView = [
                {
                    "@id": "https://bbp.epfl.ch/ontologies/core/bmo/BrainLayer",
                    "label": "Layer",
                    "description": "Layer based hierarchy",
                    "hasParentHierarchyProperty": "isLayerPartOf",
                    "hasChildrenHierarchyProperty": "hasLayerPart",
                    "hasLeafHierarchyProperty": "hasLayerLeafRegionPart",
                },
                {
                    "@id": "https://neuroshapes.org/BrainRegion",
                    "label": "BrainRegion",
                    "description": "Atlas default brain region hierarchy",
                    "hasParentHierarchyProperty": "isPartOf",
                    "hasChildrenHierarchyProperty": "hasPart",
                    "hasLeafHierarchyProperty": "hasLeafRegionPart",
                },
            ]
            e = _check_dict_for_property_type_value(
                ontology_json,
                ["hasHierarchyView", "atlasRelease"],
                [list, dict],
                [hasHierarchyView, atlas_release_prop],
            )
            errors.extend(e)
        if ontology_uri == CELL_TYPE_ONTOLOGY_URI:
            assert "defines" not in ontology_json
        else:
            e = _check_dict_for_property_type_value(
                ontology_json, ["defines"], [list], None
            )
            errors.extend(e)
            assert all(
                map(lambda k: isinstance(k, dict), ontology_json["defines"])
            ), f"One defined class of the ontology {ontology_uri} is not of type dict."
        assert len(errors) == 0, errors


def test_frame_ontologies_do_not_have_deprecated_classes(framed_ontologies):

    res = {}
    for ontology_uri, (ontology_json, ontology_graph) in framed_ontologies.items():
        if "defines" in ontology_json:
            deprecated_things = list(ontology_graph.subjects(OWL.deprecated, Literal(True, datatype=XSD.boolean)))
            deprecated_classes_in_defines = [
                e["@id"] for e in ontology_json["defines"]
                if URIRef(e["@id"]) in deprecated_things
            ]
            res[ontology_uri] = deprecated_classes_in_defines
        else:
            res[ontology_uri] = []

    assert all(len(v) == 0 for v in res.values()), f"Some deprecated classes were found in the 'defines' fields of some ontologies {res}"


def _get_in_annotation_leaves(
    uri: str, ontology_graph: Graph, view_leaf_property_uri_ref: URIRef
):
    leaves = set(ontology_graph.objects(URIRef(uri), view_leaf_property_uri_ref))
    return {
        leaf
        for leaf in leaves
        if (leaf, BMO.representedInAnnotation, Literal(True, datatype=XSD.boolean))
        in ontology_graph
    }


def test_deprecated_have_valid_type(all_ontology_graphs):
    graph_of_all_ontologies, _ = all_ontology_graphs
    deprecated_subjects = list(graph_of_all_ontologies.subjects(OWL.deprecated, Literal(True, datatype=XSD.boolean)))
    types = [OWL.Class, OWL.NamedIndividual, OWL.AnnotationProperty, OWL.ObjectProperty]
    have_class_or_named_individual = dict(
        (s, any((s, RDF.type, type_) in graph_of_all_ontologies for type_ in types))
        for s in deprecated_subjects
    )
    failed = [s for s, has_valid_type in have_class_or_named_individual.items() if not has_valid_type]
    assert len(failed) == 0, f"These are flagged as deprecated but are neither classes nor named individuals: {failed} "
