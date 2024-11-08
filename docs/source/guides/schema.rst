Schemas
=======

What is a schema ?
------------------

In the BBP Knowledge Graph, a schema is a JSON structured object enabling users to define constraints that the the metadata of a given
dataset (e.g. Neuron Morphology, Circuit, ...) should conform to when creating or updating the metadata. Constraints in
a schema can check that a piece of metadata has the expected set of properties along with expected values and cardinality.

At BBP, schemas and ontologies can help answer the following questions:

* What are the data types of interest at BBP ?
* What are the expected metadata of a given data type ?

All BBP schemas can be viewed:

* visually using the `BMO schema doc <https://bmo-ontodocs.kcp.bbp.epfl.ch/entities-az.html>`__
* programmatically using forge: |Binder_Modeling|


What schema language and syntax to use ?
----------------------------------------
While many schema languages exist, the BBP Knowledge Graph uses at its core the `W3C Shapes Constraints Language (SHACL) <https://www.w3.org/TR/shacl/>`__ schema language.

How schemas relate to ontologies and data ?
-------------------------------------------

.. image:: ../assets/images/schemas-onto-data_relations.png


Syntax of a SHACL schema ?
--------------------------


A SHACL schema is a JSON object:

* with an identifier: value of the "@id" key
* with a type: value of the "@type" key
* with a label: value of the "label" key
* defining a set of constraints applicable to the metadata of a given data type: value of the "shapes" key (e.g. optional or mandatory properties the metadata should contain along with their expected type):

The BBP Knowledge Graph applies a one type one schema policy. But a schema can target many types.

The following table and JSON example detail the different high level schema JSON keys:

+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| Property    | Description                                                    | Expected value                                                                                                                      |
+=============+================================================================+=====================================================================================================================================+
| `@context`  | A JSON-LD context                                              | Always `https://incf.github.io/neuroshapes/contexts/schema.json`                                                                    |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| `@id`       | An https based URI identifying the schema.                     | Pattern: `https://neuroshapes.org/{dash or commons}/{data_type_lowercased}`, Example: https://neuroshapes.org/dash/neuronmorphology |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| `@type`     | The type of the schema.                                        | Always `Schema`                                                                                                                     |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| `label`     | A human readable label.                                        | A string                                                                                                                            |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| `imports`   | A set of schema identifiers to reuse in the current schema.    | An array of schema identifiers                                                                                                      |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+
| `shapes`    | A set of constraints defined in the schema.                    | An array of JSON objects                                                                                                            |
+-------------+----------------------------------------------------------------+-------------------------------------------------------------------------------------------------------------------------------------+

.. code-block:: json

    {
      "@context":"https://incf.github.io/neuroshapes/contexts/schema.json",
      "@id": "https://neuroshapes.org/dash/neuronmorphology",
      "@type": "Schema",
      "label":"A label",
      "imports":["https://neuroshapes.org/commons/minds"],
      "shapes": [{
            ...
        }]
    }

Syntax of a constraint in a schema ?
------------------------------------

Different constraints (also called shapes in SHACL) applicable to the metadata of a given data type can be defined. A constraint is a JSON object and is a value of the 'shapes' key of a schema :

* with an identifier: value of the "@id" key
* with a type: value of the "@type" key
* with a label: value of the "label" key
* defining a set of constraints:

 * targeting specific data types: value of the "targetClass" key.
 * enforcing that the metadata should have an identifier or not: value of the "nodeKind" key
 * enforcing that the schema should extend another schema: value of the 'node' key of the first item of the "and" array key.
 * enforcing the (mandatory or optional) properties the metadata should have along with the specific constraints (e.g. type, cardinality) that apply to them: value of the 'properties' key of the second item of the "and" array key.

The following table  and JSON example detail the different JSON keys for tthe value of :

