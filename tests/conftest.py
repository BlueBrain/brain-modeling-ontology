import glob

import pytest
import rdflib
from kgforge.core import KnowledgeGraphForge, Resource
from rdflib import RDFS, Namespace, RDF, OWL
import bmo.ontologies as bmo
from bmo.utils import BMO, MBA, NXV, SCHEMAORG
from register_ontologies import _merge_ontology, _initialize_forge_objects
from bmo.loading import load_ontologies, load_schemas


def pytest_addoption(parser):
    parser.addoption("--environment", action="store",
                     default="https://staging.nise.bbp.epfl.ch/nexus/v1")
    parser.addoption("--bucket", action="store", default="neurosciencegraph/datamodels")
    parser.addoption("--atlas_parcellation_ontology", action="store",
                     default="https://bbp.epfl.ch/neurosciencegraph/data/ontologies/34388d3b-0b88-4deb-9686-6fcd9ef8990e")
    parser.addoption("--atlas_parcellation_ontology_version", action="store", default=None)
    parser.addoption("--atlas_parcellation_ontology_bucket", action="store", default="bbp/atlas")
    parser.addoption("--token", action="store")


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


@pytest.fixture(scope="session")
def token(pytestconfig):
    return pytestconfig.getoption("token")


@pytest.fixture(scope="session")
def environment(pytestconfig):
    return pytestconfig.getoption("environment")


@pytest.fixture(scope="session")
def bucket(pytestconfig):
    return pytestconfig.getoption("bucket")


@pytest.fixture(scope="session")
def atlas_parcellation_ontology(pytestconfig):
    return pytestconfig.getoption("atlas_parcellation_ontology")


@pytest.fixture(scope="session")
def atlas_parcellation_ontology_version(pytestconfig):
    return pytestconfig.getoption("atlas_parcellation_ontology_version")


@pytest.fixture(scope="session")
def atlas_parcellation_ontology_bucket(pytestconfig):
    return pytestconfig.getoption("atlas_parcellation_ontology_bucket")


@pytest.fixture(scope="session")
def ontology_dir(pytestconfig):
    return "./ontologies/bbp"


@pytest.fixture(scope="session")
def schema_dir(pytestconfig):
    return "./shapes"


@pytest.fixture(scope="session")
def transformed_schema_path(pytestconfig):
    return "./ontologies/bbp/shapes_jsonld_expanded"


@pytest.fixture(scope="session")
def forge_objects(environment, bucket, token, atlas_parcellation_ontology_bucket):
    return _initialize_forge_objects(
        endpoint=environment, input_bucket=bucket, token=token,
        atlas_parcellation_ontology_bucket=atlas_parcellation_ontology_bucket
    )


@pytest.fixture(scope="session")
def forge(forge_objects):
    return forge_objects[0]


@pytest.fixture(scope="session")
def forge_atlas(forge_objects):
    return forge_objects[2]


@pytest.fixture(scope="session")
def forge_schema(forge_objects):
    return forge_objects[1]


@pytest.fixture(scope="session")
def data_jsonld_context(forge, all_ontology_graphs):
    forge_context = forge._model.context()
    new_jsonld_context, errors = bmo.build_context_from_ontology(all_ontology_graphs[0],
                                                                 forge_context)
    return new_jsonld_context, errors


@pytest.fixture(scope="session")
def all_ontology_graphs(ontology_dir):
    ontology_pattern = f"{ontology_dir}/*.ttl"
    ontology_files = glob.glob(ontology_pattern)

    try:
        ontology_graphs_dict, all_ontology_graphs = load_ontologies(ontology_pattern)
        assert len(all_ontology_graphs) > 0
        assert len(ontology_files) > 0
        assert len(ontology_graphs_dict) == len(ontology_files)
        assert len(ontology_graphs_dict) == len(
            list(all_ontology_graphs.subjects(RDF.type, OWL.Ontology)))
        return all_ontology_graphs, ontology_graphs_dict
    except Exception as e:
        missing_ontologies = set([filepath.split('/')[-1] for filepath in ontology_files]) - \
                             set([filepath.split('/')[-1] for filepath in
                                  ontology_graphs_dict.keys()])

        pytest.fail(
            f"Failed to load all ontologies in {ontology_dir}. "
            f"Not loaded ontologies are: {missing_ontologies}: {e}"
        )


