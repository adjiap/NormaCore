#!/usr/bin/env bash
# scripts/lib/checks.sh
# Shared check functions sourced by check_prerequisites.sh and install-host-deps.sh.
# Each function sets relevant variables and returns 0 (pass) or 1 (fail).
#
# Variables set by these functions:
#   RUNTIME       — "docker" or "podman"
#   COMPOSE_CMD   — "docker compose" or "podman compose"
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib/checks.sh"

# ------------------------------------------------------------------------------
# Check: container runtime is installed
# Sets: $RUNTIME
# ------------------------------------------------------------------------------
check_runtime() {
    if command -v podman &>/dev/null; then
        RUNTIME="podman"
        return 0
    elif command -v docker &>/dev/null; then
        RUNTIME="docker"
        return 0
    else
        RUNTIME=""
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check: container runtime daemon is running
# Requires: $RUNTIME to be set (run check_runtime first)
# ------------------------------------------------------------------------------
check_daemon() {
    if [ -z "${RUNTIME:-}" ]; then
        return 1
    fi

    if $RUNTIME info &>/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check: compose plugin is available
# Sets: $COMPOSE_CMD
# Requires: $RUNTIME to be set (run check_runtime first)
# ------------------------------------------------------------------------------
check_compose() {
    if [ -z "${RUNTIME:-}" ]; then
        COMPOSE_CMD=""
        return 1
    fi

    # For Podman: also check for standalone podman-compose in the invoking user's PATH
    if [ "$RUNTIME" = "podman" ]; then
        local user_home
        user_home=$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)
        local user_bin="$user_home/.local/bin/podman-compose"

        if command -v podman-compose &>/dev/null; then
            COMPOSE_CMD="podman-compose"
            return 0
        elif [ -x "$user_bin" ]; then
            COMPOSE_CMD="$user_bin"
            return 0
        fi
    fi

    if $RUNTIME compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="$RUNTIME compose"
        return 0
    fi

    COMPOSE_CMD=""
    return 1
}

# ------------------------------------------------------------------------------
# Check: .env file exists
# Param: $1 — path to the setup directory containing .env and .env.example
# ------------------------------------------------------------------------------
check_env_file() {
    local setup_dir="${1:-}"
    local env_file="$setup_dir/.env"
    local env_example="$setup_dir/.env.example"

    if [ -f "$env_file" ]; then
        return 0
    elif [ -f "$env_example" ]; then
        # Copyable but not yet copied — caller decides whether to copy
        return 2
    else
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check: nvidia-smi is present and functional
# ------------------------------------------------------------------------------
check_nvidia_smi() {
    if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check: NVIDIA device nodes exist (required for Podman GPU passthrough)
# Returns 0 only if ALL required device nodes are present
# ------------------------------------------------------------------------------
check_nvidia_devices() {
    local required_devices=(
        /dev/nvidia0
        /dev/nvidiactl
        /dev/nvidia-uvm
        /dev/nvidia-modeset
    )
    local missing=0

    for dev in "${required_devices[@]}"; do
        if [ ! -e "$dev" ]; then
            missing=$((missing + 1))
        fi
    done

    if [ "$missing" -eq 0 ]; then
        return 0
    else
        return 1
    fi
}

# ------------------------------------------------------------------------------
# Check: NVIDIA container runtime is configured for Docker
# ------------------------------------------------------------------------------
check_nvidia_toolkit() {
    if docker info 2>/dev/null | grep -q "nvidia"; then
        return 0
    else
        return 1
    fi
}
