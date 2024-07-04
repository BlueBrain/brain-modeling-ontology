import json
import os


def test_registered_ontology_files(forge, framed_ontologies):
    for ontology_uri in framed_ontologies:
        registered_ontology = forge.retrieve(ontology_uri)

        # Check files are not empty
        forge.download(registered_ontology, path='./tmp_ontology/')
        for d in registered_ontology.distribution:
            fpath = f"./tmp_ontology/{d.name}"
            assert os.stat(fpath).st_size != 0, \
                f"Empty ontology file {fpath} from {ontology_uri}"

            # check if defines property exist inside the json
            if fpath.endswith('.json') and 'synthetic_texts' not in fpath and 'wiki_texts' not in fpath:
                with open(fpath, 'r') as fin:
                    registered_json = json.load(fin)
                assert 'defines' in registered_json, \
                    f"Registered ontology {fpath} doesn't contain the `defines` property"
