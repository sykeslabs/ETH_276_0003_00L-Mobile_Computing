#!/usr/bin/env bash

set -uo pipefail

ADMIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COURSE_DIR="$(cd "${ADMIN_DIR}/.." && pwd)"
SOURCE_DIR="${COURSE_DIR}/02_Notebooks"
OUTPUT_DIR="${COURSE_DIR}/02_Notebooks/Html"
HEADER_TOOL="${ADMIN_DIR}/add_slide_header.py"
THEME="${REVEAL_THEME:-solarized}"

usage() {
  echo "Usage: $0 [NOTEBOOK.ipynb ...]"
  echo
  echo "With no notebook arguments, convert every notebook under:"
  echo "  ${SOURCE_DIR}"
  echo
  echo "With one or more notebook arguments, convert only those files."
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v jupyter >/dev/null 2>&1; then
  echo "Error: jupyter is not available in the active environment." >&2
  exit 1
fi

if ! jupyter nbconvert --version >/dev/null 2>&1; then
  echo "Error: nbconvert is not installed in the active environment." >&2
  echo "Install it with: python3 -m pip install nbconvert" >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not available in the active environment." >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

converted=0
failed=0

convert_notebook() {
  local notebook="$1"
  local relative_path
  local relative_dir
  local target_dir
  local output_file

  case "${notebook}" in
    "${SOURCE_DIR}"/*) ;;
    *)
      echo "Skipped file outside ${SOURCE_DIR}: ${notebook}" >&2
      failed=$((failed + 1))
      return
      ;;
  esac

  relative_path="${notebook#"${SOURCE_DIR}/"}"
  relative_dir="$(dirname "${relative_path}")"
  target_dir="${OUTPUT_DIR}/${relative_dir}"
  output_file="${target_dir}/$(basename "${relative_path%.ipynb}").slides.html"

  mkdir -p "${target_dir}"
  echo "Converting ${relative_path}"

  if jupyter nbconvert \
    --to slides \
    --SlidesExporter.reveal_theme="${THEME}" \
    --TagRemovePreprocessor.enabled=True \
    --TagRemovePreprocessor.remove_input_tags='{"hide-input"}' \
    --output-dir="${target_dir}" \
    "${notebook}" &&
    python3 "${HEADER_TOOL}" \
      --notebook "${notebook}" \
      --html "${output_file}" \
      --logo "${ADMIN_DIR}/img/eth_logo_kurz_pos.png" \
      --font-regular "${ADMIN_DIR}/fonts/Roboto-Regular.ttf" \
      --font-bold "${ADMIN_DIR}/fonts/Roboto-Bold.ttf"; then
    converted=$((converted + 1))
  else
    echo "Failed: ${relative_path}" >&2
    failed=$((failed + 1))
  fi
}

if (($# == 0)); then
  while IFS= read -r -d '' notebook; do
    convert_notebook "${notebook}"
  done < <(find "${SOURCE_DIR}" -type f -name '*.ipynb' ! -path '*/.ipynb_checkpoints/*' -print0)
else
  for requested in "$@"; do
    if [[ -f "${requested}" ]]; then
      requested_dir="$(cd "$(dirname "${requested}")" && pwd)"
      notebook="${requested_dir}/$(basename "${requested}")"
    elif [[ -f "${SOURCE_DIR}/${requested}" ]]; then
      requested_dir="$(cd "$(dirname "${SOURCE_DIR}/${requested}")" && pwd)"
      notebook="${requested_dir}/$(basename "${requested}")"
    else
      echo "Notebook not found: ${requested}" >&2
      failed=$((failed + 1))
      continue
    fi
    convert_notebook "${notebook}"
  done
fi

echo
echo "Finished: ${converted} converted, ${failed} failed."
echo "HTML slides: ${OUTPUT_DIR}"

if ((failed > 0)); then
  exit 1
fi
