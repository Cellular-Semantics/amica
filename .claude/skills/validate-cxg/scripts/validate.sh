#!/usr/bin/env bash
# Run the CXG annotation validator.
#
# Usage:
#   scripts/validate.sh <raw-output-dir> <reports-dir>
#
# Example:
#   scripts/validate.sh runs/baseline/ runs/baseline/reports/
#
# Expects to be run from the amica project root (where pyproject.toml lives).

set -euo pipefail

RAW_DIR="${1:?raw-output-dir required}"
REPORTS_DIR="${2:?reports-dir required}"

mkdir -p "$REPORTS_DIR"

uv run python scripts/generate_validation_reports.py \
  --raw-output-dir "$RAW_DIR" \
  --reports-dir "$REPORTS_DIR"

echo "Validation complete. Reports written to: $REPORTS_DIR"
ls "$REPORTS_DIR"
