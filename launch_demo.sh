#!/usr/bin/env bash
# launch_demo.sh — one-shot demo bring-up for Sprezzature Studio.
#
# Frees the ports Studio/the API need, unloads every Ollama model except the
# one Ralph actually uses, warms it and checks it answers fast, runs the fast
# test suite as a final safety net (see .private/demo.md: "if either check
# fails, don't improvise live — fix it first"), then launches Studio and
# waits for it to actually answer before handing control back.
#
# Usage: bash launch_demo.sh

set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STUDIO_PORT=8080
API_PORT=8000
DEMO_MODEL="qwen3:8b"
LOG_FILE="/tmp/sprezzature-studio.log"

echo "==> Freeing port ${STUDIO_PORT} (Studio) and ${API_PORT} (API)..."
for port in "${STUDIO_PORT}" "${API_PORT}"; do
    pids="$(lsof -ti ":${port}" 2>/dev/null || true)"
    if [[ -n "${pids}" ]]; then
        echo "    killing $(echo "${pids}" | tr '\n' ' ') on :${port}"
        echo "${pids}" | xargs kill -9 2>/dev/null || true
    fi
done
sleep 1

echo "==> Unloading Ollama models other than ${DEMO_MODEL}..."
if command -v ollama >/dev/null 2>&1; then
    loaded="$(ollama ps 2>/dev/null | tail -n +2 | awk '{print $1}')"
    if [[ -n "${loaded}" ]]; then
        while IFS= read -r model; do
            if [[ -n "${model}" && "${model}" != "${DEMO_MODEL}" ]]; then
                echo "    stopping ${model}"
                ollama stop "${model}" >/dev/null 2>&1 || true
            fi
        done <<< "${loaded}"
    fi
else
    echo "    ollama not found on PATH, skipping"
fi

echo "==> Checking the Ollama server itself is reachable..."
if ! curl -s --max-time 3 -o /dev/null http://localhost:11434/api/version; then
    echo "    not reachable — the whole Ollama app has quit, not just its"
    echo "    models. Restarting it..."
    open -a Ollama 2>/dev/null || true
    for _ in $(seq 1 20); do
        curl -s --max-time 2 -o /dev/null http://localhost:11434/api/version && break
        sleep 1
    done
    if ! curl -s --max-time 3 -o /dev/null http://localhost:11434/api/version; then
        echo "    WARNING: still not reachable after restart. Ralph chat will"
        echo "    fail live — open Ollama.app by hand and re-run this script."
    else
        echo "    Ollama is back up"
    fi
fi

echo "==> Warming ${DEMO_MODEL} and timing its response..."
start_ts=$(date +%s)
if curl -s --max-time 30 -X POST http://localhost:11434/api/generate \
    -d "{\"model\":\"${DEMO_MODEL}\",\"prompt\":\"Say hi.\",\"stream\":false}" \
    -o /dev/null; then
    elapsed=$(( $(date +%s) - start_ts ))
    echo "    responded in ${elapsed}s"
    if (( elapsed > 15 )); then
        echo "    WARNING: that's slow — Ralph's chat may time out live. Consider"
        echo "    demoing the recommendation cards + manual style panel instead."
    fi
else
    echo "    WARNING: no response within 30s. Ralph chat is at risk; the"
    echo "    figure still renders fine without it (recommendation cards +"
    echo "    manual style panel need no model at all)."
fi

echo "==> Running the fast test suite (must pass, per .private/demo.md)..."
cd "${REPO_DIR}"
if ! python -m pytest -q > /tmp/sprezzature-pytest.log 2>&1; then
    echo "    TESTS FAILED — see /tmp/sprezzature-pytest.log. Not launching Studio."
    tail -30 /tmp/sprezzature-pytest.log
    exit 1
fi
echo "    tests passed"

echo "==> Launching Sprezzature Studio on port ${STUDIO_PORT}..."
nohup sprezzature-studio --port "${STUDIO_PORT}" > "${LOG_FILE}" 2>&1 &
disown

for _ in $(seq 1 40); do
    if curl -s -o /dev/null "http://localhost:${STUDIO_PORT}"; then
        echo "==> Studio is up: http://localhost:${STUDIO_PORT}"
        open "http://localhost:${STUDIO_PORT}" >/dev/null 2>&1 || true
        exit 0
    fi
    sleep 0.5
done

echo "    Studio did not answer in time — check ${LOG_FILE}:"
tail -40 "${LOG_FILE}"
exit 1
