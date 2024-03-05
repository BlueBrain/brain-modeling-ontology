#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  1 11:12:08 2024

@author: ricardi

This script replaces any \" with \' to avoid issues with forge processing the triples
"""
import argparse
from bmo.argument_parsing import define_arguments
import glob
import os
import re

# defines and receives script arguments
parser = define_arguments(argparse.ArgumentParser())
received_args, leftovers = parser.parse_known_args()
ontology_dir = received_args.ontology_dir

    
cwd = os.getcwd()
ontofiles = glob.iglob(ontology_dir, recursive=True)
p = re.compile(r'\\"')
for ontofile in ontofiles:
    with open(ontofile, 'r') as f:
        text = f.read()
    match = re.search(p, text)
    if match:
        print(ontofile)
        text = re.sub(p, r"\\'", text)
        with open(ontofile, 'w') as f:
            f.write(text)
