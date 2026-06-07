#!/bin/bash
# ========================================================
#  Oracle Cloud ARM VM Setup for Card Scanner
#  Run this ON the VM after SSH'ing in
# ========================================================
set -e

echo "=== Updating system ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== Installing Docker ==="
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
rm get-docker.sh

echo "=== Cloning repo ==="
git clone https://github.com/Rucha1811/cosmos.git
cd cosmos

echo "=== Building Docker image ==="
# Use the root Dockerfile (works with HF too)
docker build -t card-scanner .

echo "=== Running container ==="
# Port 5050 exposed, restart on failure, run in background
docker run -d \
  --name card-scanner \
  --restart unless-stopped \
  -p 5050:7860 \
  card-scanner

echo ""
echo "=== Done! ==="
echo "Your app is running at: http://$(curl -s ifconfig.me):5050"
echo "Check status: docker ps"
echo "View logs: docker logs card-scanner -f"
