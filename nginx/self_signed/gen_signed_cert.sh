#!/bin/bash

generate_certificate() {
    # Set the Common Name (CN) for the service
    CN=$1

    # Check if CN is provided
    if [ -z "$CN" ]; then
      echo "Usage: $0 <common_name>"
      exit 1
    fi

    # Ensure there is a directory for the common_name
    mkdir -p "./certificates/$CN"

    # Generate a private key for the service
    openssl genpkey -algorithm RSA -out "./certificates/$CN/$CN.key"

    # Generate a CSR for the service
    openssl req -new -key "./certificates/$CN/$CN.key" -out "./certificates/$CN/$CN.csr" -subj "/CN=$CN" --addext "subjectAltName=DNS:$CN"

    # Sign the CSR with the root CA
    openssl x509 -req -in "./certificates/$CN/$CN.csr" -CA ./rootCA.crt -CAkey ./rootCA.key -CAcreateserial -out "./certificates/$CN/$CN.crt" -days 365 -copy_extensions copyall

    echo "Certificate for $CN generated and signed by the root CA."
}

# Check if at least one argument is provided
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <list_of_common_names>"
    exit 1
fi

for cn in "$@"; do
    generate_certificate $cn
done

echo "Done. Don't forget to set ownership"

exit 0
