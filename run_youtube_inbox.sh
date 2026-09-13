#!/bin/bash
# Use the existing YouTube transcription environment without activating conda.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PYTHON_BIN="${YOUTUBE_PYTHON:-${HOME}/miniconda3/envs/youtube/bin/python}"
INBOX_DIR="${YOUTUBE_INBOX_DIR:-${HOME}/Desktop/YouTubeToText}"
PYTHON_SCRIPT="${SCRIPT_DIR}/src/youtube_inbox.py"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  printf 'Error: YouTube Python was not found at %s. Set YOUTUBE_PYTHON to the environment Python.\n' "${PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
  printf 'Error: Missing inbox processor: %s\n' "${PYTHON_SCRIPT}" >&2
  exit 1
fi

export PATH="$(dirname "${PYTHON_BIN}"):${HOME}/.local/bin:${HOME}/.hermes/node/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export PYTHONUNBUFFERED=1
cd -- "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" "${PYTHON_SCRIPT}" --inbox "${INBOX_DIR}" "$@"
