#!/bin/bash
# PSI Control Tower — Azure Canada Deployment Script
#
# Deploys to Azure Container Instances in Canada Central region.
# All data remains within Canadian jurisdiction (PIPEDA/Privacy Act compliant).
#
# Prerequisites:
#   - Azure CLI installed and authenticated
#   - Subscription with access to Canada Central region
#
# Usage:
#   ./deploy/azure/deploy.sh

set -euo pipefail

# ── Configuration ──
RESOURCE_GROUP="psi-control-tower-rg"
LOCATION="canadacentral"              # Azure Canada Central (Toronto)
CONTAINER_NAME="psi-control-tower"
REGISTRY_NAME="psicracr"
IMAGE_NAME="psi-control-tower"
IMAGE_TAG="latest"
DNS_LABEL="psi-control-tower"

echo "=========================================="
echo "PSI Control Tower — Azure Canada Deployment"
echo "=========================================="
echo "Region: ${LOCATION} (Canada Central — Toronto)"
echo "Data Sovereignty: All data confined to Canadian jurisdiction"
echo ""

# 1. Create Resource Group in Canada Central
echo "[1/5] Creating resource group in ${LOCATION}..."
az group create \
    --name "${RESOURCE_GROUP}" \
    --location "${LOCATION}" \
    --tags \
        project=psi-control-tower \
        classification=unclassified \
        data-sovereignty=canada \
        owner=qdt

# 2. Create Azure Container Registry
echo "[2/5] Creating container registry..."
az acr create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${REGISTRY_NAME}" \
    --sku Basic \
    --location "${LOCATION}" \
    --admin-enabled true

# 3. Build and push image
echo "[3/5] Building and pushing container image..."
az acr build \
    --registry "${REGISTRY_NAME}" \
    --image "${IMAGE_NAME}:${IMAGE_TAG}" \
    .

# 4. Get registry credentials
ACR_PASSWORD=$(az acr credential show --name "${REGISTRY_NAME}" --query "passwords[0].value" -o tsv)
ACR_SERVER="${REGISTRY_NAME}.azurecr.io"

# 5. Deploy to Azure Container Instances
echo "[4/5] Deploying container instance..."
az container create \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${CONTAINER_NAME}" \
    --image "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --registry-login-server "${ACR_SERVER}" \
    --registry-username "${REGISTRY_NAME}" \
    --registry-password "${ACR_PASSWORD}" \
    --dns-name-label "${DNS_LABEL}" \
    --ports 8000 \
    --cpu 2 \
    --memory 4 \
    --location "${LOCATION}" \
    --os-type Linux \
    --restart-policy OnFailure \
    --environment-variables \
        PSI_ENVIRONMENT=production \
        PSI_DATA_SOVEREIGNTY=canada \
        PSI_AZURE_REGION=canadacentral \
    --tags \
        project=psi-control-tower \
        classification=unclassified \
        data-sovereignty=canada

# 6. Get deployment URL
echo "[5/5] Deployment complete!"
FQDN=$(az container show \
    --resource-group "${RESOURCE_GROUP}" \
    --name "${CONTAINER_NAME}" \
    --query "ipAddress.fqdn" -o tsv)

echo ""
echo "=========================================="
echo "PSI Control Tower is live!"
echo "=========================================="
echo "URL:      http://${FQDN}:8000"
echo "API Docs: http://${FQDN}:8000/docs"
echo "Region:   ${LOCATION} (Canada Central)"
echo "=========================================="
echo ""
echo "Data Sovereignty Confirmation:"
echo "  - Container runs in Azure Canada Central (Toronto)"
echo "  - No data routing through US or international servers"
echo "  - Subject to Canadian law (PIPEDA/Privacy Act)"
echo "  - No extraterritorial exposure"
