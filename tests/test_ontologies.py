import json
from bmo.utils import BMO, NSG, SCHEMAORG, NXV

import pytest
import rdflib
from kgforge.core.commons import Context
from kgforge.core.commons.strategies import ResolvingStrategy
from rdflib import RDFS, XSD, Literal, RDF, OWL, SH
import bmo.ontologies as bmo
from register_ontologies import JSONLD_CONTEXT_IRI, _merge_ontology
from rdflib.paths import OneOrMore, ZeroOrMore, inv_path, neg_path



def test_terms_aligned_with_context(forge, all_ontology_graphs, all_schema_graphs):

    with open ("./jsonldcontext/neuroshapes_org.json", "r") as f:
        previous_forge_context_json = json.load(f)

    forge_context = Context(previous_forge_context_json["@context"], previous_forge_context_json["@id"])
    new_jsonld_context, ontology_errors = bmo.build_context_from_ontology(all_ontology_graphs[0], forge_context)
    new_jsonld_context, schema_errors = bmo.build_context_from_schema(all_schema_graphs[0], new_jsonld_context)
    errors = []
    errors.extend(ontology_errors)
    errors.extend(schema_errors)
    assert len(errors) == 0
    assert new_jsonld_context.iri == forge_context.iri
    assert set(forge_context.document.keys()).issubset(new_jsonld_context.document.keys())


def test_ontologies_classes_conform_schemas(forge, all_ontology_graphs):
    pass
    #Tests that all:
    #  - ontologies conform to the schema https://neuroshapes.org/dash/ontology
    #  - classes conform to the schema https://neuroshapes.org/dash/ontologyentity

    #ontologies = forge.from_graph(all_ontology_graphs[0], type="Ontology", use_model_context=True)
    #forge.validate(ontologies, _type="Ontology")
    #classes = forge.from_graph(all_ontology_graphs[0], type="Class", use_model_context=True)
    #forge.validate(classes, _type="Class")
    

def test_classes_instances_are_disjoint(forge, all_ontology_graphs):
    classes_instances = []
    for cls in all_ontology_graphs[0].subjects(RDF.type, OWL.Class):
        if (cls, RDF.type, OWL.NamedIndividual) in all_ontology_graphs[0]:
            classes_instances.append(cls)
    assert len(classes_instances) == 0


def test_object_annotation_properties_are_disjoint(forge, all_ontology_graphs):
    obj_prop_instances = []
    for obj_prop in all_ontology_graphs[0].subjects(RDF.type, OWL.ObjectProperty):
        if (obj_prop, RDF.type, OWL.AnnotationProperty) in all_ontology_graphs[0]:
            obj_prop_instances.append(obj_prop)
    assert len(obj_prop_instances) == 0

def test_no_topObjectProperty_instances(forge, all_ontology_graphs):
    topobj_prop_instances = all_ontology_graphs[0].subjects(RDF.type, OWL.topObjectProperty)
    assert len(list(topobj_prop_instances)) == 0


def test_all_classes_are_extracted(framed_classes):

    class_ids   = framed_classes[0] 
    class_jsons = framed_classes[1]
    all_ontology_graph = framed_classes[2]
    triples_to_add = framed_classes[3]
    triples_to_remove = framed_classes[4]

    assert len(class_ids) == len(class_jsons)

    classes = all_ontology_graph.subjects(RDF.type, OWL.Class)
    classes = [str(c) for c in classes]
    instances = all_ontology_graph.subjects(RDF.type, OWL.NamedIndividual)
    instances = [str(i) for i in instances]
    cls_int = []
    cls_int.extend(classes)
    cls_int.extend(instances)
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
    #    cls_triples_all = all_ontology_graphs[0].triples((rdflib.term.URIRef(cls.get("@id")), None, None))
    #    #assert len(list(cls_triples_all)) == len(list(cls_graph_jsonld.triples((rdflib.term.URIRef(cls.get("@id")), None, None))))
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
    forge._debug=True
    brain_region = "http://api.brain-map.org/api/v2/data/Structure/315" # Try forge.resolve("Isocortex", scope="ontology", target="terms", strategy=ResolvingStrategy.EXACT_MATCH)
    propagated_brain_regions = bmo._get_sub_regions_to_propagate_metype_to(ontology_graph, brain_region, bmo.BMO.NeuronMorphologicalType)
    expected_propagated_brain_regions  = ontology_graph.objects(rdflib.term.URIRef(brain_region), bmo.SCHEMAORG.hasPart*OneOrMore)
    expected_propagated_brain_regions = {str(br) for br in expected_propagated_brain_regions}
    assert set(propagated_brain_regions)  == expected_propagated_brain_regions
    

