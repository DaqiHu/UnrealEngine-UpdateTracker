# main.py
# This script will contain the core logic for checking Unreal Engine updates.
from __future__ import annotations
import abc
import os
import re
import sys
import time
import requests
from github import Github, Auth
from github.GithubException import UnknownObjectException
from google import genai
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UE_REPO_NAME = "EpicGames/UnrealEngine" # Target repository
raw_limit = os.environ.get("COMMIT_SCAN_LIMIT") # Keep for manual override
COMMIT_SCAN_LIMIT = int(raw_limit) if raw_limit and raw_limit.isdigit() else None

# Timeout (seconds) for outbound HTTP calls (GitHub GraphQL, Slack, Discord).
REQUEST_TIMEOUT = 30

FEATURE_SIGNATURES = {
    "Lumen": {
        "path_patterns": ["Runtime/Renderer/Private/Lumen"],
    },
    "Nanite": {
        "path_patterns": [
            "Runtime/Renderer/Private/Nanite",
            "Runtime/Engine/Private/Nanite",
        ],
    },
    "VSM": {
        "path_patterns": ["Runtime/Renderer/Private/VirtualShadowMaps"],
    },
    "VT": {
        "path_patterns": ["Runtime/Renderer/Private/VT"],
    },
    "Toon Shading": {
        "keywords": ["toon", "cel shading", "npr"],
    },
    "Animation": {
        "path_patterns": [
            "Runtime/Engine/Private/Animation",
            "Runtime/AnimationCore",
            "Runtime/AnimGraphRuntime",
            "Runtime/Experimental/Animation",
            "Plugins/Animation",
        ],
    },
    "UAF": {
        "keywords": ["uaf", "unreal animation framework", "animation framework"],
    },
    "Mover": {
        "path_patterns": [
            "Plugins/Experimental/Mover/Source/Mover",
            "Plugins/Experimental/ChaosMover/Source/ChaosMover",
            "Plugins/Experimental/MoverAnimNext/Source/MoverAnimNext",
        ],
    },
    "Level Streaming": {
        "path_patterns": [
            "Runtime/Engine/Private/Streaming",
            "Runtime/Engine/Private/LevelInstance",
        ],
    },
    "World Partition": {
        "path_patterns": [
            "Runtime/Engine/Private/WorldPartition",
            "Runtime/Engine/Private/ActorPartition",
            "Runtime/Engine/Private/ISMPartition",
            "Runtime/Engine/Private/PackedLevelActor",
        ],
    },
    "Chaos Physics": {
        "path_patterns": [
            "Runtime/Experimental/Chaos",
            "Runtime/Experimental/ChaosCore",
            "Runtime/Experimental/ChaosSolverEngine",
            "Runtime/Experimental/ChaosVehicles",
            "Runtime/Experimental/ChaosVisualDebugger",
        ],
    },
    "Geometry Collection": {
        "path_patterns": ["Runtime/Experimental/GeometryCollectionEngine"],
    },
    "Landscape": {
        "path_patterns": ["Runtime/Landscape"],
    },
    "Dynamic Mesh": {
        "path_patterns": [
            "Runtime/GeometryFramework",
            "Runtime/GeometryCore",
            "Runtime/MeshDescription",
            "Runtime/MeshConversion",
        ],
    },
    "PCG": {
        "path_patterns": [
            "Plugins/PCG/Source/PCG",
            "Plugins/PCG/Source/PCGCompute",
        ],
    },
    "Instanced Skinned Mesh": {
        "path_patterns": [
            "Runtime/Engine/Private/InstancedSkinnedMesh",
            "Runtime/Engine/Public/InstancedSkinnedMesh",
            "Runtime/Engine/Classes/Components/InstancedSkinnedMeshComponent",
        ],
    },
    "Mesh Paint": {
        "path_patterns": [
            "Plugins/MeshPainting/Source/MeshPaintEditorMode",
            "Plugins/MeshPainting/Source/MeshPaintingToolset",
        ],
    },
    "Ray Tracing": {
        "path_patterns": ["Runtime/Renderer/Private/RayTracing"],
    },
    "Substrate": {
        "path_patterns": ["Runtime/Renderer/Private/Substrate"],
    },
    "Niagara": {
        "path_patterns": [
            "Plugins/FX/Niagara/Source/Niagara",
            "Plugins/FX/Niagara/Source/NiagaraCore",
            "Plugins/FX/Niagara/Source/NiagaraShader",
            "Plugins/FX/Niagara/Source/NiagaraVertexFactories",
        ],
    },
    "PSO": {
        "keywords": ["pso", "pipeline state", "pso precache", "pipeline state object"],
        "path_patterns": [
            "Runtime/Engine/Private/PSO",
            "Runtime/Engine/Public/PSO",
            "Runtime/D3D12RHI/Private/D3D12PipelineState",
        ],
    },
    "Bindless": {
        "keywords": ["bindless", "bindless render", "bindless descriptor"],
        "path_patterns": [
            "Runtime/D3D12RHI/Private/D3D12Bindless",
            "Runtime/VulkanRHI/Private/VulkanBindless",
            "Runtime/Apple/MetalRHI/Private/MetalBindless",
        ],
    },
    "MegaLights": {
        "path_patterns": ["Runtime/Renderer/Private/MegaLights"],
    },
    "Physics Assets": {
        "keywords": ["physics asset", "physicsasset", "body setup", "skeletal body"],
        "path_patterns": ["Runtime/Engine/Private/PhysicsEngine/PhysicsAsset"],
    },
    "Resimulation": {
        "keywords": ["resim", "resimulation", "evolution resim", "resim cache"],
        "path_patterns": ["Runtime/Experimental/Chaos/Private/Chaos/EvolutionResimCache"],
    },
}


