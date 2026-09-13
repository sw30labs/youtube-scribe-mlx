#!/bin/bash
# Invoked by YouTubeToText.app in Terminal so progress and failures stay visible.
set -uo pipefail

PROJECT_DIR="${1:-/Users/spider/REPOS/mlx-youtube-scribe-omlx}"
INBOX_DIR="${2:-${HOME}/Desktop/YouTubeToText}"
export YOUTUBE_PYTHON="${3:-${HOME}/miniconda3/envs/youtube/bin/python}"
STT_KEY="${4:-}"
export PATH="$(dirname "${YOUTUBE_PYTHON}"):${HOME}/.local/bin:${HOME}/.hermes/node/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
RUNNER="${PROJECT_DIR}/run_youtube_inbox.sh"
LOG_DIR="${INBOX_DIR}/logs"

if ! mkdir -p "${LOG_DIR}"; then
  printf 'Could not create the inbox log folder: %s\n' "${LOG_DIR}" >&2
  exit 1
fi
LOG_NAME="$(date '+%Y-%m-%d_%H-%M-%S')-$$.log"
LOG_FILE="${LOG_DIR}/${LOG_NAME}"
# Each run keeps its own log even if the app is opened twice.
ln -sfn "${LOG_NAME}" "${LOG_DIR}/last-run.log"

printf '\n=== YouTubeToText ===\nInbox: %s\nLog:   %s\n\n' "${INBOX_DIR}" "${LOG_FILE}"
printf 'Transcribing new video links. Finished text opens automatically.\n\n'

if [[ ! -f "${RUNNER}" ]]; then
  printf 'Error: Pipeline script not found: %s\n' "${RUNNER}" | tee "${LOG_FILE}"
  status=1
else
  STT_ARGS=()
  if [[ -n "${STT_KEY}" ]]; then
    STT_ARGS+=(--stt "${STT_KEY}")
  fi
  /bin/bash "${RUNNER}" --inbox "${INBOX_DIR}" --open-output "${STT_ARGS[@]}" 2>&1 | tee "${LOG_FILE}"
  status=${PIPESTATUS[0]}
fi

printf '\n'
if [[ "${status}" -eq 0 ]]; then
  message="Processing finished. You can close this Terminal window."
  printf '%s\n' "${message}"
else
  message="Processing stopped. See Terminal and the latest log for details."
  printf 'Processing stopped (exit %s).\nLog: %s\n' "${status}" "${LOG_FILE}"
fi

/usr/bin/osascript - "${message}" <<'APPLESCRIPT' || true
on run argv
  display notification (item 1 of argv) with title "YouTubeToText"
end run
APPLESCRIPT
exit "${status}"
