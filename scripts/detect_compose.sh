#!/usr/bin/env bash
# Detects available container compose tool (podman compose > docker compose)
# Outputs: "podman compose" or "docker compose" to stdout.
# Exits with code 1 if no compose tool is found.

set -euo pipefail

if command -v podman &> /dev/null && command -v podman-compose &> /dev/null 2>&1; then
  echo "podman-compose"
elif command -v podman &> /dev/null && podman compose version &> /dev/null 2>&1; then
  echo "podman compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null 2>&1; then
  echo "docker compose"
else
  echo "ERROR: No compose tool found. Install podman-compose, podman with compose plugin, or docker compose" >&2
  exit 1
fi
