#!/bin/bash
# shellcheck source=/dev/null
source ~/Environments/local-db-ui/bin/activate
cd ~/Repos/local-db-ui
export PYTHONPATH=/home/franks/Repos/local-db:$PYTHONPATH
python app.py
