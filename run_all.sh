#!/bin/bash


# Run all the scripts in the current directory
## check if in venv

source ./env/bin/activate
python dog_shelter_energy.py

python visualise_simulation_results.py