def test_brain_region_same_leaves_in_all_hierarchy(all_ontology_graphs):
    ontology_graph = all_ontology_graphs[0]

    isocortex_brain_region_uri = "http://api.brain-map.org/api/v2/data/Structure/315"
    ammons_horn_brain_region_uri = "http://api.brain-map.org/api/v2/data/Structure/375"
    anterior_cingulate_area_dorsal_part_layer_6b = "http://api.brain-map.org/api/v2/data/Structure/927"

    current_class_layers = list(ontology_graph.objects(rdflib.term.URIRef(anterior_cingulate_area_dorsal_part_layer_6b), NSG.hasLayerLocationPhenotype))
    classes_relevant_for_layer = set()
    for layer in current_class_layers:
        classes_relevant_for_layer = set(ontology_graph.objects(rdflib.term.URIRef(layer), RDFS.subClassOf*OneOrMore/SCHEMAORG.about))

    new_classes = bmo._create_property_based_hierarchy(ontology_graph, rdflib.term.URIRef(anterior_cingulate_area_dorsal_part_layer_6b), 
                                                    current_class_layers, classes_relevant_for_layer, SCHEMAORG.isPartOf)
    assert len(new_classes) == 0

    ammons_horn_brain_region_layer_leaves = set(ontology_graph.objects(rdflib.term.URIRef(ammons_horn_brain_region_uri), BMO.hasLayerLeafRegionPart))
    ammons_horn_brain_region_default_leaves = set(ontology_graph.objects(rdflib.term.URIRef(ammons_horn_brain_region_uri), BMO.hasLeafRegionPart))
    assert ammons_horn_brain_region_layer_leaves == ammons_horn_brain_region_default_leaves

    isocortex_brain_region_layer_in_annotation_leaves = _get_in_annotation_leaves(isocortex_brain_region_uri, ontology_graph, BMO.hasLayerLeafRegionPart)
    isocortex_brain_region_default_in_annotation_leaves =  _get_in_annotation_leaves(isocortex_brain_region_uri, ontology_graph, BMO.hasLeafRegionPart)
    assert isocortex_brain_region_layer_in_annotation_leaves == isocortex_brain_region_default_in_annotation_leaves

def test_layered_child_has_same_parent_layer(framed_classes):
    class_ids   = framed_classes[0] 
    class_jsons = framed_classes[1]
    ontology_graph = framed_classes[2]
    triples_to_add = framed_classes[3]
    triples_to_remove = framed_classes[4]
    atlasRelease_id = framed_classes[5]
    atlasRelease_version = framed_classes[6]

    assert len(triples_to_remove) > 0
    assert len(triples_to_add) >  0
    
    framed_class_json_dict = dict(zip(class_ids, class_jsons))
    mus_musculus_class_json = framed_class_json_dict["http://purl.obolibrary.org/obo/NCBITaxon_10090"]
    assert mus_musculus_class_json["label"] == {'@language': 'en', '@value': 'Mus musculus'}
    for cls in ontology_graph.subjects(RDFS.subClassOf, NSG.BrainRegion):
        assert str(cls) in framed_class_json_dict
        cls_json = framed_class_json_dict[str(cls)]
        assert "atlasRelease" in cls_json
        assert cls_json["atlasRelease"]["@id"] ==  atlasRelease_id
        assert cls_json["atlasRelease"]["_rev"] ==  atlasRelease_version
        if (cls, RDFS.subClassOf*ZeroOrMore, BMO.BrainLayer) not in ontology_graph: 
            assert (cls, BMO.representedInAnnotation, None) in ontology_graph
            assert "representedInAnnotation" in cls_json
            is_represented_in_annotation = list(ontology_graph.objects(cls, BMO.representedInAnnotation))
            assert len(is_represented_in_annotation) == 1
            is_represented_in_annotation = is_represented_in_annotation[0]
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
                assert cls_json["regionVolumeRatioToWholeBrain"]["unitCode"] == "cubic micrometer"
                assert isinstance(cls_json["regionVolume"]["value"], float)
                assert isinstance(cls_json["regionVolumeRatioToWholeBrain"]["value"], float)
            else:
                assert (cls, BMO.regionVolume, None) not in ontology_graph
                assert (cls, BMO.regionVolumeRatioToWholeBrain, None) not in ontology_graph
                assert "regionVolume" not in cls_json
                assert "regionVolumeRatioToWholeBrain" not in cls_json
            if (cls, NSG.hasLayerLocationPhenotype, None) in ontology_graph:
                grand_parents = list(ontology_graph.objects(cls, BMO.isLayerPartOf/SCHEMAORG.isPartOf))
                current_class_layers = list(ontology_graph.objects(cls, NSG.hasLayerLocationPhenotype))
                for layer in current_class_layers:
                    classes_relevant_for_layer = set(ontology_graph.objects(layer, RDFS.subClassOf*OneOrMore/SCHEMAORG.about)) 
                    relevant_grand_parents = set()
                    for c in classes_relevant_for_layer:
                        s= {grand_parent for grand_parent in grand_parents if (grand_parent, BMO.isLayerPartOf*OneOrMore, c) in ontology_graph}
                        relevant_grand_parents.update(s)
                    assert len(classes_relevant_for_layer) > 0
                    for rg in relevant_grand_parents:
                        assert (rg, NSG.hasLayerLocationPhenotype, layer) in ontology_graph
            #is_layer_part_ofs = set(ontology_graph.objects(cls, BMO.isLayerPartOf)) # waiting to clarify if to enforce at most a single parent for layer based hierarchy
            is_part_ofs = set(ontology_graph.objects(cls, SCHEMAORG.isPartOf)) 
            #assert len (is_layer_part_ofs) in [0,1]
            assert len(is_part_ofs) in [0,1]


   

