#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
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

def post_memo(content, tags=None, visibility="PUBLIC"):
    load_env()
    url = os.environ.get("MEMOS_API_URL", "https://memos.googig.cloud/api/v1/memos")
    token = os.environ.get("MEMOS_TOKEN")
    
    if not token:
        raise RuntimeError(
            "MEMOS_TOKEN is not set in the environment or .env file. "
            "Please create a .env file with MEMOS_TOKEN='your_token'"
        )
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": f"Haber-Kuratör/3.1.0",
    }

    if tags:
        content = f"{content}\n\n{tags}"

    payload = {
        "content": content,
        "visibility": visibility
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                res_data = json.loads(response.read().decode("utf-8"))
                memo_id = res_data.get("name", "Unknown ID")
                print(f"Success! Memo published. ID: {memo_id}")
                return True
            else:
                raise RuntimeError(f"Failed to publish: HTTP {response.status}")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Error publishing memo: {str(e)}") from e

def main():
    parser = argparse.ArgumentParser(description="memos-cli - Publish to Memos platform natively")
    parser.add_argument("action", choices=["post", "reply"], help="Action to perform")
    parser.add_argument("content", help="The content of the memo to publish")
    parser.add_argument("--tags", help="Comma separated tags", default="")
    parser.add_argument("--visibility", help="Visibility (PUBLIC, PRIVATE, PROTECTED)", default="PUBLIC")
    
    # Optional arguments for reply/image that are listed in the handoff
    parser.add_argument("--image", help="Path to image (not implemented yet)", default="")
    parser.add_argument("parent_id", nargs="?", help="Parent ID for reply action")
    
    args = parser.parse_args()
    
    content = args.content
    if os.path.exists(content):
        with open(content, "r", encoding="utf-8") as f:
            content = f.read()
            
    if args.action == "reply":
        # Usually Memos API appends to the parent or handles relation.
        # For simplicity in this CLI, we will just post it normally and prepend a reply indicator.
        content = f"(Reply to {args.parent_id})\n\n{content}"
        
    post_memo(content, args.tags, args.visibility)

if __name__ == "__main__":
    main()
