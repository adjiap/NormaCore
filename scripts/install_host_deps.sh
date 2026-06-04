#!/usr/bin/env bash
# scripts/install-host-deps.sh
# One-time host provisioning script for Linux servers.
# Sources lib/checks.sh to detect what is already installed and only
# installs what is missing.
#
# Supported distros:
#   - RHEL-based: Rocky Linux, AlmaLinux, CentOS Stream, RHEL
#   - Debian-based: Ubuntu, Debian
#
# Usage:
#   sudo bash scripts/install-host-deps.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# shellcheck source=lib/checks.sh
source "$SCRIPT_DIR/lib/checks.sh"

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_ok()    { echo -e "${GREEN}✅ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }
log_info()  { echo -e "${CYAN}➜  $1${NC}"; }

confirm() {
    local prompt="$1"
    read -rp "$prompt [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}

require_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run as root. Use: sudo bash $0"
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Detect distro family
# ------------------------------------------------------------------------------
detect_distro() {
    if command -v dnf &>/dev/null; then
        DISTRO_FAMILY="rhel"
        PKG_MANAGER="dnf"
        log_ok "Detected RHEL-based distro ($(cat /etc/redhat-release 2>/dev/null || echo 'unknown'))"
    elif command -v apt &>/dev/null; then
        DISTRO_FAMILY="debian"
        PKG_MANAGER="apt"
        log_ok "Detected Debian-based distro ($(lsb_release -ds 2>/dev/null || echo 'unknown'))"
    else
        log_error "Unsupported distro. Only RHEL-based and Debian-based distros are supported."
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# Ask runtime preference
# ------------------------------------------------------------------------------
ask_runtime() {
    echo ""
    echo "Which container runtime would you like to install?"
    echo "  1) Podman"
    echo "  2) Docker"
    echo ""
    read -rp "Enter choice [1/2] (default: 1): " choice
    choice="${choice:-1}"

    case "$choice" in
        1) PREFERRED_RUNTIME="podman" ;;
        2) PREFERRED_RUNTIME="docker" ;;
        *)
            log_warn "Invalid choice, defaulting to Podman"
            PREFERRED_RUNTIME="podman"
            ;;
    esac
    log_info "Selected runtime: $PREFERRED_RUNTIME"
}

# ------------------------------------------------------------------------------
# Install Podman
# ------------------------------------------------------------------------------
install_podman() {
    log_info "Installing Podman..."
    case "$DISTRO_FAMILY" in
        rhel)
            dnf install -y podman podman-compose
            ;;
        debian)
            apt update -y
            apt install -y podman
            if ! command -v podman-compose &>/dev/null; then
                apt install -y python3-pip
                pip3 install podman-compose
            fi
            ;;
    esac
    log_ok "Podman installed: $(podman --version)"
}

# ------------------------------------------------------------------------------
# Install Docker
# ------------------------------------------------------------------------------
install_docker() {
    log_info "Installing Docker..."
    case "$DISTRO_FAMILY" in
        rhel)
            dnf remove -y docker docker-client docker-client-latest \
                docker-common docker-latest docker-latest-logrotate \
                docker-logrotate docker-engine 2>/dev/null || true
            dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            dnf install -y docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        debian)
            apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
            apt update -y
            apt install -y ca-certificates curl gnupg lsb-release
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
                | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
                | tee /etc/apt/sources.list.d/docker.list > /dev/null
            apt update -y
            apt install -y docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
    esac
    systemctl enable --now docker
    log_ok "Docker installed: $(docker --version)"
}

# ------------------------------------------------------------------------------
# Add user to runtime group
# ------------------------------------------------------------------------------
add_user_to_group() {
    local group="$1"
    local target_user="${SUDO_USER:-$USER}"

    if groups "$target_user" | grep -q "\b$group\b"; then
        log_ok "User '$target_user' already in group '$group'"
    else
        usermod -aG "$group" "$target_user"
        log_ok "Added '$target_user' to group '$group'"
        log_warn "Log out and back in (or run 'newgrp $group') for group changes to take effect"
    fi
}

# ------------------------------------------------------------------------------
# Install NVIDIA drivers
# ------------------------------------------------------------------------------
install_nvidia_drivers() {
    if ! lspci 2>/dev/null | grep -i nvidia &>/dev/null; then
        log_warn "No NVIDIA GPU detected — skipping driver install"
        return
    fi

    log_warn "NVIDIA GPU detected but drivers are not installed."
    if ! confirm "Install NVIDIA drivers? (A reboot may be required afterwards)"; then
        log_warn "Skipping NVIDIA driver install. GPU profile will not be available."
        return
    fi

    log_info "Installing NVIDIA drivers..."
    case "$DISTRO_FAMILY" in
        rhel)
            dnf install -y nvidia-driver nvidia-driver-cuda \
                nvidia-driver-cuda-libs nvidia-settings nvidia-persistenced
            ;;
        debian)
            apt update -y
            apt install -y ubuntu-drivers-common
            ubuntu-drivers install
            ;;
    esac
    log_ok "NVIDIA drivers installed"
    log_warn "A reboot may be required before the GPU is usable"
}

