import glob

import pytest
import rdflib
from kgforge.core import Resource
from rdflib import RDFS, SKOS, RDF, OWL
import bmo.ontologies as bmo
from bmo.argument_parsing import define_arguments
from bmo.utils import BMO, MBA, NXV, SCHEMAORG, _get_ontology_annotation_lang_context
from bmo.loading import load_ontologies, load_schemas
from register_ontologies import _merge_ontology, _initialize_forge_objects


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
            "Environment argument must be either \"staging\" or \"production\" "
        )

    return _initialize_forge_objects(
        endpoint=endpoint, input_bucket=bucket, token=token,
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
    new_jsonld_context.document["@context"].update(_get_ontology_annotation_lang_context())
    return new_jsonld_context, errors


@pytest.fixture(scope="session")
def all_ontology_graphs(ontology_dir):
    ontology_files = glob.glob(ontology_dir)
    ontology_graphs_dict = {}
    try:
        ontology_graphs_dict, all_ontology_graphs = load_ontologies(ontology_dir)
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
def framed_classes(
        data_jsonld_context, all_ontology_graph_merged_brain_region_atlas_hierarchy,
        atlas_release_id, atlas_release_version
):
    new_jsonld_context, errors = data_jsonld_context[0], data_jsonld_context[1]
    assert len(errors) == 0
    ontology_graph = all_ontology_graph_merged_brain_region_atlas_hierarchy

    class_ids, class_jsons, all_blank_node_triples, brain_region_new_classes = bmo.frame_classes(
        ontology_graph, new_jsonld_context, new_jsonld_context.document,
        atlas_release_id, atlas_release_version
    )
    return (
        class_ids, class_jsons, brain_region_new_classes
    )


@pytest.fixture(scope="session")
def all_ontology_graph_merged_brain_region_atlas_hierarchy(all_ontology_graphs, atlas_hierarchy_ontology_graph):
    ontology_graph = all_ontology_graphs[0]
    ontology_graphs_dict = all_ontology_graphs[1]

    brain_region_graph = ontology_graphs_dict["./ontologies/bbp/brainregion.ttl"]

    atlas_ontology_graph = atlas_hierarchy_ontology_graph[0]

    what_property_to_merge = [
        SCHEMAORG.hasPart,
        SCHEMAORG.isPartOf, RDFS.label, SKOS.prefLabel, SKOS.notation, SKOS.altLabel,
        MBA.atlas_id, MBA.color_hex_triplet, MBA.graph_order, MBA.hemisphere_id,
        MBA.st_level, SCHEMAORG.identifier, BMO.representedInAnnotation,
        BMO.regionVolumeRatioToWholeBrain, BMO.regionVolume
    ]
    triples_to_add, triples_to_remove = _merge_ontology(
        atlas_ontology_graph, brain_region_graph, ontology_graph, what_property_to_merge
    )
    assert len(triples_to_remove) > 0
    assert len(triples_to_add) > 0
    return ontology_graph


@pytest.fixture(scope="session")
def atlas_release_prop(atlas_release_id, atlas_release_version):
    return {
            "@id": atlas_release_id,
            "@type": "BrainAtlasRelease",
            "_rev": atlas_release_version
        }


@pytest.fixture(scope="session")
def atlas_release_id(atlas_hierarchy_ontology_graph):
    return atlas_hierarchy_ontology_graph[1].atlasRelease.id


@pytest.fixture(scope="session")
def atlas_release_version(atlas_hierarchy_ontology_graph):
    return atlas_hierarchy_ontology_graph[1].atlasRelease._rev


@pytest.fixture(scope="session")
def atlas_hierarchy_ontology_graph(atlas_parcellation_ontology, atlas_parcellation_ontology_version,
                                   forge_atlas):
    try:
        version = int(atlas_parcellation_ontology_version) \
            if atlas_parcellation_ontology_version is not None \
            else None
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
    recursive = True
    schema_filenames = glob.glob(schema_dir, recursive=recursive)

    # non_deprecated_schemas = [
    #     schema_filename for schema_filename in schema_filenames
    #     if not json.load(open(schema_filename, 'r')).get("owl:deprecated", False)
    # ]

    try:
        schema_graphs_dict, schema_id_to_filepath_dict, all_schema_graphs = load_schemas(
            schema_dir, transformed_schema_path, forge_schema, recursive,
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
