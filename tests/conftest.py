import glob

from kgforge.core.resource import Resource
import pytest
import rdflib
from rdflib import RDF, OWL, RDFS
from rdflib.paths import ZeroOrMore
import bmo.ontologies as bmo
from bmo.argument_parsing import define_arguments
from bmo.utils import (
    BMO,
    NSG,
    NXV,
    _get_ontology_annotation_lang_context,
)
from bmo.loading import load_ontologies, load_schemas
from scripts.register_ontologies import (
    _initialize_forge_objects,
    _merge_ontology,
    combine_jsonld_context
)


def pytest_addoption(parser):
    parser = define_arguments(parser)
    parser.addoption("--no_randomisation", action="store", default=False, type=bool)


@pytest.fixture(scope="session")
def randomize(pytestconfig):
    return not pytestconfig.getoption("no_randomisation")


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
    return pytestconfig.getoption("ontology_dir")


@pytest.fixture(scope="session")
def slim_ontology_dir(pytestconfig):
    return pytestconfig.getoption("slim_ontology_dir")


@pytest.fixture(scope="session")
def schema_dir(pytestconfig):
    return pytestconfig.getoption("schema_dir")


@pytest.fixture(scope="session")
def transformed_schema_path(pytestconfig):
    return pytestconfig.getoption("transformed_schema_path")


