from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib import error, request


DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
DEFAULT_BASE_MODEL = "qwen3:4b"
DEFAULT_TARGET_MODEL = "qwen/qwen3-4b-instruct-2507"


def api_request(base_url: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 1800) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama API error {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Make sure the Ollama container is running and reachable "
            f"at {base_url}."
        ) from exc


def list_model_names(base_url: str) -> set[str]:
    payload = api_request(base_url, "/api/tags")
    return {model["name"] for model in payload.get("models", [])}


def pull_model(base_url: str, model_name: str) -> None:
    print(f"Pulling base Ollama model: {model_name}", flush=True)
    api_request(
        base_url,
        "/api/pull",
        {
            "name": model_name,
            "stream": False,
        },
    )


def create_alias(base_url: str, base_model: str, target_model: str) -> None:
    print(f"Creating Ollama alias: {target_model} -> {base_model}", flush=True)
    api_request(
        base_url,
        "/api/create",
        {
            "model": target_model,
            "from": base_model,
            "stream": False,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the Ollama model used by the MCP agent.")
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Base URL for the Ollama HTTP API.",
    )
    parser.add_argument(
        "--base-model",
        default=DEFAULT_BASE_MODEL,
        help="Existing Ollama model to pull first.",
    )
    parser.add_argument(
        "--target-model",
        default=DEFAULT_TARGET_MODEL,
        help="Model name the agent should use.",
    )
    parser.add_argument(
        "--recreate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Recreate the target model alias even if it already exists.",
    )
    args = parser.parse_args()

    print(f"Ollama URL: {args.ollama_url}", flush=True)
    existing_models = list_model_names(args.ollama_url)

    if args.base_model not in existing_models:
        pull_model(args.ollama_url, args.base_model)
        existing_models = list_model_names(args.ollama_url)

    if args.base_model not in existing_models:
        raise RuntimeError(f"Base model was not found after pull: {args.base_model}")

    if args.target_model == args.base_model:
        print(f"Model ready: {args.target_model}", flush=True)
        return

    if args.recreate or args.target_model not in existing_models:
        create_alias(args.ollama_url, args.base_model, args.target_model)
    else:
        print(f"Alias already exists: {args.target_model}", flush=True)

    print(f"Model ready: {args.target_model}", flush=True)


if __name__ == "__main__":
    main()
