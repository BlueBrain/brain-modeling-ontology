import glob
import json
import os
from copy import deepcopy
from typing import Dict, List, Tuple
from rdflib import Namespace, Graph
from kgforge.core import KnowledgeGraphForge, Resource


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
    "obo": "http://purl.obolibrary.org/obo/",
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


SCHEMA_JSONLD_CONTEXT_PATH = "./jsonldcontext/schema.json"
DATA_JSONLD_CONTEXT_PATH = "./jsonldcontext/neuroshapes_org.json"


def initialise_graph() -> Graph:
    graph = Graph()
    for prefix, mapping in PREFIX_MAPPINGS.items():
        graph.bind(prefix, Namespace(mapping))
    return graph


def load_schemas(
        schema_dir: str,
        transformed_schema_path: str,
        forge: KnowledgeGraphForge,
        recursive=False,
        save_transformed_schema=False

) -> Tuple[Dict[str, Dict], Dict[str, str], Graph]:

    all_schema_graphs: Graph = initialise_graph()
    schemas_files: List[str] = glob.glob(schema_dir, recursive=recursive)

    schema_graphs_dict = {}
    schema_id_to_filepath_dict = {}

    for schema_file in schemas_files:

        with open(schema_file, 'r') as sfr:
            schema_jsonld = json.load(sfr)

        schema_file_path_parts = schema_file.split("/")
        schema_subdir = schema_file_path_parts[-2]
        schema_subdir_parent = schema_file_path_parts[-3]
        schema_name, _ = os.path.splitext(schema_file_path_parts[-1])

        original_schema_context = deepcopy(schema_jsonld["@context"])

        schema_jsonld["@context"] = ["./jsonldcontext/schema.json"] +\
                                    [d for d in schema_jsonld["@context"] if isinstance(d, dict)]

        schema_resource: Resource = forge.from_jsonld(schema_jsonld)
        schema_jsonld_expanded: Dict = forge.as_jsonld(schema_resource, form="expanded")

        schema_jsonld_expanded_graph = Graph().parse(data=schema_jsonld_expanded, format="json-ld")

        all_schema_graphs.parse(data=schema_jsonld_expanded, format="json-ld")

        # This is needed for ontodocs to be able to generate doc web app
        if save_transformed_schema:

            shapes_jsonld_expanded_directory = os.path.join(
                transformed_schema_path,
                schema_subdir_parent if schema_subdir != "commons" else "",
                schema_subdir
            )

            os.makedirs(shapes_jsonld_expanded_directory, exist_ok=True)

            new_filename = schema_name + ".ttl"

            schema_jsonld_expanded_graph.serialize(
                os.path.join(shapes_jsonld_expanded_directory, new_filename), format="ttl"
            )

        schema_resource.context = original_schema_context
        schema_jsonld["@context"] = original_schema_context

        owl_imports = schema_resource.imports if hasattr(schema_resource, "imports") else []

        schema_graphs_dict[schema_file] = {
            "resource": schema_resource,
            "graph": schema_jsonld_expanded_graph,
            "jsonld": schema_jsonld,
            "imports": owl_imports,
            "id": schema_resource.id
        }
        schema_id_to_filepath_dict[schema_resource.id] = schema_file

    return schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs


def load_ontologies(ontology_dir: str) -> Tuple[Dict, Graph]:
    all_ontology_graphs: Graph = initialise_graph()
    ontology_files = glob.glob(ontology_dir)

    ontology_graphs_dict = {}
    errors = []
    for ontology_path in ontology_files:
        try:
            # remove_non_ascii(ontology_path)
            # read the ontology
            ontology_graph = Graph()
            for prefix, mapping in PREFIX_MAPPINGS.items():
                ontology_graph.bind(prefix, Namespace(mapping))
            ontology_graph.parse(ontology_path, format="turtle")
            all_ontology_graphs.parse(ontology_path, format="turtle")
            ontology_graphs_dict[ontology_path] = ontology_graph
        except Exception as e:
            errors.append(f"Failed to load ontology {ontology_path}: {e}")
        if len(errors) > 0:
            raise ValueError(f"Failed to load ontologies: {errors}")
    return ontology_graphs_dict, all_ontology_graphs
