#!/bin/bash
set -e
cd $(dirname "$(readlink -f "$0")")
docker build -t myagentlab/openclaw:latest openclaw/
docker build -t myagentlab/hermes:latest hermes/
docker build -t myagentlab/lobechat:latest lobechat/
echo "All 3 images built successfully"
docker images | grep myagentlab
