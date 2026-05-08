#!/bin/bash

# Kong Konnect Gateway Setup Script
# This script helps you connect to Kong Konnect and manage your Flood-Management-Gateway

set -e

# Configuration
KONNECT_ADDR="${KONNECT_ADDR:-https://in.api.konghq.com}"
KONNECT_TOKEN="${KONNECT_TOKEN:-}"
CONTROL_PLANE_NAME="${CONTROL_PLANE_NAME:-Flood-Management-Gateway}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Kong Konnect Gateway Setup ===${NC}\n"

# Check if token is provided
if [ -z "$KONNECT_TOKEN" ]; then
    echo -e "${RED}Error: KONNECT_TOKEN environment variable is not set${NC}"
    echo -e "${YELLOW}Usage:${NC}"
    echo "  export KONNECT_TOKEN='kpat_YOUR_TOKEN_HERE'"
    echo "  export KONNECT_ADDR='https://in.api.konghq.com'"
    echo "  export CONTROL_PLANE_NAME='Flood-Management-Gateway'"
    echo ""
    echo "Then run: $0 [command]"
    echo ""
    echo -e "${YELLOW}Available commands:${NC}"
    echo "  ping       - Test connectivity to Kong Konnect"
    echo "  dump       - Export current gateway configuration"
    echo "  sync       - Sync local configuration to Kong Konnect"
    exit 1
fi

# Function to test connectivity
ping_gateway() {
    echo -e "${YELLOW}Testing connectivity to Kong Konnect...${NC}"
    echo "Control Plane: $CONTROL_PLANE_NAME"
    echo "Address: $KONNECT_ADDR"
    echo ""
    
    curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" | jq '.data[] | {id: .id, name: .name}'
    
    echo -e "\n${GREEN}✓ Connection successful!${NC}"
}

# Function to dump configuration
dump_config() {
    echo -e "${YELLOW}Exporting gateway configuration...${NC}"
    
    local output_file="${1:-kong-konnect-export.yaml}"
    
    # Get control plane ID
    local cp_id=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" | \
        jq -r ".data[] | select(.name==\"${CONTROL_PLANE_NAME}\") | .id")
    
    if [ -z "$cp_id" ]; then
        echo -e "${RED}Error: Could not find control plane with name '${CONTROL_PLANE_NAME}'${NC}"
        exit 1
    fi
    
    echo "Control Plane ID: $cp_id"
    
    # Export services
    curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${cp_id}/core-entities/services" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" > "${output_file}.services.json"
    
    # Export routes
    curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${cp_id}/core-entities/routes" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" > "${output_file}.routes.json"
    
    # Export plugins
    curl -s -X GET "${KONNECT_ADDR}/v2/control-planes/${cp_id}/core-entities/plugins" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" > "${output_file}.plugins.json"
    
    echo -e "${GREEN}✓ Configuration exported:${NC}"
    echo "  - ${output_file}.services.json"
    echo "  - ${output_file}.routes.json"
    echo "  - ${output_file}.plugins.json"
}

# Function to sync configuration
sync_config() {
    local config_file="${1:-}"
    
    if [ -z "$config_file" ]; then
        echo -e "${RED}Error: Configuration file not specified${NC}"
        echo "Usage: $0 sync <config-file.yaml>"
        exit 1
    fi
    
    if [ ! -f "$config_file" ]; then
        echo -e "${RED}Error: Configuration file not found: $config_file${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}Syncing configuration to Kong Konnect...${NC}"
    echo "File: $config_file"
    
    # Get control plane ID
    local cp_id=$(curl -s -X GET "${KONNECT_ADDR}/v2/control-planes" \
        --header "Authorization: Bearer ${KONNECT_TOKEN}" \
        --header "Content-Type: application/json" | \
        jq -r ".data[] | select(.name==\"${CONTROL_PLANE_NAME}\") | .id")
    
    if [ -z "$cp_id" ]; then
        echo -e "${RED}Error: Could not find control plane with name '${CONTROL_PLANE_NAME}'${NC}"
        exit 1
    fi
    
    echo -e "${YELLOW}This feature requires deck CLI. Install it with:${NC}"
    echo "curl -L https://github.com/Kong/deck/releases/download/v1.42.2/deck_1.42.2_linux_amd64.tar.gz | tar xz && sudo mv deck /usr/local/bin/"
    echo ""
    echo "Then run:"
    echo "  deck gateway sync $config_file \\"
    echo "    --konnect-control-plane-name='${CONTROL_PLANE_NAME}' \\"
    echo "    --konnect-addr='${KONNECT_ADDR}' \\"
    echo "    --konnect-token='${KONNECT_TOKEN}'"
}

# Main command handling
COMMAND="${1:-ping}"

case "$COMMAND" in
    ping)
        ping_gateway
        ;;
    dump)
        dump_config "${2:-kong-konnect-export.yaml}"
        ;;
    sync)
        sync_config "$2"
        ;;
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo "Available commands: ping, dump, sync"
        exit 1
        ;;
esac
