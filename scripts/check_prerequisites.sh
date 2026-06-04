#!/usr/bin/env bash
# scripts/check_prerequisites.sh
# Pre-flight checks before running the compose stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# shellcheck source=lib/checks.sh
source "$SCRIPT_DIR/lib/checks.sh"

ERRORS=0

log_ok()    { echo "✅ $1"; }
log_warn()  { echo "⚠️  $1"; }
log_error() { echo "❌ $1"; ERRORS=$((ERRORS + 1)); }

echo "=== Pre-flight Checks ==="
echo ""

# ------------------------------------------------------------------------------
# 1. Container runtime
# ------------------------------------------------------------------------------
if check_runtime; then
    log_ok "Container runtime: $RUNTIME"
else
    log_error "No container runtime found. Install Docker or Podman."
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Daemon is running
# ------------------------------------------------------------------------------
if check_daemon; then
    log_ok "$RUNTIME daemon is running"
else
    log_error "$RUNTIME daemon is not running. Start it before proceeding."
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. Compose plugin
# ------------------------------------------------------------------------------
if check_compose; then
    log_ok "Compose plugin: $COMPOSE_CMD"
else
    log_error "No compose plugin found for $RUNTIME. Install the compose plugin."
    exit 1
fi

# ------------------------------------------------------------------------------
# 4. .env file
# ------------------------------------------------------------------------------
case $(check_env_file "$REPO_ROOT"; echo $?) in
    0) log_ok ".env file exists" ;;
    2)
        log_warn ".env not found — copying from .env.example"
        cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
        log_ok "Copied .env.example → .env. Review and edit before proceeding."
        ;;
    1)
        log_error ".env and .env.example both missing. Cannot proceed."
        ;;
esac

# ------------------------------------------------------------------------------
# 5. GPU checks
# ------------------------------------------------------------------------------
if check_nvidia_smi; then
    log_ok "nvidia-smi found and functional"

    if [ "$RUNTIME" = "podman" ]; then
        if check_nvidia_devices; then
            log_ok "NVIDIA device nodes present"
        else
            log_warn "One or more NVIDIA device nodes missing — GPU passthrough may fail"
        fi
    fi

    if [ "$RUNTIME" = "docker" ]; then
        if check_nvidia_toolkit; then
            log_ok "NVIDIA container runtime configured for Docker"
        else
            log_warn "NVIDIA container runtime not detected. Run: nvidia-ctk runtime configure --runtime=docker"
        fi
    fi
else
    log_warn "nvidia-smi not found or not functional — will use CPU profile"
fi

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo "❌ $ERRORS error(s) found. Resolve the above before running compose."
    exit 1
else
    echo "✅ All checks passed."
fi
