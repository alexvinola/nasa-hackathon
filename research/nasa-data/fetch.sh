#!/usr/bin/env bash
# Downloads the public NASA data PULSAR uses into research/nasa-data/raw/ (git-ignored). Idempotent.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p raw

fetch() {  # fetch <url> <file>
  if [[ -s "raw/$2" ]]; then echo "present      raw/$2"; return; fi
  echo "downloading  raw/$2"
  curl -fsSL --retry 3 -A "Mozilla/5.0" -o "raw/$2.part" "$1" && mv "raw/$2.part" "raw/$2"
}

OSDR="https://osdr.nasa.gov/geode-py/ws/studies"
fetch "$OSDR/OSD-569/download?source=datamanager&file=LSDS-7_Complete_Blood_Count_CBC_TRANSFORMED.csv" cbc.csv
fetch "$OSDR/OSD-575/download?source=datamanager&file=LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv" cmp.csv
fetch "$OSDR/OSD-575/download?source=datamanager&file=LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv" cardio.csv
fetch "https://asrs.arc.nasa.gov/docs/rpsts/acr_fatg.pdf" asrs_air_carrier_fatigue.pdf
fetch "https://asrs.arc.nasa.gov/docs/rpsts/com_fatigue.pdf" asrs_commuter_corporate_fatigue.pdf
