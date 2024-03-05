#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 12 14:03:34 2023

@author: ricardi
"""
import rdflib
from rdflib import RDFS

infile = 'datatypes.ttl'
outfile = 'redacted.ttl'
keep_prefixes = True  # True uses prefixes from infile, False lets rdflib handle those

g = rdflib.Graph().parse(infile)

def split_camelcase(s):
    chars = list(s) + ["a"]
    new = []
    for n, char in enumerate(chars):
        if char.isupper() and chars[n - 1] != " ": 
            if chars[n + 1].islower() or chars[n - 1].islower():
                new.append(" ")
        new.append(char)
    return ("").join(new[:-1]).strip()

l1 = []
for s, p, o  in g.triples((None, RDFS.label, None)):
    new_o = rdflib.term.Literal(split_camelcase(o.value), lang='en')
    g.set((s, p, new_o))

if keep_prefixes:
    import re
    pattern = r'@prefix[ \t]+(?P<key>[\w\d#-]+):[ \t]+<(?P<value>[\w\d:/\.#-]+)>'
    with open(infile, 'r') as f:
        while True:
            line = f.readline().strip() 
            m = re.match(pattern, line)
            print(line)
            if not m:
                break
            print('setting', m.group('key'), m.group('value'))
            g.bind(m.group('key'), rdflib.term.URIRef(m.group('value')), replace=True)
g.serialize(outfile)    
