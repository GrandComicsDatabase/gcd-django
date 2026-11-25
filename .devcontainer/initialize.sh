#!/usr/bin/env bash
# Runs on the host before Compose: never start or modify an existing project.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
workspace="$(pwd -P)"
if [[ -n "${COMPOSE_PROJECT_NAME:-}" ]]; then
    echo 'Unset COMPOSE_PROJECT_NAME before opening the Dev Container; it uses a checkout-specific project.' >&2
    exit 1
fi

# Git is already needed to clone the checkout. No host Python/Node is required.
project="gcd-editor-$(printf '%s' "$workspace" | git hash-object --stdin)"
project_file=.devcontainer/compose.project.yaml
if [[ -L "$project_file" ]]; then
    echo 'Refusing to overwrite a symlink at .devcontainer/compose.project.yaml.' >&2
    exit 1
fi
printf 'name: %s\n' "$project" > "$project_file"

# A root .env can override the generated name. Inspect only; never rewrite the
# contributor's settings or silently attach to their ordinary Compose database.
effective_project="$(docker compose -f compose.yaml -f .devcontainer/compose.yaml \
    -f "$project_file" config | awk '$1 == "name:" && !/^ / { print $2 }')"
if [[ "$effective_project" != "$project" ]]; then
    echo 'Remove COMPOSE_PROJECT_NAME from this checkout .env before using the Dev Container (or use a separate clone).' >&2
    exit 1
fi
printf 'Dev Container project: %s\n' "$project"
