#!/bin/bash

echo "Updating files..."
sudo git pull
sudo git submodule init
sudo git submodule update --recursive --remote
