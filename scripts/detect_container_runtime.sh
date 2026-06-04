#!/usr/bin/env bash
# scripts/detect_container_runtime.sh
# Detects available container runtime and outputs the binary name.
# Podman is preferred over Docker if both are available.
# Outputs: "podman" or "docker" to stdout.
# Exits with code 1 if no container runtime is found.

set -euo pipefail

if command -v podman &> /dev/null; then
  echo "podman"
elif command -v docker &> /dev/null; then
  echo "docker"
else
  echo "ERROR: No container runtime found. Install podman or docker." >&2
  exit 1
fi
