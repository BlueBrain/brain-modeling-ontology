"""Utils for pushing ontologies into a Neo4j DB."""
import re
from neo4j import GraphDatabase

from bluegraph import PandasPGFrame
from bluegraph.backends.neo4j import pgframe_to_neo4j


LABEL_MAPPING = {
    "Biological Brain Component": "BRAIN_COMPONENT",
    "Brain Component Type": "PHENOTYPE",
    "Brain Component Feature": "BIOLOGICAL_FEATURE",
    "Workflow": "WORKFLOW",
    "Model Brain Component": "MODEL",
    "Model Brain Activity": "MODEL",
    "Electrical Stimulus": "STIMULUS",
    "Model Brain Parameter": "PARAMETER",
    "Dataset": "DATASET",
    "Molecule": "MOLECULE"
}


def replace_uris(x):
    return {
        el
        if not re.match(r"(http:\/\/.*)#(.*)", el)
        else re.match(r"(http:\/\/.*)#(.*)", el).groups()[1]
        for el in x
    }


def execute(driver, query):
    """Execute Cypher query."""
    session = driver.session()
    response = session.run(query)
    result = response.data()
    session.close()
    return result


def clean_db(driver):
    """Clean the Neo4j DB."""
    query = "MATCH (n) DETACH DELETE n"
    execute(driver, query)


def label_top_level(driver):
    """Assign top level labels."""
    execute(driver, "MATCH (n)-[:IS_SUBCLASS_OF|IS_INSTANCE_OF*..]->(m {id: 'Entity'}) SET n:ENTITY SET m:ENTITY")
    execute(driver, "MATCH (n)-[:IS_SUBCLASS_OF|IS_INSTANCE_OF*..]->(m {id: 'Activity'}) SET n:ACTIVITY SET m:ACTIVITY")
    execute(driver, "MATCH (n)-[:IS_SUBCLASS_OF|IS_INSTANCE_OF*..]->(m {id: 'Brain Modeling Agent'}) SET n:AGENT SET m:AGENT")


def label_entities(driver, mapping=LABEL_MAPPING):
    """Label entities to distinguish between different classes."""
    for k, v in LABEL_MAPPING.items():
        execute(
            driver,
            "MATCH (n)-[:IS_SUBCLASS_OF|IS_INSTANCE_OF*..]->(m {{id: '{}'}}) SET n:{} SET m:{}".format(
                k, v, v))


def ontology_to_neo4j(uri, username, password, path_to_ontology=None,
                      rdf_graph=None, format=None, node_types_as_labels=False):
    """Export local ontology into Neo4j."""
    driver = GraphDatabase.driver(
        uri, auth=(username, password))
    frame = PandasPGFrame.from_ontology(
        filepath=path_to_ontology, rdf_graph=rdf_graph,
        format=format, remove_prop_uris=True)

    # Check no uri-like edge types were produced
    frame._edges["@type"] = frame._edges["@type"].apply(replace_uris)

    clean_db(driver)
    pgframe_to_neo4j(
        frame, driver=driver, node_label="ONTOLOGY_CLASS",
        node_types_as_labels=node_types_as_labels,
        edge_types_as_labels=True)
    label_top_level(driver)
    label_entities(driver)
