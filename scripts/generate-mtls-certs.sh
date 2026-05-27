#!/usr/bin/env bash
# INFRA-019 / Phase 5 — generate self-signed mTLS certs for service-to-service auth.
#
# Output layout:
#   infra/certs/
#     ca.crt                      # root CA (mounted into every service for verification)
#     ca.key                      # NEVER ship this anywhere; staging-only
#     <service>/server.crt        # per-service leaf cert
#     <service>/server.key
#
# Each service mounts:
#   - /etc/eduzim-tls/ca.crt              (read-only, shared)
#   - /etc/eduzim-tls/server.crt          (read-only, service-specific)
#   - /etc/eduzim-tls/server.key          (read-only, service-specific)
#
# The eduzim_shared.mtls module wires these into uvicorn (server side)
# and httpx (client side).
#
# When to rotate:
#   - Default validity is 365 days; rerun this script and `docker compose
#     restart <service>` for each service.
#   - For production-grade rotation, replace this script with cert-manager
#     in k8s; this script is staging-only.
set -euo pipefail

CERT_DIR="${CERT_DIR:-./infra/certs}"
DAYS="${DAYS:-365}"

# All services that need an inbound TLS cert. The gateway is included
# (services talk to the gateway in some flows) and so are the four
# downstream services + reporting.
SERVICES=(api-gateway identity academics finance communications reporting-service)

mkdir -p "${CERT_DIR}"

# ─── Root CA ───
if [[ ! -f "${CERT_DIR}/ca.key" ]]; then
    echo "[mtls] generating root CA"
    openssl genrsa -out "${CERT_DIR}/ca.key" 4096
    openssl req -x509 -new -nodes -sha256 -key "${CERT_DIR}/ca.key" \
        -subj "/C=ZW/ST=Harare/O=EduZim/CN=eduzim-internal-ca" \
        -days $((DAYS * 5)) \
        -out "${CERT_DIR}/ca.crt"
    chmod 600 "${CERT_DIR}/ca.key"
else
    echo "[mtls] reusing existing root CA (${CERT_DIR}/ca.crt)"
fi

# ─── Per-service leaf certs ───
for svc in "${SERVICES[@]}"; do
    out="${CERT_DIR}/${svc}"
    mkdir -p "${out}"

    echo "[mtls] generating cert for ${svc}"
    openssl genrsa -out "${out}/server.key" 2048

    cat > "${out}/server.cnf" <<EOF
[ req ]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[ req_distinguished_name ]
C = ZW
ST = Harare
O = EduZim
CN = ${svc}

[ v3_req ]
subjectAltName = @alt_names
extendedKeyUsage = serverAuth, clientAuth

[ alt_names ]
DNS.1 = ${svc}
DNS.2 = localhost
DNS.3 = eduzim-${svc#api-}     # back-compat container_name
IP.1 = 127.0.0.1
EOF

    openssl req -new -key "${out}/server.key" -out "${out}/server.csr" \
        -config "${out}/server.cnf"

    openssl x509 -req -in "${out}/server.csr" \
        -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key" -CAcreateserial \
        -out "${out}/server.crt" -days "${DAYS}" -sha256 \
        -extfile "${out}/server.cnf" -extensions v3_req

    chmod 600 "${out}/server.key"
    rm "${out}/server.csr" "${out}/server.cnf"
done

echo ""
echo "[mtls] done. ${CERT_DIR}/ now contains:"
ls -la "${CERT_DIR}"
echo ""
echo "Next steps:"
echo "  1. Mount ${CERT_DIR}/ca.crt and ${CERT_DIR}/<svc>/server.{crt,key}"
echo "     into each service container. See docker-compose.ha.yml's"
echo "     volumes blocks for the per-service path."
echo "  2. Set EDUZIM_TLS_ENABLED=true on each service so app_factory wires uvicorn for TLS."
echo "  3. Rotate every ${DAYS} days (or every 90 in prod once you switch to cert-manager)."