def test_all_schema_are_valid(all_schema_graphs, data_jsonld_context):
    schema_graphs, schema_graphs_dict, schema_id_to_filepath_dict = all_schema_graphs
    jsonld_context_from_ontologies, _ = data_jsonld_context
    for schema_file, schema_content_dict in schema_graphs_dict.items():
        used_shapes = get_referenced_shapes(None, schema_content_dict["graph"], SH.node|SH.property) # used shapes
        already_imported_schemas = []
        directly_imported_schemas, transitive_imported_schemas = get_imported_schemas(jsonld_context_from_ontologies, schema_content_dict, schema_graphs_dict,
                                                                                       schema_id_to_filepath_dict, already_imported_schemas, expand_uri=True,
                                                                                         transitive_imports=True)
        for imported_schema in transitive_imported_schemas:
            # check imported schemas are defined
            assert imported_schema in schema_id_to_filepath_dict # there is a file within which the imported_schema is defined
            # check no recursive schema import
            imported_schema_content_dict = get_imported_schema_content_dict(schema_graphs_dict, schema_id_to_filepath_dict,imported_schema)
            if "imports" in imported_schema_content_dict:
                already_imported_schemas = []
                _, transitive_imported_imported_schemas = get_imported_schemas(jsonld_context_from_ontologies, imported_schema_content_dict, schema_graphs_dict, 
                                                                               schema_id_to_filepath_dict, already_imported_schemas, expand_uri=True,
                                                                                 transitive_imports=True)
                
                message = f"The schema {schema_content_dict['id']} located in {schema_file} imported the schema {imported_schema} " + \
                          f"that recursively imports it: {transitive_imported_imported_schemas}. A schema should not be (recursively)" + \
                           "imported by one of its imported schema"
                
                assert schema_content_dict["id"] not in transitive_imported_imported_schemas, message
        
        # check imported schemas are actually used
        for imported_schema in directly_imported_schemas:   
            imported_schema_content_dict = get_imported_schema_content_dict(schema_graphs_dict, schema_id_to_filepath_dict,imported_schema)
            imported_shapes = get_referenced_shapes(rdflib.term.URIRef(imported_schema),imported_schema_content_dict["graph"], NXV.shapes|(NXV.shapes/SH.property)) # defined shapes
            
            message = f"The schema {schema_content_dict['id']} located in {schema_file} imported the schema {imported_schema}" + \
                      f"but is not using a shape from it. Used shapes are: {used_shapes} while imported shapes are: {imported_shapes}." + \
                      "For each imported schema, there should be at least one used shape."
            
            assert (len(used_shapes) == 0) or (len(set(used_shapes).intersection(imported_shapes)) >= 1), message
        
        # check used schemas are defined locally or imported
        for used_shape in used_shapes:
            imported_shema_defines_shape=[]
            imported_shema_defines_shape.append(is_shape_defined_by_schema(schema_content_dict["id"], schema_content_dict["graph"], used_shape))
            for imported_schema in set(transitive_imported_schemas):
                imported_schema_content_dict = get_imported_schema_content_dict(schema_graphs_dict, schema_id_to_filepath_dict,imported_schema)
                imported_shema_defines_shape.append(is_shape_defined_by_schema(imported_schema, imported_schema_content_dict["graph"], used_shape))
            
            message = f"The schema '{schema_content_dict['id']}' located in {schema_file} used a shape {used_shape} defined by {imported_shema_defines_shape.count(True)}" + \
                      f"(imported or local) schemas. Imported schemas are: {transitive_imported_schemas}. Each used shapes should be defined by local or imported schemas."
            
            assert imported_shema_defines_shape.count(True) >= 1,  message

    #check against SHACL of SHACL
    # https://incf.github.io/neuroshapes/contexts/schema.json is in

