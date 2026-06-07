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
docker build -t card-scanner -f backend/Dockerfile .

echo "=== Running container ==="
docker run -d \
  --name card-scanner \
  --restart unless-stopped \
  -p 5050:5050 \
  card-scanner

echo ""
echo "=== Done! ==="
echo "App running at: http://$(curl -s ifconfig.me):5050"
echo "Check: docker ps"
echo "Logs: docker logs card-scanner -f"
