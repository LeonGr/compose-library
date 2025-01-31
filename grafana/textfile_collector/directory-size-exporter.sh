#!/bin/bash

# Exit on failure, pipe failure
set -e -o pipefail

get_size_bytes() {
    DIR_PATH="$1"
    du -sb "$DIR_PATH" | awk '{print $1}'
}

DIRECTORY_SIZE_BYTES_METRIC_NAME="directory_size_bytes"

get_prometheus_metric() {
    DIR_PATH="$1"
    SIZE_BYTES="$2"
    echo "$DIRECTORY_SIZE_BYTES_METRIC_NAME{directory=\"$DIR_PATH\"} $SIZE_BYTES"
}

PATHS_FILE="/home/leon/Services/compose-library/grafana/textfile_collector/paths.txt"
TMP_FILE="/home/leon/Services/compose-library/grafana/textfile_collector/tmp/directory-size.prom"
OUTPUT_FILE="/home/leon/Services/compose-library/grafana/textfile_collector/prom/directory-size.prom"

echo "# TYPE $DIRECTORY_SIZE_BYTES_METRIC_NAME" > "$TMP_FILE"

while IFS= read -r LINE;
do
    if [[ $LINE == \#* ]]; then
        echo "Skipping commented line $LINE"
    else
        DIR_PATH="$LINE"
        echo "Getting size of '$DIR_PATH'"

        start=$(date +%s.%N)
        SIZE_BYTES=$(get_size_bytes "$DIR_PATH")
        end=$(date +%s.%N)

        elapsed=$(echo "$end - $start" | bc)
        echo "Elapsed time: $elapsed seconds"

        METRIC=$(get_prometheus_metric "$DIR_PATH" "$SIZE_BYTES")
        echo "$METRIC" >> "$TMP_FILE"
    fi
done < "$PATHS_FILE"

cat "$TMP_FILE" > "$OUTPUT_FILE"

exit 0
