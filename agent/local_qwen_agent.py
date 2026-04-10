from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT_FILE = ROOT / "prompts" / "agent-prompt.md"
DEFAULT_OLLAMA_MODEL = "qwen/qwen3-4b-instruct-2507"
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


SYSTEM_PROMPT_TEMPLATE = """You are a local database agent powered by Qwen through Ollama.

You can use MCP tools through a bridge process.
You must solve the user's task by choosing exactly one action at a time.

Available tools:
{tool_catalog}

Rules:
- Start by understanding the database schema before making assumptions.
- Use tools when you need facts from the database.
- Never invent query results.
- If the user asks for SQL, include it in the final answer.
- Respond with exactly one JSON object and nothing else.

Valid response formats:
{{"action":"tool_call","tool_name":"list_tables","arguments":{{}}}}
{{"action":"tool_call","tool_name":"describe_table","arguments":{{"table_name":"orders"}}}}
{{"action":"final","answer":"your final answer here"}}
"""


def run_json_command(args: list[str]) -> Any:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def load_tool_catalog() -> str:
    payload = run_json_command(["node", "src/mcp-client-cli.js", "tools"])
    tools = payload.get("tools", [])
    lines = []

    for tool in tools:
        name = tool["name"]
        description = tool.get("description", "")
        input_schema = json.dumps(tool.get("inputSchema", {}), ensure_ascii=True)
        lines.append(f"- {name}: {description} | input_schema={input_schema}")

    return "\n".join(lines)


def ollama_request(base_url: str, path: str, payload: dict[str, Any], timeout: int = 600) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    api_request = request.Request(
        url=f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama API error {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(
            "Could not reach Ollama. Make sure the Ollama container is running and reachable "
            f"at {base_url}."
        ) from exc


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    normalized_texts = [text]

    repaired_text = text
    repaired_text = repaired_text.replace('"arguments:{}', '"arguments":{}')
    repaired_text = repaired_text.replace('"arguments:{', '"arguments":{')
    repaired_text = re.sub(r'"arguments\s*:\s*', '"arguments":', repaired_text)
    repaired_text = re.sub(r'"arguments:\s*', '"arguments":', repaired_text)

    if repaired_text != text:
        normalized_texts.append(repaired_text)

    final_prefix = '{"action": "final","answer":"'
    alt_final_prefix = '{"action":"final","answer":"'
    for prefix in (final_prefix, alt_final_prefix):
        if text.startswith(prefix):
            answer = text[len(prefix) :]
            answer = answer.replace('\\"', '"')
            answer = answer.replace("\\n", "\n")
            return {
                "action": "final",
                "answer": answer.strip(),
            }

    for candidate_text in normalized_texts:
        for index, char in enumerate(candidate_text):
            if char != "{":
                continue

            try:
                candidate, _end = decoder.raw_decode(candidate_text[index:])
            except json.JSONDecodeError:
                continue

            if isinstance(candidate, dict) and candidate.get("action") in {"tool_call", "final"}:
                return candidate

            if isinstance(candidate, dict) and candidate:
                return candidate

    raise ValueError(f"Model did not return JSON. Raw output:\n{text}")


def render_messages(system_prompt: str, user_task: str, transcript: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": user_task})
    messages.extend(transcript)
    return messages


def generate_action(
    ollama_url: str,
    model_name: str,
    system_prompt: str,
    user_task: str,
    transcript: list[dict[str, str]],
) -> dict[str, Any]:
    messages = render_messages(system_prompt, user_task, transcript)
    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }
    response = ollama_request(ollama_url, "/api/chat", payload)
    message = response.get("message", {})
    text = str(message.get("content", "")).strip()
    print("Raw model output:", flush=True)
    print(text, flush=True)
    return extract_json_object(text)


def call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    return run_json_command(
        [
            "node",
            "src/mcp-client-cli.js",
            "call",
            tool_name,
            json.dumps(arguments, ensure_ascii=True),
        ]
    )


def run_agent(
    ollama_url: str,
    model_name: str,
    task: str,
    max_steps: int,
) -> str:
    tool_catalog = load_tool_catalog()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_catalog=tool_catalog)
    print("Task received. Initializing agent...", flush=True)
    print(f"Ollama URL: {ollama_url}", flush=True)
    print(f"Ollama model: {model_name}", flush=True)
    transcript: list[dict[str, str]] = []

    for step in range(1, max_steps + 1):
        print(f"\n--- Step {step}/{max_steps} ---", flush=True)
        action = generate_action(
            ollama_url=ollama_url,
            model_name=model_name,
            system_prompt=system_prompt,
            user_task=task,
            transcript=transcript,
        )
        print(f"Parsed action: {json.dumps(action, ensure_ascii=True)}", flush=True)

        if action.get("action") == "final":
            return str(action.get("answer", "")).strip()

        if action.get("action") != "tool_call":
            transcript.append(
                {
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=True),
                }
            )
            transcript.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid. "
                        "Return exactly one JSON object with either "
                        "{\"action\":\"tool_call\",\"tool_name\":\"...\",\"arguments\":{...}} "
                        "or {\"action\":\"final\",\"answer\":\"...\"}. "
                        "Do not return an empty object."
                    ),
                }
            )
            print("Action invalid. Asking model to retry with exact JSON schema.", flush=True)
            continue

        tool_name = str(action.get("tool_name", "")).strip()
        arguments = action.get("arguments", {})

        if not tool_name or not isinstance(arguments, dict):
            transcript.append(
                {
                    "role": "assistant",
                    "content": json.dumps(action, ensure_ascii=True),
                }
            )
            transcript.append(
                {
                    "role": "user",
                    "content": (
                        "Your tool call was incomplete. "
                        "Return exactly one JSON object with a non-empty tool_name "
                        "and an arguments object."
                    ),
                }
            )
            print("Tool call incomplete. Asking model to retry with a complete tool call.", flush=True)
            continue

        print(f"Calling tool: {tool_name} with arguments {json.dumps(arguments, ensure_ascii=True)}", flush=True)
        tool_result = call_tool(tool_name, arguments)
        print("Tool result received.", flush=True)

        transcript.append(
            {
                "role": "assistant",
                "content": json.dumps(action, ensure_ascii=True),
            }
        )
        transcript.append(
            {
                "role": "user",
                "content": (
                    f"Tool result for {tool_name}:\n"
                    f"{json.dumps(tool_result, indent=2, ensure_ascii=True)}"
                ),
            }
        )

    raise RuntimeError("Agent reached the maximum number of tool steps without finishing.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Qwen agent against MCP tools through Ollama.")
    parser.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL,
        help="Ollama model name to use.",
    )
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Base URL for the Ollama HTTP API.",
    )
    parser.add_argument(
        "--prompt-file",
        default=str(DEFAULT_PROMPT_FILE),
        help="Markdown file containing the user task.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Maximum number of MCP tool turns before stopping.",
    )
    args = parser.parse_args()

    prompt_text = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    answer = run_agent(
        ollama_url=args.ollama_url,
        model_name=args.model,
        task=prompt_text,
        max_steps=args.max_steps,
    )
    print(answer)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr or str(error))
        raise
