from typing import Dict
import json
import random
import os
import pytest
from kgforge.core.commons.strategies import ResolvingStrategy
from rdflib import RDFS, RDF, OWL, URIRef, Literal, XSD
from rdflib.paths import OneOrMore

from bmo.utils import BMO, NSG, SKOS
from register_ontologies import JSONLD_DATA_CONTEXT_IRI


@pytest.mark.parametrize("object_, predicate, resolver_target", [
    pytest.param(
        object_, predicate, resolver_target, id=object_.toPython()
    )
    for object_, predicate, resolver_target in [
        (NSG.BrainRegion, RDFS.subClassOf * OneOrMore, "BrainRegion"),
        (BMO.BrainCellType, RDFS.subClassOf * OneOrMore, "CellType"),
        (NSG.Species, RDFS.subClassOf * OneOrMore, "Species"),
        (OWL.Class, RDF.type, "terms")
    ]
])
def test_classes_can_be_resolved(
        forge, all_ontology_graph_merged_brain_region_atlas_hierarchy, object_: URIRef,
        predicate, resolver_target: str, randomize
):
    """
    Check if the values of `label`, `altLabel`, `prefLabel` and `notation` of each class
    in the ontology can be resolved using forge
    """

    all_ontology_graphs_merged = all_ontology_graph_merged_brain_region_atlas_hierarchy[0]

    class_list = list(all_ontology_graphs_merged.subjects(predicate, object_))

    sample_count = 20
    if len(class_list) > sample_count and randomize:
        class_list = random.sample(class_list, sample_count)

    hierarchy_class_info: Dict[str, Dict] = dict(
        (
            ontology_class.toPython(),
            {
                "label": list(all_ontology_graphs_merged.objects(ontology_class, RDFS.label)),
                "altLabel": list(all_ontology_graphs_merged.objects(ontology_class, SKOS.altLabel)),
                "prefLabel": list(all_ontology_graphs_merged.objects(ontology_class, SKOS.prefLabel)),
                "notation": list(all_ontology_graphs_merged.objects(ontology_class, SKOS.notation))
            }
        )
        for ontology_class in class_list
    )

    errors = []
    nb_items = hierarchy_class_info.items()

    for i, (ontology_class, ontology_info) in enumerate(hierarchy_class_info.items()):

        t = list(all_ontology_graphs_merged.objects(URIRef(ontology_class), OWL.deprecated))
        deprecated = t[0] == Literal('true', datatype=XSD.boolean) if len(t) > 0 else False
        if deprecated:
            continue

        if i % 50 == 0:
            print(f"{i}/{nb_items}")

        for field_name, all_values in ontology_info.items():
            for value in all_values:

                try:
                    resolved = forge.resolve(
                        value.toPython(), scope='ontology',
                        target=str(resolver_target), strategy=ResolvingStrategy.EXACT_MATCH
                    )

                    if not resolved:
                        raise Exception("Returns nothing")

                except Exception as e:
                    errors.append(
                        f'Class {ontology_class} not resolved by resolver {resolver_target}'
                        f' using {field_name}: {value}: {e}'
                    )

    err_output_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), "errors")
    os.makedirs(err_output_directory, exist_ok=True)

    with open(
            os.path.join(err_output_directory, f"errors_{object_.toPython().split('/')[-1]}.json"),
            "w", encoding='utf-8'
    ) as f:

        f.write(json.dumps(errors, indent=4))

    assert len(errors) == 0, f"{errors}"


def test_registered_classes_local_classes_diff(framed_classes, forge):
    _, class_jsons, _ = framed_classes

    for class_json in class_jsons:
        class_json["@context"] = JSONLD_DATA_CONTEXT_IRI

    local_resources = [forge.from_json(el) for el in class_jsons]

    local_ids = set(
        el.get_identifier() for el in local_resources
        if not el.__dict__.get("deprecated", False)
    )

    q = "SELECT ?id WHERE {GRAPH ?g { ?id a Class ; _deprecated false }}"
    registered_ids = set(el.id for el in forge.sparql(q, limit=None))

    local_not_registered = local_ids.difference(registered_ids)
    assert len(local_not_registered) == 0, \
        f"The following classes were found but were not registered {local_not_registered}"

    registered_not_local = registered_ids.difference(local_ids)
    assert len(registered_not_local) == 0, \
        f"The following classes were registered but were not found locally {registered_not_local}"
