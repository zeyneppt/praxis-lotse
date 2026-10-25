#!/usr/bin/env bash
# Gibt für jede Spec mit Status „fertig" oder „in Arbeit" ein
# `--include spec-NNN` aus (eine Zeile pro Spec). Keine aktive Spec: keine Ausgabe.
set -euo pipefail

specs_dir="${1:-$(dirname "$0")/../specs}"

for datei in "$specs_dir"/0*.md; do
  [ -e "$datei" ] || continue
  status=$(sed -n 's/^\*\*Status:\*\*[[:space:]]*//p' "$datei" | head -n 1 | sed 's/[[:space:]]*$//')
  case "$status" in
    fertig | "in Arbeit")
      nummer=$(basename "$datei" | cut -c1-3)
      echo "--include spec-$nummer"
      ;;
  esac
done
