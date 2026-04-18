# ===========================================================================
# Scout - Enterprise Context Agent
# ===========================================================================

FROM agnohq/python:3.12

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        git-lfs \
        openssh-client \
        ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Git configuration (safe defaults for agent use)
# ---------------------------------------------------------------------------
RUN git config --system init.defaultBranch main \
    && git config --system user.name "Scout" \
    && git config --system user.email "scout@agno.com" \
    && git config --system advice.detachedHead false \
    && git config --system --add safe.directory '*'

# ---------------------------------------------------------------------------
# GitHub token configuration
# ---------------------------------------------------------------------------
# The GITHUB_ACCESS_TOKEN env var is used for cloning private repos and GitHub API.
# Git credential helper stores it in memory (never written to disk).
# ---------------------------------------------------------------------------
RUN printf '%s\n' \
        '#!/bin/bash' \
        'if [ -n "$GITHUB_ACCESS_TOKEN" ]; then' \
        '    echo "protocol=https"' \
        '    echo "host=github.com"' \
        '    echo "username=x-access-token"' \
        '    echo "password=$GITHUB_ACCESS_TOKEN"' \
        'fi' \
        > /usr/local/bin/git-credential-scout \
    && chmod +x /usr/local/bin/git-credential-scout \
    && git config --system credential.helper '/usr/local/bin/git-credential-scout'

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
WORKDIR /app
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system
COPY . .
ENV PYTHONPATH=/app

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
RUN chmod +x /app/scripts/entrypoint.sh
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Default command (overridden by compose)
# ---------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
