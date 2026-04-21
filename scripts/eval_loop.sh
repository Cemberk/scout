#!/usr/bin/env bash
############################################################################
#
#   Scout autonomous eval loop
#
#   Usage: ./scripts/eval_loop.sh <case_id>
#     env: MAX_ATTEMPTS (default 5)
#          BASE_URL     (default http://localhost:8000)
#
#   Each attempt:
#     1. run the case — exit 0 on PASS
#     2. read the diagnostic written by `run` to evals/results/<case>.md
#     3. hand it to `claude -p` (headless, restricted tools) to edit
#     4. checkpoint the edit as a git commit (revertable)
#     5. restart the docker service, loop
#
############################################################################

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CASE="${1:-}"
if [[ -z "${CASE}" ]]; then
    echo "usage: $0 <case_id>" >&2
    echo "       MAX_ATTEMPTS=\${MAX_ATTEMPTS:-5}  BASE_URL=\${BASE_URL:-http://localhost:8000}" >&2
    exit 2
fi

MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
SERVICE="scout-api"
DIAGNOSTIC="${REPO_ROOT}/evals/results/${CASE}.md"

BOLD='\033[1m'
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
NC='\033[0m'

IS_GIT=1
git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1 || IS_GIT=0

for i in $(seq 1 "${MAX_ATTEMPTS}"); do
    echo -e "\n${BOLD}=== attempt ${i}/${MAX_ATTEMPTS} (case: ${CASE}) ===${NC}\n"

    if python -m evals --live --case "${CASE}" --base-url "${BASE_URL}"; then
        echo -e "\n${GREEN}${BOLD}PASS on attempt ${i}${NC}"
        exit 0
    fi

    if [[ ! -s "${DIAGNOSTIC}" ]]; then
        echo -e "${RED}no diagnostic written at ${DIAGNOSTIC} — aborting${NC}" >&2
        exit 1
    fi

    echo -e "${YELLOW}diagnostic: ${DIAGNOSTIC} ($(wc -l < "${DIAGNOSTIC}") lines)${NC}"

    # Hand off to Claude Code. Restricted to read/edit/search — no Bash.
    claude -p \
        "Read ${DIAGNOSTIC}. Diagnose the failure, edit only the file it names, and exit. Do not run any commands." \
        --allowed-tools Read,Edit,Grep,Glob

    # Checkpoint the edit so every attempt is revertable.
    if [[ ${IS_GIT} -eq 1 ]]; then
        git -C "${REPO_ROOT}" add -A scout/ app/ 2>/dev/null || true
        git -C "${REPO_ROOT}" commit -m "eval_loop: ${CASE} attempt ${i}" --allow-empty >/dev/null
    fi

    echo -e "${BOLD}restarting ${SERVICE}...${NC}"
    docker compose restart "${SERVICE}" >/dev/null
    # API needs a moment to re-wire contexts on lifespan.
    sleep 6
done

echo -e "\n${RED}${BOLD}FAILED after ${MAX_ATTEMPTS} attempts${NC}"
echo "last diagnostic: ${DIAGNOSTIC}"
[[ ${IS_GIT} -eq 1 ]] && echo "revert: git log --oneline | grep 'eval_loop: ${CASE}'"
exit 1
