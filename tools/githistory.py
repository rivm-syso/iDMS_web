import argparse
import datetime
import re
import subprocess
from pathlib import Path


def get_remote_project_path() -> str:
    """Extracts the 'namespace/project' path from the git remote URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Match git@gitlab.example.com:group/project.git or https://gitlab.example.com/group/project.git
        match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
        if match:
            return match.group(1)
    except subprocess.CalledProcessError:
        pass
    return ""


def get_latest_non_merge_commits(
    count: int = 10,
    gitlab_base_url: str = "https://gitlab.example.com",
    project_path: str = "",
) -> list[dict]:
    """Retrieves standard commits and generates GitLab commit URLs.

    Args:
        count: Number of commits to retrieve.
        gitlab_base_url: Base URL of the GitLab instance.
        project_path: Group/project path (e.g., 'team/my-repo').

    Returns:
        List of dictionaries with commit metadata and GitLab URL.
    """
    # Clean up base URL
    gitlab_base_url = gitlab_base_url.rstrip("/")

    # Try auto-detecting project path if not specified
    if not project_path:
        project_path = get_remote_project_path()

    git_format = "%H%x1f%an <%ae>%x1f%ad%x1f%B%x1e"

    cmd = [
        "git",
        "log",
        "--no-merges",
        f"-n{count}",
        f"--format={git_format}",
        "--date=iso-strict",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, encoding="utf-8"
        )
    except subprocess.CalledProcessError as err:
        raise RuntimeError(f"Git command failed: {err.stderr}") from err
    except FileNotFoundError:
        raise RuntimeError(
            "Git is not installed or not available in system PATH."
        )

    raw_data = result.stdout.strip("\n\x1e")
    if not raw_data:
        return []

    commits = []
    records = raw_data.split("\x1e")

    for record in records:
        record = record.strip()
        if not record:
            continue

        parts = record.split("\x1f")
        if len(parts) == 4:
            commit_hash, author, date_str, message = parts

            # Standard GitLab commit URL format:
            # https://gitlab.domain.com/<namespace>/<project>/-/commit/<hash>
            if project_path:
                url = f"{gitlab_base_url}/{project_path}/-/commit/{commit_hash}"
            else:
                url = f"{gitlab_base_url}/-/commit/{commit_hash}"

            commits.append(
                {
                    "commit": commit_hash,
                    "author": author,
                    "date": date_str,
                    "message": message.strip(),
                    "url": url,
                }
            )

    return commits


def save_commits_to_py_file(commits: list[dict], output_path: Path) -> None:
    """Saves the commit list data structure into a Python file."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = f'"""Auto-generated commits data generated on {timestamp}."""\n\n'
    content += f"COMMITS = {repr(commits)}\n"

    output_path.write_text(content, encoding="utf-8")
    print(f"Successfully saved {len(commits)} commits to '{output_path}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract non-merge Git commits with GitLab URLs into a Python file."
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=10,
        help="Number of non-merge commits to retrieve (default: 10)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("commits_data.py"),
        help="Output Python file path (default: commits_data.py)",
    )
    parser.add_argument(
        "--gitlab-url",
        type=str,
        default="https://gitlab.com",
        help="Base URL of your GitLab instance (default: https://gitlab.com)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="",
        help="GitLab project path e.g. 'org/repository' (auto-detected from remote if empty)",
    )

    args = parser.parse_args()

    commit_data = get_latest_non_merge_commits(
        count=args.count,
        gitlab_base_url=args.gitlab_url,
        project_path=args.project,
    )
    save_commits_to_py_file(commit_data, args.output)


if __name__ == "__main__":
    main()