@pytest.fixture(scope="session")
def framed_classes(data_jsonld_context, all_ontology_graphs, atlas_hierarchy_ontology_graph):
    new_jsonld_context, errors = data_jsonld_context[0], data_jsonld_context[1]
    assert len(errors) == 0

    ontology_graph = all_ontology_graphs[0]
    ontology_graphs_dict = all_ontology_graphs[1]

    brain_region_graph = ontology_graphs_dict["./ontologies/bbp/brainregion.ttl"]

    atlas_ontology_graph = atlas_hierarchy_ontology_graph[0]
    atlas_hierarchy = atlas_hierarchy_ontology_graph[1]

    triples_to_add, triples_to_remove = _merge_ontology(
        atlas_ontology_graph, brain_region_graph,
        ontology_graph, [
            SCHEMAORG.hasPart,
            SCHEMAORG.isPartOf, RDFS.label, MBA.atlas_id, MBA.color_hex_triplet,
            MBA.graph_order, MBA.hemisphere_id, MBA.st_level, SCHEMAORG.identifier,
            BMO.representedInAnnotation, BMO.regionVolumeRatioToWholeBrain, BMO.regionVolume
        ]
    )
    class_ids, class_jsons, all_blank_node_triples, new_classes = bmo.frame_classes(
        ontology_graph, new_jsonld_context, new_jsonld_context.document,
        atlas_hierarchy.atlasRelease.id, atlas_hierarchy.atlasRelease._rev
    )
    return (
        class_ids, class_jsons, ontology_graph, triples_to_add, triples_to_remove,
        atlas_hierarchy.atlasRelease.id, atlas_hierarchy.atlasRelease._rev
    )


@pytest.fixture(scope="session")
def atlas_hierarchy_ontology_graph(atlas_parcellation_ontology, atlas_parcellation_ontology_version,
                                   forge_atlas):
    try:
        version = int(
            atlas_parcellation_ontology_version) if atlas_parcellation_ontology_version is not None else atlas_parcellation_ontology_version
        atlas_hierarchy = forge_atlas.retrieve(atlas_parcellation_ontology, version=version)
        assert hasattr(atlas_hierarchy, "atlasRelease")
        assert hasattr(atlas_hierarchy.atlasRelease, "_rev")
        atlas_hierarchy_jsonld_distribution = [
            distrib for distrib in atlas_hierarchy.distribution
            if distrib.encodingFormat == "application/ld+json"
        ]
        atlas_hierarchy_jsonld_distribution = atlas_hierarchy_jsonld_distribution[0]
        forge_atlas.download(atlas_hierarchy_jsonld_distribution, follow="contentUrl", path=".",
                             overwrite=True)
        atlas_hierarchy_ontology_graph = rdflib.Graph().parse(
            atlas_hierarchy_jsonld_distribution.name, format="json-ld")
        assert len(atlas_hierarchy_ontology_graph) > 0
        return atlas_hierarchy_ontology_graph, atlas_hierarchy
    except Exception as e:
        pytest.fail(f"Failed to load {atlas_parcellation_ontology}: {e}")


@pytest.fixture(scope="session")
def all_schema_graphs(transformed_schema_path, schema_dir, forge_schema):
    schema_pattern = f"{schema_dir}/**/*.json"
    recursive = True
    schema_filenames = glob.glob(schema_pattern, recursive=recursive)

    # non_deprecated_schemas = [
    #     schema_filename for schema_filename in schema_filenames
    #     if not json.load(open(schema_filename, 'r')).get("owl:deprecated", False)
    # ]

    try:
        schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs = load_schemas(
            schema_pattern, transformed_schema_path, forge_schema, recursive,
            save_transformed_schema=False
        )
        assert len(all_schema_graphs) > 0
        assert len(schema_id_to_filepath_dict) == len(schema_id_to_filepath_dict)

        assert len(schema_filenames) > 0
        assert len(schema_graphs_dict) == len(schema_filenames)
        assert len(schema_graphs_dict) == len(
            list(all_schema_graphs.subjects(RDF.type, NXV.Schema)))
        all_imported_schemas = all_schema_graphs.objects(None, OWL.imports)
        all_imported_schemas = {str(r) for r in all_imported_schemas}
        loaded_schema = set(schema_id_to_filepath_dict.keys())
        assert len(loaded_schema) >= len(set(all_imported_schemas))
        assert all_imported_schemas.issubset(
            loaded_schema), f"Imported schemas are missing: {all_imported_schemas - loaded_schema}"
        schema_id_to_filepath_dict_values = list(schema_id_to_filepath_dict.values())
        for k, v in schema_graphs_dict.items():
            assert k in schema_filenames
            assert k in schema_id_to_filepath_dict_values
            assert len(v) == 5
            assert "resource" in v
            assert isinstance(v["resource"], Resource)
            assert "graph" in v
            assert isinstance(v["graph"], rdflib.Graph)
            assert "imports" in v
            assert "id" in v
            assert "jsonld" in v
        return all_schema_graphs, schema_graphs_dict, schema_id_to_filepath_dict
    except Exception as e:
        missing_schemas = set([filepath.split('/')[-1] for filepath in schema_filenames]) - \
                          set([filepath.split('/')[-1] for filepath in schema_graphs_dict.keys()])
        pytest.fail(
            f"Failed to load all schemas in {schema_dir}. "
            f"Not loaded schemas are {missing_schemas}. {e}"
        )
