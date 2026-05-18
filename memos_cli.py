#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
import argparse


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")


def _get_url_token():
    load_env()
    url = os.environ.get("MEMOS_API_URL", "https://memos.googig.cloud/api/v1/memos")
    token = os.environ.get("MEMOS_TOKEN")
    if not token:
        raise RuntimeError(
            "MEMOS_TOKEN is not set in the environment or .env file. "
            "Please create a .env file with MEMOS_TOKEN='your_token'"
        )
    return url, token


def _api_request(method, endpoint, payload=None):
    """Generic Memos API request.
    
    Args:
        method: HTTP method (POST, PATCH, DELETE)
        endpoint: Path appended to MEMOS_API_URL. Pass "" to use MEMOS_API_URL as-is.
                  MEMOS_API_URL already includes e.g. .../api/v1/memos, so:
                  - post_memo() passes ""  → posts to MEMOS_API_URL directly
                  - update_memo/delete_memo pass memo_id → appends /{memo_id}
        payload: Optional JSON body
    """
    base_url, token = _get_url_token()
    base_url = base_url.rstrip('/')
    if endpoint:
        full_url = f"{base_url}/{endpoint.lstrip('/')}"
    else:
        full_url = base_url
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Haber-Kuratör/3.1.0",
    }
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {endpoint} → HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        raise RuntimeError(f"{method} {endpoint} → {str(e)[:200]}")


def post_memo(content, tags=None, visibility="PUBLIC"):
    """Post a new memo to Memos."""
    _, _ = _get_url_token()
    if tags:
        content = f"{content}\n\n{tags}"
    payload = {"content": content, "visibility": visibility}
    try:
        result = _api_request("POST", "", payload)
        memo_name = result.get("name", "Unknown")
        print(f"Success! Memo published. ID: {memo_name}")
        return True
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error publishing memo: {str(e)}") from e


def update_memo(memo_id, content, tags=None, visibility="PUBLIC"):
    """Update an existing memo. memo_id is the UUID without 'memos/' prefix."""
    _, _ = _get_url_token()
    full_content = content
    if tags:
        full_content = f"{content}\n\n{tags}"
    payload = {"content": full_content}
    if visibility:
        payload["visibility"] = visibility
    try:
        result = _api_request("PATCH", memo_id, payload)
        print(f"Success! Memo updated. ID: memos/{memo_id}")
        return True
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error updating memo: {str(e)}") from e


def delete_memo(memo_id):
    """Delete a memo. memo_id is the UUID without 'memos/' prefix."""
    _, _ = _get_url_token()
    try:
        result = _api_request("DELETE", memo_id)
        print(f"Success! Memo deleted. ID: memos/{memo_id}")
        return True
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error deleting memo: {str(e)}") from e


def main():
    parser = argparse.ArgumentParser(description="memos-cli - Publish to Memos platform natively")
    parser.add_argument("action", choices=["post", "update", "delete", "reply"], help="Action to perform")
    parser.add_argument("content", help="The content of the memo to publish (or memo_id for update/delete)")
    parser.add_argument("--tags", help="Comma separated tags", default="")
    parser.add_argument("--visibility", help="Visibility (PUBLIC, PRIVATE, PROTECTED)", default="PUBLIC")
    parser.add_argument("--parent-id", help="Parent ID for reply action or memo ID for update", default="")
    args = parser.parse_args()

    if args.action == "delete":
        delete_memo(args.content)
        return

    if args.action == "update":
        memo_id = args.parent_id or input("Enter memo ID to update: ")
        if args.content and os.path.exists(args.content):
            with open(args.content, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = args.content
        update_memo(memo_id, content, args.tags, args.visibility)
        return

    # post / reply
    content = args.content
    if os.path.exists(content):
        with open(content, "r", encoding="utf-8") as f:
            content = f.read()
    if args.action == "reply":
        content = f"(Reply to {args.parent_id})\n\n{content}"
    post_memo(content, args.tags, args.visibility)


if __name__ == "__main__":
    main()
