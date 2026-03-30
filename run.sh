#!/bin/bash
# shellcheck source=/dev/null
source ~/Environments/local-db-ui/bin/activate
export PYTHONPATH=/home/franks/Repos/local-db:$PYTHONPATH
cd ~/Repos/local-db
python /home/franks/Repos/local-db-ui/app.py
