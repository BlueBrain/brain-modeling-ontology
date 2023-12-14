from typing import Dict
import pytest
from rdflib import RDFS, RDF, OWL
from rdflib.paths import OneOrMore

from bmo.utils import BMO, NSG, SKOS


@pytest.mark.parametrize("object_, predicate, resolver_target", [
    pytest.param(
        object_, predicate, resolver_target, id=object_.toPython())
        for object_, predicate, resolver_target in [
            (NSG.BrainRegion, RDFS.subClassOf * OneOrMore, "BrainRegion"),
            (BMO.BrainCellType, RDFS.subClassOf * OneOrMore, "CellType"),
            (NSG.Species, RDFS.subClassOf * OneOrMore, "Species"),
            (OWL.Class, RDF.type, "terms")
        ]
])
def test_classes_can_be_resolved(
        forge, all_ontology_graphs, object_, predicate, resolver_target
):
    """
    Check if the values of `label`, `altLabel`, `prefLabel` and `notation` of each class
    in the ontology can be resolved using forge
    """

    all_ontology_graphs = all_ontology_graphs[0]

    class_list = list(all_ontology_graphs.subjects(predicate, object_))

    hierarchy_class_info: Dict[str, Dict] = dict(
        (
            ontology_class.toPython(),
            {
                "label": list(all_ontology_graphs.objects(ontology_class, RDFS.label)),
                "altLabel": list(all_ontology_graphs.objects(ontology_class, SKOS.altLabel)),
                "prefLabel": list(all_ontology_graphs.objects(ontology_class, SKOS.prefLabel)),
                "notation": list(all_ontology_graphs.objects(ontology_class, SKOS.notation))
            }
        )
        for ontology_class in class_list
    )

    errors = []

    for ontology_class, ontology_info in hierarchy_class_info.items():
        for field_name, all_values in ontology_info.items():
            for value in all_values:

                resolved = forge.resolve(
                    value.toPython(), scope='ontology',
                    target=str(resolver_target), strategy='EXACT_MATCH'
                )

                if not resolved:

                    errors.append(
                        f'Class {ontology_class} not resolved by resolver {resolver_target}'
                        f' using {field_name}: {value}'
                    )

    assert len(errors) == 0, f"{errors}"
