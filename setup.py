import os
from setuptools import setup, find_packages

HERE = os.path.abspath(os.path.dirname(__file__))


# Get the long description from the README file.
with open(os.path.join(HERE, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="bmo",
    author="Blue Brain Project, EPFL",
    use_scm_version={
        "relative_to": __file__,
        "write_to": "bmo/version.py",
        "write_to_template": "__version__ = '{version}'\n",
    },
    description="Tools for processing Brain Modeling Ontology .",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    keywords="ontology knowledge graph data science",
    packages=find_packages(),
    python_requires=">=3.8",
    setup_requires=[
        "setuptools_scm",
    ],
    install_requires=[
        "rdflib==7.0.0",
        "pyld==2.0.3",
        "numpy==1.24.4",
        "nexusforge@git+https://github.com/BlueBrain/nexus-forge"
    ],
    extras_require={
        "dev": [
            "tox==4.11.3",
            "pytest==7.4.2",
            "pytest-bdd==6.1.1",
            "pytest-cov==2.10.1",
            "pytest-mock==3.3.1",
            "codecov==2.1.13",
            "flake8==6.1.0"
        ],
        "docs": [
            "sphinx==7.1.2",
            "sphinx-bluebrain-theme==0.4.2"
        ]
    },
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "Programming Language :: Python :: 3 :: Only",
        "Natural Language :: English",
    ]
)
