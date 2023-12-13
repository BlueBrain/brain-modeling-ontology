import argparse

def define_arguments():
    """
    Defines the arguments of the Python script

    :return: the argument parser
    :rtype: ArgumentParser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--environment',
        choices=["production", "staging"],
        help='In which Nexus environment should the script run?',
        required=True
    )
    parser.add_argument(
        "--token", help="The nexus token", type=str, required=True
    )
    parser.add_argument(
        "--tag", help="The tag of the ontology. Defaults to None",
        default=None, type=str
    )
    parser.add_argument(
        "--no_data_update", help="Whether to update data in Nexus", default=False, type=bool
    )

    parser.add_argument(
        "--bucket", help="The Nexus org/project in which to push the ontologies and the schemas.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--ontology_dir", help="The path to load ontologies from.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--schema_dir", help="The path to load schemas from.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--transformed_schema_path",
        help="The path to write and load schemas transformed for use by ontodocs.",
        default="./ontologies/bbp/shapes_jsonld_expanded", type=str
    )

    parser.add_argument(
        "--atlas_parcellation_ontology", help="The atlas parcellation ontology.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--atlas_parcellation_ontology_version", help="The atlas parcellation ontology version.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--atlas_parcellation_ontology_bucket", help="The atlas parcellation ontology bucket.",
        default=None, type=str, required=True
    )

    parser.add_argument(
        "--exclude_deprecated_from_context",
        help="Whether deprecated schemas and ontology elements should be excluded from the jsonld "
        "context or not", default=False, type=bool
    )

    return parser
