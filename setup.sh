#!/bin/bash
sudo apt install python3.11-venv
python3 -m venv myenv
source myenv/bin/activate
pip3 install -r requirements.txt 
deactivate