class AIProvider(abc.ABC):
    """Abstract base for AI model providers."""

    @abc.abstractmethod
    def generate(self, model: str, prompt: str) -> str:
        ...

    @abc.abstractmethod
    def name(self) -> str:
        ...


class GeminiProvider(AIProvider):
    """Google Gemini via google.genai SDK."""

    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)

    def generate(self, model: str, prompt: str) -> str:
        response = self._client.models.generate_content(model=model, contents=prompt)
        return response.text

    def name(self) -> str:
        return "Gemini"


class DeepSeekProvider(AIProvider):
    """DeepSeek via OpenAI-compatible API.
    Activated by setting AI_PROVIDER=deepseek and DEEPSEEK_API_KEY."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://api.deepseek.com/v1"

    def generate(self, model: str, prompt: str) -> str:
        resp = requests.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def name(self) -> str:
        return "DeepSeek"


def create_ai_provider() -> tuple[AIProvider | None, str]:
    """Factory: reads AI_PROVIDER env and returns (provider, default_model) or (None, '')."""
    provider_name = os.environ.get("AI_PROVIDER", "deepseek").strip().lower()

    if provider_name == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("FATAL: GEMINI_API_KEY environment variable not set.")
            return None, ""
        return GeminiProvider(api_key), "gemini-2.5-pro"

    if provider_name == "deepseek":
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("FATAL: DEEPSEEK_API_KEY environment variable not set.")
            return None, ""
        return DeepSeekProvider(api_key), "deepseek-v4-flash"

    print(f"FATAL: Unknown AI_PROVIDER '{provider_name}'. Supported: gemini, deepseek")
    return None, ""


def tag_commit_features(commit):
    """Returns the set of tracked features this commit relates to."""
    msg = commit.commit.message.lower()
    paths = [f.filename for f in commit.files]
    matched = set()
    for feature, sig in FEATURE_SIGNATURES.items():
        kw = sig.get("keywords", [])
        pats = sig.get("path_patterns", [])
        if any(k in msg for k in kw):
            matched.add(feature)
            continue
        if any(any(p in path for p in pats) for path in paths):
            matched.add(feature)
    return matched


def get_target_branches():
    """Returns the list of (label, branch) pairs to track.

    Reads UE_BRANCHES (comma-separated, e.g. "ue5-main,ue6-main"). Falls back to
    the legacy single UE_BRANCH for backward compatibility, then to a default of
    both ue5-main and ue6-main. The label is derived from the first '-'-delimited
    segment, uppercased (ue5-main -> UE5, ue6-main -> UE6).
    """
    raw = os.environ.get("UE_BRANCHES") or os.environ.get("UE_BRANCH") or "ue5-main,ue6-main"
    branches = [b.strip() for b in raw.split(",") if b.strip()]
    return [(branch.split("-")[0].upper(), branch) for branch in branches]


def fetch_new_commits(github_client, branch):
    """
    Fetches new commits from the UE repo for the given branch.
    - If COMMIT_SCAN_LIMIT is set (manual run), it fetches that many recent commits.
    - Otherwise (scheduled run), it fetches commits from the last 24 hours.
    """
    print(f"Fetching commits from {UE_REPO_NAME} on branch {branch}...")
    try:
        repo = github_client.get_repo(UE_REPO_NAME)
        print("Successfully accessed repository.")

        if COMMIT_SCAN_LIMIT:
            print(f"Manual override: Fetching the latest {COMMIT_SCAN_LIMIT} commits from branch '{branch}'.")
            commits = repo.get_commits(sha=branch)
            new_commits = list(commits[:COMMIT_SCAN_LIMIT])
            new_commits.reverse() # Oldest to newest
        else:
            since_time = datetime.now(timezone.utc) - timedelta(hours=24)
            print(f"Scheduled run: Fetching commits from branch '{branch}' since {since_time.isoformat()} UTC...")
            commits = repo.get_commits(sha=branch, since=since_time)
            new_commits = list(commits)
            # Commits from .get_commits(since=...) are already in chronological order.

        print(f"Found {len(new_commits)} new commits.")
        return new_commits

    except UnknownObjectException:
        print(f"Error: Repository '{UE_REPO_NAME}' not found. Check PAT permissions.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching commits: {e}")
        return None


def filter_commit(commit):
    """
    Performs primary filtering to exclude obviously unimportant commits.
    Returns True if the commit is potentially important, False otherwise.
    """
    features = tag_commit_features(commit)
    if features:
        return True

    commit_message = commit.commit.message.lower()
    # commit.files is a PaginatedList; materialize it once so we don't trigger a
    # fresh paginated API fetch on every check below. (PaginatedList also has no
    # __bool__/__len__, so `not commit.files` would always be False.)
    files = list(commit.files)
    # Ignore merge/empty commits with no file changes
    if not files:
        return False
    # Ignore commits that only touch documentation
    if all(f.filename.startswith("Documentation/") for f in files):
        return False
    # Ignore localization-only changes
    if all("Localization/" in f.filename for f in files):
        return False
    # Ignore simple typo fixes
    if "typo" in commit_message and len(files) == 1:
        return False
    return True


def analyze_commits_in_bulk(ai_provider: AIProvider, model_name: str, commits, report_language: str = "Japanese") -> str | None:
    """
    Analyzes a list of commits in bulk with the AI provider and returns a formatted Markdown report.
    """
    print(f"Aggregating {len(commits)} commits for bulk analysis...")
    
    commits_data = []
    for commit in commits:
        tags = tag_commit_features(commit)
        tag_str = ", ".join(sorted(tags)) if tags else "(none)"
        file_list = "\n".join([f"- {file.filename}" for file in commit.files])
        commit_info = f"""---
