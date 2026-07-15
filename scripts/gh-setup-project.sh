#!/usr/bin/env bash
# Creates GitHub Project and links repo. Writes GH_PROJECT_NUM to .workflow-kit.env when possible.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

REPO="${1:-${GH_REPO:?Set GH_REPO}}"
REPO_OWNER="${REPO%%/*}"
PROJECT_TITLE="${GH_PROJECT_TITLE:-Project delivery}"

if ! gh auth status 2>&1 | grep -q 'project'; then
  echo "Missing 'project' scope. Run:"
  echo "  gh auth refresh -h github.com -s project,read:project"
  exit 1
fi

find_project() {
  local owner_id="$1"
  gh api graphql -f query='
query($owner: ID!, $title: String!) {
  node(id: $owner) {
    ... on User {
      projectsV2(first: 20, query: $title) { nodes { id title url number } }
    }
    ... on Organization {
      projectsV2(first: 20, query: $title) { nodes { id title url number } }
    }
  }
}' -f owner="$owner_id" -f title="$PROJECT_TITLE" \
    --jq '.data.node.projectsV2.nodes[] | select(.title=="'"$PROJECT_TITLE"'")' 2>/dev/null || true
}

REPO_OWNER_ID="$(gh api "repos/${REPO}" --jq '.owner.node_id')"
VIEWER_ID="$(gh api graphql -f query='{ viewer { id login } }' --jq '.data.viewer.id')"
VIEWER_LOGIN="$(gh api graphql -f query='{ viewer { login } }' --jq '.data.viewer.login')"

PROJECT_JSON="$(find_project "$REPO_OWNER_ID")"
PROJECT_OWNER="repo owner ($REPO_OWNER)"

if [[ -z "$PROJECT_JSON" ]]; then
  PROJECT_JSON="$(find_project "$VIEWER_ID")"
  [[ -n "$PROJECT_JSON" ]] && PROJECT_OWNER="your account ($VIEWER_LOGIN)"
fi

if [[ -z "$PROJECT_JSON" ]]; then
  CREATE_OWNER_ID="$REPO_OWNER_ID"
  PROJECT_OWNER="repo owner ($REPO_OWNER)"
  if ! CREATE_RESULT="$(gh api graphql -f query='
mutation($owner: ID!, $title: String!) {
  createProjectV2(input: {ownerId: $owner, title: $title}) {
    projectV2 { id url title number }
  }
}' -f owner="$CREATE_OWNER_ID" -f title="$PROJECT_TITLE" 2>/dev/null)"; then
    echo "Cannot create project on $REPO_OWNER (need admin). Creating under $VIEWER_LOGIN …"
    CREATE_OWNER_ID="$VIEWER_ID"
    PROJECT_OWNER="your account ($VIEWER_LOGIN)"
    CREATE_RESULT="$(gh api graphql -f query='
mutation($owner: ID!, $title: String!) {
  createProjectV2(input: {ownerId: $owner, title: $title}) {
    projectV2 { id url title number }
  }
}' -f owner="$CREATE_OWNER_ID" -f title="$PROJECT_TITLE")"
  fi
  PROJECT_JSON="$(echo "$CREATE_RESULT" | jq '.data.createProjectV2.projectV2')"
  echo "Created project under $PROJECT_OWNER"
else
  echo "Using existing project under $PROJECT_OWNER"
fi

PROJECT_ID="$(echo "$PROJECT_JSON" | jq -r '.id')"
PROJECT_NUM="$(echo "$PROJECT_JSON" | jq -r '.number')"
PROJECT_URL="$(echo "$PROJECT_JSON" | jq -r '.url')"

REPO_ID="$(gh api "repos/${REPO}" --jq '.node_id')"
if gh api graphql -f query='
mutation($projectId: ID!, $contentId: ID!) {
  linkProjectV2ToRepository(input: {projectId: $projectId, repositoryId: $contentId}) {
    repository { nameWithOwner }
  }
}' -f projectId="$PROJECT_ID" -f contentId="$REPO_ID" >/dev/null 2>&1; then
  echo "Linked repository $REPO to project."
else
  echo "Note: repository link skipped (project owner must match repo owner)."
fi

echo "Adding open issues to project …"
while IFS= read -r issue_id; do
  [[ -z "$issue_id" ]] && continue
  gh api graphql -f query='
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}' -f projectId="$PROJECT_ID" -f contentId="$issue_id" >/dev/null 2>&1 || true
done < <(gh issue list --repo "$REPO" --state open --json id --jq '.[].id')

# Persist project number
ENV_FILE="$ROOT/.workflow-kit.env"
if [[ -f "$ENV_FILE" ]]; then
  if grep -q '^GH_PROJECT_NUM=' "$ENV_FILE"; then
    sed -i.bak "s/^GH_PROJECT_NUM=.*/GH_PROJECT_NUM=$PROJECT_NUM/" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    echo "GH_PROJECT_NUM=$PROJECT_NUM" >>"$ENV_FILE"
  fi
else
  echo "GH_PROJECT_NUM=$PROJECT_NUM" >>"$ENV_FILE"
fi

echo ""
echo "Project: $PROJECT_URL (number $PROJECT_NUM)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -x "$SCRIPT_DIR/gh-ensure-project-status-qa.sh" ]]; then
  GH_PROJECT_NUM="$PROJECT_NUM" "$SCRIPT_DIR/gh-ensure-project-status-qa.sh" || true
fi

if [[ -x "$SCRIPT_DIR/gh-configure-project.sh" ]]; then
  echo ""
  echo "Running board configuration …"
  GH_PROJECT_NUM="$PROJECT_NUM" "$SCRIPT_DIR/gh-configure-project.sh" "$REPO"
fi