def get_imported_schemas(jsonld_context, schema_content_dict, schema_graphs_dict, schema_id_to_filepath_dict, already_imported_schemas=[], expand_uri=True, transitive_imports=True):
    imported_schemas = set()
    transitive_imported_schemas = set()
    if schema_content_dict["id"] not in already_imported_schemas:
        already_imported_schemas.append(schema_content_dict["id"])
        if "imports" in schema_content_dict:
            imported_schemas = {jsonld_context.expand(i) for i in schema_content_dict["imports"]}
            transitive_imported_schemas.update(imported_schemas)
            if transitive_imports:
                for imported_schema in imported_schemas:
                    imported_schema_file  = schema_id_to_filepath_dict[imported_schema]
                    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
                    i_p, t_i_s = get_imported_schemas(jsonld_context, imported_schema_content_dict, schema_graphs_dict, schema_id_to_filepath_dict,
                                                       already_imported_schemas, expand_uri, transitive_imports)
                    transitive_imported_schemas.update(t_i_s)
            already_imported_schemas.extend(list(imported_schemas))
    return imported_schemas, transitive_imported_schemas

def is_shape_defined_by_schema(schema_id, schema_graph, shape):
    shema_defines_shape = []
    # A shape is defined by a schema if it is linked to it through the "NXV.shapes" property either directly or with SH["and"], SH["or"], SH["xone"] and SH["property"]
    # SH["and"], SH["or"], SH["xone"] properties being RDF lists, they need to be traversed using (RDF.rest|RDF.first|RDF.rest)*ZeroOrMore
    shema_defines_shape.append((rdflib.term.URIRef(schema_id), NXV.shapes, shape) in schema_graph)
    shema_defines_shape.append((rdflib.term.URIRef(schema_id), NXV.shapes/SH["and"]*ZeroOrMore/(RDF.rest|RDF.first|RDF.rest)*ZeroOrMore, shape) in schema_graph)
    shema_defines_shape.append((rdflib.term.URIRef(schema_id), NXV.shapes/SH["or"]*ZeroOrMore/(RDF.rest|RDF.first|RDF.rest)*ZeroOrMore, shape) in schema_graph)
    shema_defines_shape.append((rdflib.term.URIRef(schema_id), NXV.shapes/SH["xone"]*ZeroOrMore/(RDF.rest|RDF.first|RDF.rest)*ZeroOrMore, shape) in schema_graph)
    shema_defines_shape.append((rdflib.term.URIRef(schema_id), NXV.shapes/SH["property"], shape) in schema_graph)
    return shema_defines_shape.count(True) >= 1

def get_imported_schema_content_dict(schema_graphs_dict, schema_id_to_filepath_dict,imported_schema):
    imported_schema_file  = schema_id_to_filepath_dict[imported_schema]
    imported_schema_content_dict = schema_graphs_dict[imported_schema_file]
    return imported_schema_content_dict

def get_referenced_shapes(schema_uri, schema_graph, sparql_path):
    defined_shapes = []
    for defined_shape in schema_graph.objects(schema_uri, sparql_path):
        if not isinstance(defined_shape,rdflib.term.BNode):
            defined_shapes.append(defined_shape)
    return defined_shapes

def _get_in_annotation_leaves(uri, ontology_graph, view_leaf_property_uri_ref):
    leaves = set(ontology_graph.objects(rdflib.term.URIRef(uri), view_leaf_property_uri_ref))
    return {l for l in leaves if (l, BMO.representedInAnnotation, Literal(True, datatype=XSD.boolean)) in ontology_graph}
 