Commit: {commit.sha[:7]}
URL: {commit.html_url}
Tags: {tag_str}
Message:
{commit.commit.message}
Files Changed:
{file_list}
"""
        commits_data.append(commit_info)
    
    aggregated_commits = "\n".join(commits_data)

    feature_names = sorted(FEATURE_SIGNATURES.keys())
    feature_focus = (
        "**Tracked Feature Areas:** " + ", ".join(feature_names) + "\n\n"
        "Each commit has a `Tags:` field indicating which tracked feature(s) it belongs to. "
        "Use these tags to:\n"
        "1. Build the ## FeatureName per-feature sections — all tagged commits of a feature go under its own `## FeatureName` section, grouped by change topic.\n"
        "2. Populate ### Feature Highlights — one bullet per affected feature with the representative commit hash.\n"
        "3. Only commits **without** tracked feature tags go into standard categories (## New Features, ## Major Changes, etc.).\n\n"
        "If a tracked feature has no notable changes, omit its `##` section entirely."
    )

    try:
        with open("prompts/report_prompt.md", "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        prompt = prompt_template.format(
            report_language=report_language,
            feature_focus=feature_focus,
            aggregated_commits=aggregated_commits
        )

        print(f"  > Sending aggregated prompt to {ai_provider.name()} for {len(commits)} commits (Language: {report_language})...")
        print(f"  > Tracked features: {len(feature_names)}")

        response = ai_provider.generate(model=model_name, prompt=prompt)
        
        print(f"--- BULK RESPONSE ---\n{response}\n--------------------\n")
        print(f"  < Received bulk response from {ai_provider.name()}.")
        
        return response

    except FileNotFoundError:
        print("FATAL: prompts/report_prompt.md not found.")
        return None
    except Exception as e:
        print(f"Error analyzing commits in bulk with AI: {e}")
        return None


def _run_graphql_query(query, variables, pat):
    """A helper function to run a GraphQL query."""
    headers = {"Authorization": f"bearer {pat}"}
    response = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, 'variables': variables},
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code == 200:
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL query failed: {result['errors']}")
        return result
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")

def get_repository_and_category_ids(repo_name, pat, category_name="Daily Reports"):
    """Gets the repository and discussion category IDs using the GraphQL API."""
    owner, name = repo_name.split('/')
    query = """
    query GetRepoAndCategory($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        discussionCategories(first: 10) {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    variables = {"owner": owner, "name": name}
    result = _run_graphql_query(query, variables, pat)
    
    repo_id = result["data"]["repository"]["id"]
    category_id = None
    for category in result["data"]["repository"]["discussionCategories"]["nodes"]:
        if category["name"] == category_name:
            category_id = category["id"]
            break
            
    if not category_id:
        # Fallback to the first category if the named one isn't found
        categories = result["data"]["repository"]["discussionCategories"]["nodes"]
        if categories:
            fallback_category = categories[0]
            category_id = fallback_category["id"]
            print(f"Warning: Discussion category '{category_name}' not found. Falling back to '{fallback_category['name']}'.")
        else:
            raise Exception(f"No discussion categories found in the repository.")
        
    return repo_id, category_id

def create_discussion(repo_name, title, body, pat, category_name="Daily Reports"):
    """Creates a new GitHub Discussion using the GraphQL API."""
    print("---")
    print("Creating GitHub Discussion via GraphQL...")
    try:
        repo_id, category_id = get_repository_and_category_ids(repo_name, pat, category_name)
        print(f"Found Repository ID: {repo_id}")
        print(f"Found Category ID: {category_id} for category '{category_name}'")

        mutation_query = """
        mutation CreateDiscussion($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {
            repositoryId: $repoId,
            categoryId: $categoryId,
            title: $title,
            body: $body
          }) {
            discussion {
              url
            }
          }
        }
        """
        variables = {
            "repoId": repo_id,
            "categoryId": category_id,
            "title": title,
            "body": body
        }

        result = _run_graphql_query(mutation_query, variables, pat)
        discussion_url = result["data"]["createDiscussion"]["discussion"]["url"]
        print(f"Successfully created GitHub Discussion: {discussion_url}")
        return True

    except Exception as e:
        print(f"An error occurred while creating discussion: {e}")
        return False


def _github_md_to_slack_mrkdwn(text):
    """Convert the GitHub-flavored Markdown report into Slack mrkdwn.

    Slack mrkdwn differs from GitHub Markdown: it has no '#' headers, uses
    *bold* (single asterisk), and links are <url|text> instead of [text](url).
    """
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Horizontal rule -> a visual separator (Slack mrkdwn has no '---' rule)
        if stripped in ("---", "***", "___"):
            lines.append("───────────────")
            continue
        # Headers (#, ##, ###...) -> a bold line
        m = re.match(r"^\s*#{1,6}\s+(.*)$", line)
        if m:
            lines.append(f"*{m.group(1).strip()}*")
            continue
        lines.append(line)
    converted = "\n".join(lines)
    # [text](url) -> <url|text>
    converted = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"<\2|\1>", converted)
    # **bold** -> *bold*
    converted = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", converted)
    return converted


def _chunk_text(text, limit):
    """Split text into <=limit-char chunks at line boundaries.

    Used by both Slack (section text fields capped at 3000 chars) and Discord
    (embed descriptions capped at 4096 chars); callers pass an appropriate limit
    with a safety margin. A single over-long line is hard-split as a last resort.
    """
    chunks = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\n" + line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def send_slack_notification(webhook_url, channel, message_text, title):
    """Sends a notification to a Slack channel via a webhook.

    The full report can easily exceed Slack's 3000-char per-section limit, so we
    convert it to mrkdwn and split it across multiple 'section' blocks.
    """
    print("---")
    print("Sending Slack notification...")
    try:
        chunks = _chunk_text(_github_md_to_slack_mrkdwn(message_text), 2900)

        # Slack allows at most 50 blocks per message. Reserve room for the header,
        # the divider, and (when truncating) the truncation notice, so the total
        # stays <= 50: 47 sections + header + divider + notice = 50.
        MAX_SECTION_BLOCKS = 47
        truncated = len(chunks) > MAX_SECTION_BLOCKS
        if truncated:
            chunks = chunks[:MAX_SECTION_BLOCKS]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title[:150], "emoji": True}
            },
            {"type": "divider"},
        ]
        for chunk in chunks:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
        if truncated:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "_… (message truncated)_"}})

        payload = {
            "channel": channel,
            "username": "UE Update Tracker",
            "icon_emoji": ":robot_face:",
            "text": f"*{title}*", # Fallback text for notifications
            "blocks": blocks
        }

        response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status() # Raise an exception for bad status codes
        print("Successfully sent Slack notification.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while sending Slack notification: {e}")
        return False


