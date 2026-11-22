#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
TRANSCRIBE_SCRIPT="${SCRIPT_DIR}/src/transcribe_m4a.py"
VENV_DIR="${VENV_DIR:-${SCRIPT_DIR}/.venv-nemotron}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_PYTHON="${VENV_DIR}/bin/python"
YOUTUBE_PYTHON="${YOUTUBE_PYTHON:-${HOME}/miniconda3/envs/youtube/bin/python}"
NEMOTRON_IMPORT='import mlx_audio.stt.models.nemotron_transcribe'


usage() {
    cat <<EOF
Usage: $(basename "$0") AUDIO_FILE.(m4a|mp3|wav) [TRANSCRIPTION_OPTIONS]

Set up Nemotron 3.5 Transcribe and transcribe an M4A, MP3, or WAV file.

Uses ${YOUTUBE_PYTHON} when that interpreter can already import Nemotron.
Otherwise creates ${VENV_DIR} and installs mlx-audio>=0.6.3.

The BF16 checkpoint is about 66 GB and is downloaded on the first run.
Unload other large models first. Set NEMOTRON_STT_MODEL to a 4-bit MLX
build or a local folder to load a smaller checkpoint.

Options forwarded to transcribe_m4a.py:
  -o, --output PATH       Write the transcript to a UTF-8 text file
  --language LANGUAGE     Kept for compatibility. Nemotron transcribes in the
                          spoken language and does not take this as a target.
  --save-stt              Remember nemotron as the default STT
  -h, --help              Show this help message

Environment overrides:
  YOUTUBE_PYTHON          Conda interpreter to use when Nemotron is installed
  PYTHON_BIN              Python used to create the fallback environment
  VENV_DIR                Fallback virtual environment (default: .venv-nemotron)
  NEMOTRON_STT_MODEL      Checkpoint repo or local folder

Examples:
  $(basename "$0") /path/to/audio.m4a
  $(basename "$0") /path/to/audio.wav --output transcript.txt
EOF
}


log() {
    printf '==> %s\n' "$*" >&2
}


die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}


run_as_root() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@" >&2
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@" >&2
    else
        die "Installing FFmpeg requires root privileges. Re-run with sudo available or install FFmpeg manually."
    fi
}


ensure_ffmpeg() {
    if command -v ffmpeg >/dev/null 2>&1; then
        return
    fi

    log "FFmpeg was not found; attempting to install it."
    case "${OSTYPE:-}" in
        darwin*)
            if ! command -v brew >/dev/null 2>&1; then
                die "Homebrew is required to install FFmpeg on macOS. Install Homebrew, then run: brew install ffmpeg"
            fi
            brew install ffmpeg >&2
            ;;
        linux*)
            if command -v apt-get >/dev/null 2>&1; then
                run_as_root apt-get update
                run_as_root apt-get install -y ffmpeg
            elif command -v dnf >/dev/null 2>&1; then
                run_as_root dnf install -y ffmpeg
            elif command -v yum >/dev/null 2>&1; then
                run_as_root yum install -y ffmpeg
            elif command -v pacman >/dev/null 2>&1; then
                run_as_root pacman -S --needed --noconfirm ffmpeg
            elif command -v zypper >/dev/null 2>&1; then
                run_as_root zypper --non-interactive install ffmpeg
            else
                die "No supported package manager was found. Install FFmpeg manually and ensure it is on PATH."
            fi
            ;;
        *)
            die "Install FFmpeg manually and ensure it is on PATH."
            ;;
    esac

    hash -r
    command -v ffmpeg >/dev/null 2>&1 || die "FFmpeg installation completed, but ffmpeg is still not on PATH."
}


check_python_version() {
    local python_path="$1"
    if ! "${python_path}" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' >/dev/null 2>&1; then
        die "Python 3.9 or newer is required: ${python_path}"
    fi
}


python_has_nemotron() {
    local python_path="$1"
    [[ -x "${python_path}" ]] || return 1
    "${python_path}" -c "${NEMOTRON_IMPORT}" >/dev/null 2>&1
}


ensure_virtual_environment() {
    if [[ -x "${VENV_PYTHON}" ]]; then
        check_python_version "${VENV_PYTHON}"
        log "Using existing virtual environment: ${VENV_DIR}"
        return
    fi

    if [[ -e "${VENV_DIR}" ]]; then
        die "${VENV_DIR} exists but is not a usable Python virtual environment."
    fi
    if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
        die "Python executable not found: ${PYTHON_BIN}"
    fi

    check_python_version "${PYTHON_BIN}"
    log "Creating virtual environment: ${VENV_DIR}"
    "${PYTHON_BIN}" -m venv "${VENV_DIR}" >&2
    [[ -x "${VENV_PYTHON}" ]] || die "Virtual environment creation failed: ${VENV_DIR}"
}


ensure_python_dependencies() {
    if python_has_nemotron "${VENV_PYTHON}"; then
        log "Nemotron STT dependencies are already installed."
        return
    fi

    log "Installing Nemotron STT dependencies (mlx-audio>=0.6.3)..."
    "${VENV_PYTHON}" -m pip install --upgrade pip >&2
    "${VENV_PYTHON}" -m pip install --upgrade numpy 'mlx-audio>=0.6.3' >&2

    if ! python_has_nemotron "${VENV_PYTHON}"; then
        die "mlx-audio was installed but Nemotron 3.5 Transcribe could not be imported."
    fi
}


resolve_python() {
    if python_has_nemotron "${YOUTUBE_PYTHON}"; then
        log "Using ${YOUTUBE_PYTHON}"
        printf '%s\n' "${YOUTUBE_PYTHON}"
        return
    fi

    ensure_virtual_environment
    ensure_python_dependencies
    printf '%s\n' "${VENV_PYTHON}"
}


# Drop a caller-supplied --stt so this wrapper always runs Nemotron.
filter_stt_args() {
    FILTERED_ARGS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --stt)
                shift
                if [[ $# -gt 0 ]]; then
                    shift
                fi
                ;;
            --stt=*)
                shift
                ;;
            *)
                FILTERED_ARGS+=("$1")
                shift
                ;;
        esac
    done
}


main() {
    if [[ $# -eq 0 ]]; then
        usage >&2
        exit 2
    fi
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        usage
        exit 0
    fi

    local audio_file="$1"
    shift

    [[ -f "${audio_file}" ]] || die "Audio file not found: ${audio_file}"
    case "${audio_file}" in
        *.[mM]4[aA]|*.[mM][pP]3|*.[wW][aA][vV]) ;;
        *) die "Expected an .m4a, .mp3, or .wav audio file: ${audio_file}" ;;
    esac
    [[ -f "${TRANSCRIBE_SCRIPT}" ]] || die "Transcription script not found: ${TRANSCRIBE_SCRIPT}"

    ensure_ffmpeg
    local run_python
    run_python="$(resolve_python)"
    filter_stt_args "$@"

    log "Nemotron 3.5 Transcribe BF16 is about 66 GB. Unload other large models before the first download."
    log "Starting Nemotron transcription: ${audio_file}"
    # bash 3.2 treats an empty "${array[@]}" as unbound when set -u is on.
    if [[ ${#FILTERED_ARGS[@]} -eq 0 ]]; then
        exec "${run_python}" "${TRANSCRIBE_SCRIPT}" "${audio_file}" --stt nemotron
    fi
    exec "${run_python}" "${TRANSCRIBE_SCRIPT}" "${audio_file}" "${FILTERED_ARGS[@]}" --stt nemotron
}


main "$@"