+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Property                          | Description                                                                                                                                                                           | Expected value                                                                                                                                                                                                                                                     |
+===================================+=======================================================================================================================================================================================+====================================================================================================================================================================================================================================================================+
| `@id`                             | An https based URI identifying the shape.                                                                                                                                             | Pattern: {schema_uri}/shapes/{data_type}Shape, Example: https://neuroshapes.org/dash/neuronmorphology/shapes/NeuronMorphologyShape                                                                                                                                 |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `@type`                           | The type of the shape.                                                                                                                                                                | Always `NodeShape`                                                                                                                                                                                                                                                 |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `label`                           | A human readable text.                                                                                                                                                                | A string                                                                                                                                                                                                                                                           |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `targetClass`                     | The type of data this shape applies to                                                                                                                                                | A full URI such as https://neuroshapes.org/NeuronMorphology can be used or a short form (CURIE) nsg:NeuronMorphology. The `BMO schema doc <https://bmo-ontodocs.kcp.bbp.epfl.ch/entities-az.html>`__ can be used to search for the URI or CURIE of a given type.   |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `nodeKind`                        | Whether the metadata should have an identifier or not                                                                                                                                 | Always `sh:BlankNodeOrIRI`                                                                                                                                                                                                                                         |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and`                             | Reuse of a shape defined in an imported schema and extends it with  of local constraints.                                                                                             | An array of JSON objects                                                                                                                                                                                                                                           |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[0].node`                     | The identifier of a shape to reuse. The shape can be defined by an imported schema or locally.                                                                                        | An https based URI.                                                                                                                                                                                                                                                |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property`                 | Enforces the (mandatory or optional) properties the metadata should have along with the specific constraints (e.g. type, cardinality) that apply to them                              | An array of JSON objects with each item defining the constraints of a property                                                                                                                                                                                     |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].path`         | The property of the metadata to define constraints for                                                                                                                                | A full URI such as https://schema.org/name can be used or a short form schema:name                                                                                                                                                                                 |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].name`         | A human readable short name of the property                                                                                                                                           | A string                                                                                                                                                                                                                                                           |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].description`  | A human readable text describing the property of the metadata                                                                                                                         | A string                                                                                                                                                                                                                                                           |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].datatype`     | The expected primitive data type (e.g. string, integer, ...) of the value of this property. Using `datatype` means the value of the property is a typed literal.                      | One of the XML Schema Definition (XSD) data types (e.g. xsd:string, xsd:integer). See more `XSD data types <https://www.liquid-technologies.com/Reference/XmlStudio/XsdEditorNotation_BuiltInXsdTypes.html>`__                                                     |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].class`        | The expected non primitive type of the value of this property. `class` is exclusive to `datatype`.                                                                                    | A full URI such as http://www.w3.org/ns/prov#Entity can be used or a short form prov:Entity                                                                                                                                                                        |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].minCount`     | The minimum cardinality of the value of this property                                                                                                                                 | A positive integer or zero. Default to 0                                                                                                                                                                                                                           |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].maxCount`     | The maximum cardinality of the value of this property                                                                                                                                 | A positive integer or 0. Default to 0                                                                                                                                                                                                                              |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| `and[1].property[*].node`         | The identifier of a shape the value of this property should conform to. The shape can be defined by an imported schema or locally as another item in the shapes array of the schema.  | A positive integer or zero                                                                                                                                                                                                                                         |
+-----------------------------------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

The following JSON is an example of schema:
* targeting the type `ScholarlyArticle` (CURIE: `schema:ScholarlyArticle`, URI: `http://schema.org/ScholarlyArticle`)
* extending the Entity schema with specific properties and constraints

  * enforcing that a ScholarlyArticle should have at most one property schema:title whose value should be a string
  * enforcing that a ScholarlyArticle should have exactly one property schema:abstract whose value should be a string
  * enforcing that a ScholarlyArticle should have at least one property schema:publisher whose value should be of type schema:Organization and conform to the constraints defined in the shape https://neuroshapes.org/commons/organization/shapes/OrganizationShape

.. code-block:: json

    {
      "@context": "https://incf.github.io/neuroshapes/contexts/schema.json",
      "@id": "https://neuroshapes.org/dash/scholarlyarticle",
      "@type": "nxv:Schema",
      "imports": ["https://neuroshapes.org/commons/organization", "https://neuroshapes.org/commons/entity"],
      "shapes": [{
          "@id": "this:ScholarlyArticleShape",
          "@type": "sh:NodeShape",
          "label": "Scholarly article",
          "targetClass": "schema:ScholarlyArticle",
          "and": [{
              "node": "https://neuroshapes.org/commons/entity/shapes/EntityShape"
            },{
              "property": [{
                  "path": "schema:title",
                  "name": "Title",
                  "description": "The article title.",
                  "maxCount": 1,
                  "datatype": "xsd:string"
                },{
                  "path": "schema:abstract",
                  "name": "Abstract",
                  "description": "Article abstract.",
                  "minCount": 1,
                  "maxCount": 1,
                  "datatype": "xsd:string"
                },{
                  "path": "schema:publisher",
                  "name": "Publisher",
                  "description": "The Creative Work publisher.",
                  "minCount": 1,
                  "class": "schema:Organization",
                  "node": "https://neuroshapes.org/commons/organization/shapes/OrganizationShape",
                }]}]}]}


How to create a SHACL schema ?
------------------------------

Schemas are stored and managed in a directory within the `BMO pipeline repository <https://bbpgitlab.epfl.ch/dke/apps/brain-modeling-ontology/-/tree/develop/shapes>`__.
This directory is structured as follows:

* the subdirectory `commons` is a library of reusable schemas. A reusable schema should not target specific types, i.e should not have a value for the targetClasss property.
* the subdirectory `datashapes.core` is where schemas targeting specific BBP data types are defined as files with the following naming pattern: `data_type_lowercased.json` (e.g. scholarlyarticle.json for the type ScholarlyArticle).



The following illustration shows the pipeline for creating a schema in gitlab.

.. image:: ../assets/images/bmo-schema-pipeline.png

How to validate metadata against a schema ?
-------------------------------------------

|Binder_Modeling| to explore more about how to use schemas in forge for validation.


.. |Binder_Modeling| image:: https://mybinder.org/badge_logo.svg
    :alt: Binder_Modeling
    :target: https://mybinder.org/v2/gh/BlueBrain/nexus-forge/master?filepath=examples%2Fnotebooks%2Fgetting-started%2F11%20-%20Modeling.ipynb
