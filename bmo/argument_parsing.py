import argparse
from typing import Union
from _pytest.config.argparsing import Parser


def define_arguments(parser: Union[argparse.ArgumentParser, Parser]):
    """
    Defines the arguments of the Python script

    :return: the argument parser
    :rtype: ArgumentParser
    """

    add_arg = parser.addoption if isinstance(parser, Parser) else parser.add_argument

    add_arg(
        '--environment',
        choices=["production", "staging"],
        help='In which Nexus environment should the script run?',
        required=True
    )
    add_arg(
        "--token", help="The nexus token", type=str, required=True
    )
    add_arg(
        "--tag", help="The tag of the ontology. Defaults to None",
        default=None, type=str
    )
    add_arg(
        "--no_data_update", help="Whether to update data in Nexus", default=False, type=bool
    )

    add_arg(
        "--bucket", help="The Nexus org/project in which to push the ontologies and the schemas.",
        default='neurosciencegraph/datamodels', type=str
    )

    add_arg(
        "--ontology_dir", help="The path to load ontologies from.",
        default='./ontologies/bbp/*.ttl', type=str
    )

    add_arg(
        "--slim_ontology_dir", help="The path to load slim ontologies from.",
        default='./ontologies/bbp_slim/*.ttl', type=str
    )

    add_arg(
        "--schema_dir", help="The path to load schemas from.",
        default='./shapes/**/*.json', type=str
    )

    add_arg(
        "--transformed_schema_path",
        help="The path to write and load schemas transformed for use by ontodocs.",
        default="./ontologies/bbp/shapes_jsonld_expanded", type=str
    )

    add_arg(
        "--atlas_parcellation_ontology", help="The atlas parcellation ontology.",
        default=None, type=str, required=True
    )

    add_arg(
        "--atlas_parcellation_ontology_version", help="The atlas parcellation ontology version.",
        default=None, type=str, required=True
    )

    add_arg(
        "--atlas_parcellation_ontology_bucket", help="The atlas parcellation ontology bucket.",
        default="bbp/atlas", type=str
    )

    add_arg(
        "--exclude_deprecated_from_context",
        help="Whether deprecated schemas and ontology elements should be excluded from the jsonld "
        "context or not", default=False, type=bool
    )

    return parser
