#!/usr/bin/env bash

set -uo pipefail

ADMIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COURSE_DIR="$(cd "${ADMIN_DIR}/.." && pwd)"
SOURCE_DIR="${COURSE_DIR}/02_Notebooks"
OUTPUT_DIR="${COURSE_DIR}/02_Notebooks/Pdf"
RENDER_TOOL="${ADMIN_DIR}/render_pdf_handout.py"
ALLOW_DOWNLOAD=0

usage() {
  echo "Usage: $0 [--allow-chromium-download] [NOTEBOOK.ipynb ...]"
  echo
  echo "With no notebook arguments, convert every notebook under:"
  echo "  ${SOURCE_DIR}"
  echo
  echo "PDF handouts are written under:"
  echo "  ${OUTPUT_DIR}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${1:-}" == "--allow-chromium-download" ]]; then
  ALLOW_DOWNLOAD=1
  shift
fi

if ! command -v jupyter >/dev/null 2>&1 || ! jupyter nbconvert --version >/dev/null 2>&1; then
  echo "Error: jupyter nbconvert is not available in the active environment." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not available in the active environment." >&2
  exit 1
fi

if ! python3 -c 'import playwright' >/dev/null 2>&1; then
  echo "Error: Playwright is required for PDF generation." >&2
  echo "Install it with: python3 -m pip install 'nbconvert[webpdf]'" >&2
  exit 1
fi

BROWSER_INSTALL_DIR="$(python3 -m playwright install --dry-run chromium | awk '\
  /Chrome Headless Shell/ { found = 1 } \
  found && /Install location:/ { sub(/^.*Install location:[[:space:]]*/, ""); print; exit }\
')"

if [[ -z "${BROWSER_INSTALL_DIR}" || ! -d "${BROWSER_INSTALL_DIR}" ]]; then
  if ((ALLOW_DOWNLOAD)); then
    echo "Chromium is missing; installing the browser used by Playwright..."
    python3 -m playwright install chromium || exit 1
    if [[ -z "${BROWSER_INSTALL_DIR}" || ! -d "${BROWSER_INSTALL_DIR}" ]]; then
      echo "Error: Playwright Chromium is still unavailable after installation." >&2
      exit 1
    fi
  else
    echo "Error: Playwright is installed, but its Chromium browser is missing." >&2
    echo "Rerun with Chromium download enabled:" >&2
    echo "  $0 --allow-chromium-download [NOTEBOOK.ipynb ...]" >&2
    exit 1
  fi
fi

mkdir -p "${OUTPUT_DIR}"
TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mobile-computing-handouts.XXXXXX")"
trap 'rm -rf "${TEMP_DIR}"' EXIT

converted=0
failed=0

convert_notebook() {
  local notebook="$1"
  local relative_path relative_dir target_dir stem html_file pdf_file

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
  stem="$(basename "${relative_path%.ipynb}")"
  target_dir="${OUTPUT_DIR}/${relative_dir}"
  html_file="${TEMP_DIR}/${stem}.html"
  pdf_file="${target_dir}/${stem}.handout.pdf"

  mkdir -p "${target_dir}"
  echo "Converting ${relative_path}"

  if jupyter nbconvert \
    --to html \
    --HTMLExporter.embed_images=True \
    --TagRemovePreprocessor.enabled=True \
    --TagRemovePreprocessor.remove_input_tags='{"hide-input"}' \
    --output="${html_file}" \
    "${notebook}" &&
    python3 "${RENDER_TOOL}" \
      --notebook "${notebook}" \
      --html "${html_file}" \
      --pdf "${pdf_file}" \
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
      notebook="${requested_dir}/$(basename "${SOURCE_DIR}/${requested}")"
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
echo "PDF handouts: ${OUTPUT_DIR}"

if ((failed > 0)); then
  exit 1
fi
