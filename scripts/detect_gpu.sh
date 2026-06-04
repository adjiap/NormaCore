#!/usr/bin/env bash
# Detects availability of NVIDIA GPU
# Outputs: "gpu" or "cpu" to stdout.

if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
  echo "gpu"
else
  echo "cpu"
fi
