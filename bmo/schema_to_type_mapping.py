from typing import Dict, List, Tuple
from collections import defaultdict
import json
from rdflib import RDF, Graph, OWL
from kgforge.core import KnowledgeGraphForge, Resource
from bmo.registration import _register_update
from bmo.utils import NXV, SHACL


def get_shapes_in_schemas(schemas_graph: Graph) -> List[Tuple]:
    shapes_in_schema = list(schemas_graph.subject_objects(NXV.shapes))

    def is_deprecated(schema):
        dep = list(
            schemas_graph.objects(schema, OWL.deprecated))
        return len(dep) == 1 and dep[0].value

    return [(schema, shape) for (schema, shape) in shapes_in_schema if not is_deprecated(schema)]


def get_node_shapes_in_schemas(schemas_graph: Graph) -> List[Tuple]:
    non_deprecated_schemas = get_shapes_in_schemas(schemas_graph)

    return [
        (schema, shape) for (schema, shape) in non_deprecated_schemas
        if shape in list(schemas_graph.subjects(RDF.type, SHACL.NodeShape))
    ]


# Decomposing the steps allows for better testing
def get_schema_to_target_classes_1(schemas_graph: Graph) -> Dict[str, List]:
    node_shapes_in_schemas = get_node_shapes_in_schemas(schemas_graph)

    res = defaultdict(list)
    for schema, shape in node_shapes_in_schemas:
        res_i = list(schemas_graph.objects(shape, SHACL.targetClass))
        res[schema].extend(res_i)

    return res


def get_schema_to_target_classes_2(
        schemas_graph: Graph, forge: KnowledgeGraphForge
) -> Dict[str, List]:

    query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?type ?shape ?resource_id WHERE {{
            {{ ?shape sh:targetClass ?type .
               ?resource_id <{NXV.shapes}> ?shape .
               OPTIONAL {{ ?resource_id owl:deprecated ?dep }}
               FILTER (!bound(?dep) ||  ?dep = "false"^^xsd:boolean)
            }} UNION {{
                SELECT (?shape as ?type) ?shape ?resource_id WHERE {{
                    ?shape a sh:NodeShape .
                    ?shape a rdfs:Class .
                    ?resource_id <{NXV.shapes}> ?shape .
                    OPTIONAL {{ ?resource_id owl:deprecated ?dep }}
                    FILTER (!bound(?dep) ||  ?dep = "false"^^xsd:boolean)

                }}
            }}
        }} ORDER BY ?type
    """

    # Second half of union doesn't seem to return anything so far

    sparql_result = schemas_graph.query(query_object=query)
    sparql_result_json = sparql_result.serialize(format="json")
    bindings = json.loads(sparql_result_json)["results"]["bindings"]

    results_resources = forge.from_json(bindings)

    into_dict = defaultdict(list)
    for el in results_resources:
        into_dict[el.resource_id.value].append(el.type.value)

    return into_dict


def enforce_single_target_class(schema_to_type_mapping: Dict[str, List]) -> Dict[str, str]:
    multiple_target_classes = dict((a, b) for (a, b) in schema_to_type_mapping.items() if len(b) > 1)
    if len(multiple_target_classes) > 0:
        raise Exception(f"Some schemas are targeting multiple classes: {multiple_target_classes}")

    return dict((a, b[0]) for (a, b) in schema_to_type_mapping.items())


def create_update_type_to_schema_mapping(
        all_schema_graphs: Graph, forge: KnowledgeGraphForge, data_update: bool, tag: str
) -> Resource:

    schema_target_class: Dict[str, List] = get_schema_to_target_classes_2(all_schema_graphs, forge)
    schema_target_class: Dict[str, str] = enforce_single_target_class(schema_target_class)

    schema_to_type_mapping = dict(
        (schema, forge._model.context().to_symbol(class_))
        for schema, class_ in schema_target_class.items()
    )

    schema_id = "https://bbp.epfl.ch/shapes/dash/schematotypemapping"

    id_ = f"{forge._store.endpoint}/resources/{forge._store.bucket}/_/schema_to_type_mapping"

    mapping = Resource()
    mapping.id = id_
    mapping.name = "Schema to Type Mapping"
    mapping.type = ["SchemaToTypeMapping"]
    mapping.value = schema_to_type_mapping

    forge.validate(mapping, type_="SchemaToTypeMapping")

    if data_update:
        _register_update(
            forge, mapping, schema_id=schema_id, tag=tag,
            raise_on_fail=True, type_str="SchemaToTypeMapping"
        )
    return mapping