@pytest.fixture(scope="session")
def forge_objects(environment, bucket, token, atlas_parcellation_ontology_bucket):
    if environment == "staging":
        endpoint = "https://staging.nise.bbp.epfl.ch/nexus/v1"
    elif environment == "production":
        endpoint = "https://bbp.epfl.ch/nexus/v1"
    else:
        raise ValueError(
            'Environment argument must be either "staging" or "production" '
        )

    return _initialize_forge_objects(
        endpoint=endpoint,
        input_bucket=bucket,
        token=token,
        atlas_parcellation_ontology_bucket=atlas_parcellation_ontology_bucket,
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
    graph_of_all_ontologies, _ = all_ontology_graphs
    new_jsonld_context, errors = bmo.build_context_from_ontology(
        graph_of_all_ontologies, forge_context
    )
    new_jsonld_context.document["@context"].update(
        _get_ontology_annotation_lang_context()
    )
    return new_jsonld_context, errors


@pytest.fixture(scope="session")
def forge_endpoint(forge):
    return forge._store.endpoint


@pytest.fixture(scope="session")
def all_ontology_graphs(ontology_dir):
    ontology_files = glob.glob(ontology_dir)
    ontology_graphs_dict = {}
    try:
        ontology_graphs_dict, graph_of_all_ontologies = load_ontologies(ontology_dir)
        assert len(graph_of_all_ontologies) > 0
        assert len(ontology_files) > 0
        assert len(ontology_graphs_dict) == len(ontology_files)
        assert len(ontology_graphs_dict) == len(
            list(graph_of_all_ontologies.subjects(RDF.type, OWL.Ontology))
        )
        return graph_of_all_ontologies, ontology_graphs_dict
    except Exception as e:
        missing_ontologies = set(
            [filepath.split("/")[-1] for filepath in ontology_files]
        ) - set([filepath.split("/")[-1] for filepath in ontology_graphs_dict.keys()])

        pytest.fail(
            f"Failed to load all ontologies in {ontology_dir}. "
            f"Not loaded ontologies are: {missing_ontologies}: {e}"
        )


@pytest.fixture(scope="session")
def slim_ontology_list(slim_ontology_dir):
    _, all_ontology_graphs = load_ontologies(slim_ontology_dir)
    return list(all_ontology_graphs.subjects(RDF.type, OWL.Ontology))


@pytest.fixture(scope="session")
def framed_classes(
        data_jsonld_context,
        all_ontology_graph_merged_brain_region_atlas_hierarchy,
        atlas_release_id,
        atlas_release_version,
):
    new_jsonld_context, errors = data_jsonld_context
    assert len(errors) == 0
    ontology_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[0]
    class_ids, class_jsons, all_blank_node_triples, brain_region_new_classes = (
        bmo.frame_classes(
            ontology_graph,
            new_jsonld_context,
            new_jsonld_context.document,
            atlas_release_id,
            atlas_release_version,
        )
    )
    return class_ids, class_jsons, brain_region_new_classes


@pytest.fixture(scope="session")
def all_ontology_graph_merged_brain_region_atlas_hierarchy(
        all_ontology_graphs, ontology_dir, atlas_hierarchy_ontology_graph
):
    graph_of_all_ontologies, ontology_graphs_dict = all_ontology_graphs

    brain_region_graph = ontology_graphs_dict["./ontologies/bbp/brainregion.ttl"]

    triples_to_add, triples_to_remove = _merge_ontology(
        atlas_hierarchy_ontology_graph,
        brain_region_graph,
        graph_of_all_ontologies,
    )
    assert len(triples_to_remove) > 0
    assert len(triples_to_add) > 0
    return graph_of_all_ontologies, brain_region_graph


@pytest.fixture(scope="session")
def atlas_release_prop(atlas_release_id, atlas_release_version):
    return {
        "@id": atlas_release_id,
        "@type": "BrainAtlasRelease",
        "_rev": atlas_release_version,
    }


@pytest.fixture(scope="session")
def atlas_release_id(atlas_parcellation_ontology_resource):
    return atlas_parcellation_ontology_resource.atlasRelease.id


@pytest.fixture(scope="session")
def atlas_release_version(atlas_parcellation_ontology_resource):
    return atlas_parcellation_ontology_resource.atlasRelease._rev


@pytest.fixture(scope="session")
def atlas_parcellation_ontology_resource(atlas_parcellation_ontology, atlas_parcellation_ontology_version, forge_atlas):
    try:
        version = (
            int(atlas_parcellation_ontology_version)
            if atlas_parcellation_ontology_version is not None
            else None
        )
        atlas_parcellation_ontology_resource = forge_atlas.retrieve(
            atlas_parcellation_ontology, version=version
        )
        assert hasattr(atlas_parcellation_ontology_resource, "atlasRelease")
        assert hasattr(atlas_parcellation_ontology_resource.atlasRelease, "_rev")

        return atlas_parcellation_ontology_resource

    except Exception as e:
        pytest.fail(f"Failed to load {atlas_parcellation_ontology}: {e}")


@pytest.fixture(scope="session")
def atlas_hierarchy_ontology_graph(atlas_parcellation_ontology_resource, forge_atlas):
    try:
        atlas_hierarchy_jsonld_distribution = next(
            (distrib for distrib in atlas_parcellation_ontology_resource.distribution
             if distrib.encodingFormat == "application/ld+json"), None
        )

        assert atlas_hierarchy_jsonld_distribution, "Couldn't find json-ld distribution in atlas parcellation ontology resource"

        forge_atlas.download(
            atlas_hierarchy_jsonld_distribution,
            follow="contentUrl",
            path=".",
            overwrite=True,
        )
        atlas_hierarchy_ontology_graph = rdflib.Graph().parse(
            atlas_hierarchy_jsonld_distribution.name, format="json-ld"
        )
        assert len(atlas_hierarchy_ontology_graph) > 0

        return atlas_hierarchy_ontology_graph
    except Exception as e:
        pytest.fail(f"Failed to load atlas hierarchy ontology graph from atlas hierarchy resource: {e}")


@pytest.fixture(scope="session")
def atlas_hierarchy_ontology_graph_classes(atlas_hierarchy_ontology_graph):
    atlas_hierarchy_ontology_classes = list(
        atlas_hierarchy_ontology_graph.subjects(RDF.type, OWL.Class)
    )
    assert len(atlas_hierarchy_ontology_classes) > 0
    return atlas_hierarchy_ontology_classes


@pytest.fixture(scope="session")
def brain_region_ontologygraph_classes(
        atlas_hierarchy_ontology_graph_classes,
        all_ontology_graph_merged_brain_region_atlas_hierarchy,
):
    brain_region_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy[1]
    brain_region_layer_graph_classes = list(
        brain_region_graph.subjects(RDFS.subClassOf, NSG.BrainRegion)
    )
    brain_region_graph_classes = [
        cls
        for cls in brain_region_layer_graph_classes
        if (cls, RDFS.subClassOf * ZeroOrMore, BMO.BrainLayer) not in brain_region_graph
    ]
    assert len(brain_region_graph_classes) >= len(
        atlas_hierarchy_ontology_graph_classes
    )
    return brain_region_graph_classes


@pytest.fixture(scope="session")
def all_schema_graphs(transformed_schema_path, schema_dir, forge_schema, slim_ontology_list):

    recursive = True
    schema_filenames = glob.glob(schema_dir, recursive=recursive)

    # non_deprecated_schemas = [
    #     schema_filename for schema_filename in schema_filenames
    #     if not json.load(open(schema_filename, 'r')).get("owl:deprecated", False)
    # ]

    try:
        schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs = (
            load_schemas(
                schema_dir,
                transformed_schema_path,
                forge_schema,
                recursive,
                save_transformed_schema=False,
            )
        )
        assert len(all_schema_graphs) > 0
        assert len(schema_graphs_dict) == len(schema_id_to_filepath_dict)

        assert len(schema_filenames) > 0
        assert len(schema_graphs_dict) == len(schema_filenames)
        assert len(schema_graphs_dict) == len(
            list(all_schema_graphs.subjects(RDF.type, NXV.Schema))
        )
        all_imported_schemas = all_schema_graphs.objects(None, OWL.imports)
        # make sure it was not an ontology
        all_imported_schemas = {str(r) for r in all_imported_schemas if r not in slim_ontology_list}
        loaded_schema = set(schema_id_to_filepath_dict.keys())
        assert len(loaded_schema) >= len(set(all_imported_schemas))
        assert all_imported_schemas.issubset(
            loaded_schema
        ), f"Imported schemas are missing: {all_imported_schemas - loaded_schema}"
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
        missing_schemas = set(
            [filepath.split("/")[-1] for filepath in schema_filenames]
        ) - set([filepath.split("/")[-1] for filepath in schema_graphs_dict.keys()])
        pytest.fail(
            f"Failed to load all schemas in {schema_dir}. "
            f"Not loaded schemas are {missing_schemas}. {e}"
        )


@pytest.fixture(scope="session")
def updated_local_jsonld_context(all_ontology_graphs, all_schema_graphs):
    _, new_jsonld_context, _ = combine_jsonld_context(all_ontology_graphs[0],
                                                      all_schema_graphs[0],
                                                      True)
    return new_jsonld_context