# ------------------------------------------------------------------------------
# Install NVIDIA container toolkit
# ------------------------------------------------------------------------------
install_nvidia_container_toolkit() {
    log_info "Installing NVIDIA container toolkit..."
    case "$DISTRO_FAMILY" in
        rhel)
            dnf install -y nvidia-container-toolkit
            ;;
        debian)
            curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
                | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
            curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
                | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
                | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
            apt update -y
            apt install -y nvidia-container-toolkit
            ;;
    esac

    if [ "$RUNTIME" = "docker" ]; then
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
        log_ok "NVIDIA container toolkit configured for Docker"
    elif [ "$RUNTIME" = "podman" ]; then
        nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
        log_ok "NVIDIA container toolkit configured for Podman (CDI spec generated)"
    fi
}

# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------
main() {
    echo ""
    echo -e "${CYAN}=== Host Dependency Installer ===${NC}"
    echo -e "${CYAN}    On-Premise LLM Infrastructure${NC}"
    echo ""

    require_root
    detect_distro

    log_info "Running pre-flight checks to detect what needs installing..."
    echo ""

    # ------------------------------------------------------------------------------
    # Runtime check
    # ------------------------------------------------------------------------------
    if check_runtime; then
        log_ok "Container runtime already installed: $RUNTIME"
        PREFERRED_RUNTIME="$RUNTIME"
    else
        ask_runtime
        RUNTIME="$PREFERRED_RUNTIME"
        if [ "$RUNTIME" = "podman" ]; then
            install_podman
        else
            install_docker
        fi
    fi

    # ------------------------------------------------------------------------------
    # Daemon check
    # ------------------------------------------------------------------------------
    if ! check_daemon; then
        log_info "Starting $RUNTIME daemon..."
        systemctl enable --now "$RUNTIME" 2>/dev/null || true
    fi

    # ------------------------------------------------------------------------------
    # Compose plugin check
    # ------------------------------------------------------------------------------
    if check_compose; then
        log_ok "Compose plugin already available: $COMPOSE_CMD"
    else
        log_warn "Compose plugin missing — reinstalling runtime with compose support"
        if [ "$RUNTIME" = "podman" ]; then
            install_podman
        else
            install_docker
        fi
    fi

    # ------------------------------------------------------------------------------
    # Group membership
    # ------------------------------------------------------------------------------
    add_user_to_group "$RUNTIME" 2>/dev/null || true

    # ------------------------------------------------------------------------------
    # .env file
    # ------------------------------------------------------------------------------
    local env_status
    check_env_file "$SETUP_DIR"; env_status=$?
    case $env_status in
        0) log_ok ".env file already exists" ;;
        2)
            log_info "Copying .env.example → .env"
            cp "$SETUP_DIR/.env.example" "$SETUP_DIR/.env"
            log_ok "Copied. Review and edit $SETUP_DIR/.env before running compose."
            ;;
        1) log_warn ".env.example not found — you will need to create .env manually" ;;
    esac

    # ------------------------------------------------------------------------------
    # NVIDIA drivers
    # ------------------------------------------------------------------------------
    if check_nvidia_smi; then
        log_ok "NVIDIA drivers already installed"
    else
        install_nvidia_drivers
    fi

    # ------------------------------------------------------------------------------
    # NVIDIA container toolkit
    # ------------------------------------------------------------------------------
    if check_nvidia_smi; then
        if [ "$RUNTIME" = "docker" ] && check_nvidia_toolkit; then
            log_ok "NVIDIA container toolkit already configured for Docker"
        elif [ "$RUNTIME" = "podman" ]  && check_nvidia_devices &&  [ -f /etc/cdi/nvidia.yaml ]; then
            log_ok "NVIDIA CDI spec already present"
        else
            install_nvidia_container_toolkit
        fi
    fi

    # ------------------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------------------
    echo ""
    echo -e "${GREEN}=== Host setup complete ===${NC}"
    echo ""
    log_info "Next steps:"
    echo "  1. If group changes were made, log out and back in"
    echo "  2. If NVIDIA drivers were installed, reboot the server"
    echo "  3. Navigate to docker-small-team-setup/ and run: make compose"
    echo ""
}

main "$@"
