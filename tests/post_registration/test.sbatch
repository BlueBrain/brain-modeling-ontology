#!/bin/bash -l
#SBATCH -t 24:00:00
#SBATCH -p prod
#SBATCH -C "cpu"
#SBATCH --account=proj116
#SBATCH --mem=0

module load archive/2021-12
module load python/3.8.3
source venv/bin/activate
pip install --upgrade pip
pip install .[dev]

pytest tests/post_registration  --atlas_parcellation_ontology_version 163 --token $1 --no-randomisation