def _post_discord_message(webhook_url, payload):
    """POST a single Discord webhook message, honoring 429 rate limits.

    Discord returns 429 with a Retry-After header (seconds) when rate limited;
    we wait and retry once. Returns True on success, False otherwise.
    """
    for attempt in range(2):
        response = requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 429 and attempt == 0:
            retry_after = response.headers.get("Retry-After", "1")
            try:
                wait = float(retry_after)
            except ValueError:
                wait = 1.0
            print(f"  Discord rate limited (429). Waiting {wait}s before retry...")
            time.sleep(min(wait, 30))
            continue
        response.raise_for_status()
        return True
    return False


def send_discord_notification(webhook_url, message_text, title):
    """Sends a notification to a Discord channel via a webhook.

    The full report can exceed Discord's 4096-char embed description limit, so we
    split it across multiple sequential messages. Returns True only if every
    chunk posts successfully, so a partially-delivered report is not silently
    reported as success.
    """
    print("---")
    print("Sending Discord notification...")
    # 3900 keeps a margin under the 4096 embed-description limit, leaving room for
    # the truncation notice appended to the final chunk when we hit the cap.
    chunks = _chunk_text(message_text, 3900)

    # Cap the number of messages to avoid flooding the channel; mark truncation
    # on the last message, mirroring the Slack section cap.
    MAX_MESSAGES = 10
    truncated = len(chunks) > MAX_MESSAGES
    if truncated:
        chunks = chunks[:MAX_MESSAGES]
        chunks[-1] = chunks[-1] + "\n\n… (message truncated)"

    total = len(chunks)
    all_ok = True
    for i, chunk in enumerate(chunks, start=1):
        embed_title = title if i == 1 else f"{title} ({i}/{total})"
        payload = {
            "username": "UE Update Tracker",
            "avatar_url": "https://i.imgur.com/4M34hi2.png", # A simple robot icon
            "embeds": [
                {
                    "title": embed_title,
                    "description": chunk,
                    "color": 3447003,  # A nice blue color, hex #3498db
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        try:
            if _post_discord_message(webhook_url, payload):
                # Small delay between sequential posts to ease webhook rate limits.
                if i < total:
                    time.sleep(0.5)
            else:
                all_ok = False
                print(f"  Failed to send Discord message {i}/{total}.")
        except requests.exceptions.RequestException as e:
            all_ok = False
            print(f"  An error occurred while sending Discord message {i}/{total}: {e}")

    if all_ok:
        print(f"Successfully sent Discord notification ({total} message(s)).")
    else:
        print("Discord notification incomplete: one or more messages failed.")
    return all_ok

def process_branch(github_client, ai_provider, branch, label, model_name, report_language):
    """Fetch, filter, and analyze commits for a single branch.

    Returns a dict {label, branch, status, body, shas} where status is one of:
      - "ok":    body holds the generated Markdown report
      - "empty": no important commits after filtering (nothing to report)
      - "error": fetch failed or the AI returned no content
    Failures are returned (not raised) so the caller can isolate one branch's
    problem and still report the others.
    """
    new_commits = fetch_new_commits(github_client, branch)
    if new_commits is None:
        print(f"Failed to fetch commits for branch '{branch}'.")
        return {"label": label, "branch": branch, "status": "error", "body": None, "shas": []}
    if not new_commits:
        print(f"No new commits found for branch '{branch}'.")
        return {"label": label, "branch": branch, "status": "empty", "body": None, "shas": []}

    important_commits = [commit for commit in new_commits if filter_commit(commit)]
    if not important_commits:
        print(f"No potentially important commits found after filtering for branch '{branch}'.")
        return {"label": label, "branch": branch, "status": "empty", "body": None, "shas": []}

    print(f"Found {len(important_commits)} potentially important commits to analyze for '{branch}'.")
    shas = [commit.sha for commit in important_commits]
    report_body = analyze_commits_in_bulk(ai_provider, model_name, important_commits, report_language)
    if not report_body:
        print(f"Failed to generate report from AI for branch '{branch}'.")
        return {"label": label, "branch": branch, "status": "error", "body": None, "shas": shas}

    return {"label": label, "branch": branch, "status": "ok", "body": report_body, "shas": shas}


def _warn_duplicate_shas(branch_results):
    """Log a warning when the same commit appears on more than one branch.

    UE branches share history, so a cherry-picked/merged commit can land in two
    branches' windows and be summarized twice. We only surface this (no dedupe),
    since deciding which branch 'owns' a shared commit is out of scope.
    """
    seen = {}
    for result in branch_results:
        for sha in result.get("shas", []):
            seen.setdefault(sha, []).append(result["label"])
    dups = {sha: labels for sha, labels in seen.items() if len(labels) > 1}
    if dups:
        print(f"Warning: {len(dups)} commit(s) appear on multiple tracked branches "
              f"(reported per-branch, not de-duplicated):")
        for sha, labels in list(dups.items())[:20]:
            print(f"  {sha[:7]}: {', '.join(labels)}")


def _build_combined_report(branch_results, report_language):
    """Concatenate per-branch reports into one document, each under an H2 header.

    'ok' branches contribute their generated report; 'empty' and 'error' branches
    get a short localized placeholder so readers know the branch was checked.
    """
    is_ja = ("japan" in report_language.lower()) or ("日本" in report_language)
    no_update = "_本日の注目すべき更新はありません。_" if is_ja else "_No notable updates today._"
    failed_note = "_⚠️ レポート生成に失敗しました。_" if is_ja else "_⚠️ Failed to generate the report._"

    sections = []
    for result in branch_results:
        header = f"## {result['label']} ({result['branch']})"
        if result["status"] == "ok":
            body = result["body"].strip()
        elif result["status"] == "empty":
            body = no_update
        else:
            body = failed_note
        sections.append(f"{header}\n\n{body}")
    return "\n\n---\n\n".join(sections)


def main():
    """
    Main function to execute the update check.
    """
    print("=============================================")
    print("Starting Unreal Engine Update Check Script")
    print("=============================================")
    
    # --- API Setup ---
    print("\n--- 1. Setting up APIs ---")
    pat = os.environ.get("UE_REPO_PAT")
    
    if not pat:
        print("FATAL: UE_REPO_PAT environment variable not set.")
        sys.exit(1)
    print("UE_REPO_PAT found.")
    
    try:
        print("Initializing GitHub client...")
        github_client = Github(auth=Auth.Token(pat))
        print("GitHub client initialized.")

        ai_provider, default_model = create_ai_provider()
        if ai_provider is None:
            return

        model_name = os.environ.get("AI_MODEL") or os.environ.get("GEMINI_MODEL") or default_model
        print(f"AI provider: {ai_provider.name()}, model: {model_name}")
    except Exception as e:
        print(f"FATAL: Failed to initialize APIs: {e}")
        sys.exit(1)

    # --- Notification Target Check ---
    print("\n--- 2. Checking Notification Targets ---")
    discussion_repo_name = os.environ.get("DISCUSSION_REPO")
    discussion_repo_pat = os.environ.get("DISCUSSION_REPO_PAT")
    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    slack_channel = os.environ.get("SLACK_CHANNEL")
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    has_discussion_target = discussion_repo_name and discussion_repo_pat
    has_slack_target = slack_webhook_url and slack_channel
    has_discord_target = discord_webhook_url

    # A discussion repo without a PAT silently posts nowhere — warn explicitly.
    # (We intentionally do NOT fall back to GITHUB_TOKEN: that would auto-post to
    # the current repo, risking a leak if it is public. Discussion posting is
    # opt-in via DISCUSSION_REPO_PAT on a private repo.)
    if discussion_repo_name and not discussion_repo_pat:
        print("Warning: DISCUSSION_REPO is set but DISCUSSION_REPO_PAT is missing. "
              "GitHub Discussion posting will be skipped. Set DISCUSSION_REPO_PAT "
              "(a PAT with 'discussions: write' on a private repo) to enable it.")

    if not has_discussion_target and not has_slack_target and not has_discord_target:
        print("FATAL: No notification target is configured. Please set at least one of the following: DISCUSSION_REPO/DISCUSSION_REPO_PAT, SLACK_WEBHOOK_URL/SLACK_CHANNEL, or DISCORD_WEBHOOK_URL.")
        sys.exit(1)
    
    print("Notification target(s) configured correctly.")
    if has_discussion_target:
        print("- GitHub Discussion is enabled.")
    if has_slack_target:
        print("- Slack Notification is enabled.")
    if has_discord_target:
        print("- Discord Notification is enabled.")

    # --- Process Each Tracked Branch ---
    print("\n--- 3. Processing Tracked Branches ---")
    targets = get_target_branches()
    print(f"Tracking {len(targets)} branch(es): {', '.join(branch for _, branch in targets)}")

    report_language = os.environ.get("REPORT_LANGUAGE", "Japanese")
    print(f"Report language set to: {report_language}")

    branch_results = []
    for label, branch in targets:
        print(f"\n--- Branch: {label} ({branch}) ---")
        try:
            branch_results.append(
                process_branch(github_client, ai_provider, branch, label, model_name, report_language)
            )
        except Exception as e:
            # Isolate per-branch failures so one bad branch doesn't abort the rest.
            print(f"Unexpected error while processing branch '{branch}': {e}")
            branch_results.append({"label": label, "branch": branch, "status": "error", "body": None, "shas": []})

    # Surface (do not dedupe) commits shared across branches.
    _warn_duplicate_shas(branch_results)

    has_ok = any(r["status"] == "ok" for r in branch_results)
    has_error = any(r["status"] == "error" for r in branch_results)

    # All branches empty (and none errored): nothing worth reporting — exit quietly.
    if not has_ok and not has_error:
        print("\nNo important commits found on any tracked branch. Exiting.")
        return

    # --- Generate Report Title ---
    # Date the report in the configured timezone (defaults to JST) so the daily
    # title matches when readers receive it. time.strftime() uses the runner's
    # UTC clock, which dates the report a day behind for JST readers.
    report_tz = os.environ.get("REPORT_TIMEZONE", "Asia/Tokyo")
    try:
        report_date = datetime.now(ZoneInfo(report_tz)).strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Warning: invalid REPORT_TIMEZONE '{report_tz}' ({e}); falling back to UTC.")
        report_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    report_title = f"Unreal Engine Daily Report - {report_date}"

    # Track (target_name, success) so the workflow can fail if nothing posted.
    results = []

    # No branch produced content, but at least one errored: don't hide the
    # failure. Notify Slack/Discord (a Discussion needs a body) and fail the run.
    if not has_ok:
        failed = ", ".join(f"{r['label']} ({r['branch']})" for r in branch_results if r["status"] == "error")
        print(f"\nFailed to generate a report for all branches with commits: {failed}")
        error_message = f"Error: Failed to generate the Unreal Engine report for: {failed}."
        if has_slack_target:
            print("\n--- Handling Slack Notification for failure ---")
            results.append(("Slack", send_slack_notification(slack_webhook_url, slack_channel, error_message, report_title)))
        if has_discord_target:
            print("\n--- Handling Discord Notification for failure ---")
            results.append(("Discord", send_discord_notification(discord_webhook_url, error_message, report_title)))
        print("\n--- Delivery summary ---")
        for name, ok in results:
            print(f"  {'OK    ' if ok else 'FAILED'}: {name}")
        print("FATAL: report generation failed for all branches; no report was delivered.")
        sys.exit(1)

    # --- Build and Send the Combined Report ---
    print("\n--- 5. Generating and Sending Combined Report ---")
    report_body = _build_combined_report(branch_results, report_language)

    # --- 5a. Post to GitHub Discussion ---
    if has_discussion_target:
        print("\n--- 5a. Posting to GitHub Discussion ---")
        discussion_category = os.environ.get("DISCUSSION_CATEGORY", "Daily Reports")
        print(f"Attempting to post to repository '{discussion_repo_name}' in category: '{discussion_category}'")
        results.append(("GitHub Discussion", create_discussion(discussion_repo_name, report_title, report_body, discussion_repo_pat, category_name=discussion_category)))
    else:
        print("\n--- 5a. GitHub Discussion target not configured. Skipping. ---")

    # --- 5b. Post to Slack ---
    if has_slack_target:
        print("\n--- 5b. Posting to Slack ---")
        results.append(("Slack", send_slack_notification(slack_webhook_url, slack_channel, report_body, report_title)))
    else:
        print("\n--- 5b. Slack target not configured. Skipping. ---")

    # --- 5c. Post to Discord ---
    if has_discord_target:
        print("\n--- 5c. Posting to Discord ---")
        results.append(("Discord", send_discord_notification(discord_webhook_url, report_body, report_title)))
    else:
        print("\n--- 5c. Discord target not configured. Skipping. ---")

    # --- Delivery summary ---
    print("\n--- Delivery summary ---")
    for name, ok in results:
        print(f"  {'OK    ' if ok else 'FAILED'}: {name}")
    if results and not any(ok for _, ok in results):
        print("FATAL: all configured notification targets failed.")
        sys.exit(1)

    # --- Finish ---
    print("\n=============================================")
    print("Update Check Script Finished")
    print("=============================================")

if __name__ == "__main__":
    main()
