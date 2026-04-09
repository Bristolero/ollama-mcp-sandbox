from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

try:
    from transformers import BitsAndBytesConfig
except ImportError:
    BitsAndBytesConfig = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = ROOT / "models" / "mistral-7b-instruct-v0.3"
DEFAULT_PROMPT_FILE = ROOT / "prompts" / "agent-prompt.md"


SYSTEM_PROMPT_TEMPLATE = """You are a local database agent powered by Mistral.

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


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()

    for index, char in enumerate(text):
        if char != "{":
            continue

        try:
            candidate, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue

        if isinstance(candidate, dict):
            return candidate

    raise ValueError(f"Model did not return JSON. Raw output:\n{text}")


def render_messages(system_prompt: str, user_task: str, transcript: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": user_task})
    messages.extend(transcript)
    return messages


def generate_action(
    processor: Any,
    model: Any,
    system_prompt: str,
    user_task: str,
    transcript: list[dict[str, str]],
    max_new_tokens: int,
    uses_multimodal_stack: bool,
) -> dict[str, Any]:
    messages = render_messages(system_prompt, user_task, transcript)

    if uses_multimodal_stack:
        mistral3_messages = []
        for message in messages:
            mistral3_messages.append(
                {
                    "role": message["role"],
                    "content": [
                        {
                            "type": "text",
                            "text": message["content"],
                        }
                    ],
                }
            )

        model_input_device = next(model.parameters()).device
        inputs = processor.apply_chat_template(
            mistral3_messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
        ).to(model_input_device)
    else:
        prompt = processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        model_input_device = next(model.parameters()).device
        inputs = processor(prompt, return_tensors="pt").to(model_input_device)

    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=processor.eos_token_id if hasattr(processor, "eos_token_id") else None,
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[-1] :]
    if uses_multimodal_stack:
        text = processor.batch_decode(generated_tokens.unsqueeze(0), skip_special_tokens=True)[0].strip()
    else:
        text = processor.decode(generated_tokens, skip_special_tokens=True).strip()
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


def choose_dtype() -> torch.dtype:
    if torch.cuda.is_available():
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return torch.float32


def build_model_kwargs(load_in_4bit: bool) -> dict[str, Any]:
    dtype = choose_dtype()

    model_kwargs: dict[str, Any] = {
        "torch_dtype": dtype,
        "low_cpu_mem_usage": True,
    }

    if torch.cuda.is_available():
        model_kwargs["device_map"] = "auto"

    if load_in_4bit:
        if not torch.cuda.is_available():
            raise RuntimeError("4-bit loading requires a CUDA-capable PyTorch install and visible GPU.")

        if BitsAndBytesConfig is None:
            raise RuntimeError(
                "4-bit loading requested, but BitsAndBytesConfig is unavailable. "
                "Install a compatible transformers/bitsandbytes stack first."
            )

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )

    return model_kwargs


def load_model(model_dir: Path, load_in_4bit: bool) -> tuple[Any, Any, bool]:
    config = AutoConfig.from_pretrained(str(model_dir))
    uses_multimodal_stack = config.model_type == "mistral3"

    if uses_multimodal_stack:
        if hasattr(config, "quantization_config"):
            delattr(config, "quantization_config")
        try:
            processor = AutoProcessor.from_pretrained(str(model_dir))
        except ImportError as error:
            raise RuntimeError(
                "This model uses the mistral3 multimodal stack and requires torchvision "
                "for its PixtralProcessor. Install a torchvision version that matches your "
                "current torch build, or switch to a text-only model."
            ) from error
    else:
        processor = AutoTokenizer.from_pretrained(str(model_dir))
        if processor.pad_token is None:
            processor.pad_token = processor.eos_token

    model_kwargs = build_model_kwargs(load_in_4bit=load_in_4bit)

    if uses_multimodal_stack:
        model = AutoModelForImageTextToText.from_pretrained(
            str(model_dir),
            config=config,
            **model_kwargs,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(str(model_dir), **model_kwargs)

    if not torch.cuda.is_available():
        print("No CUDA found!")
        model.to("cpu")

    return processor, model, uses_multimodal_stack


def run_agent(model_dir: Path, task: str, max_steps: int, max_new_tokens: int, load_in_4bit: bool) -> str:
    tool_catalog = load_tool_catalog()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_catalog=tool_catalog)
    print("Task received. Initializing model...", flush=True)
    print(f"Model directory: {model_dir}", flush=True)
    print(f"4-bit quantization enabled: {load_in_4bit}", flush=True)
    processor, model, uses_multimodal_stack = load_model(model_dir, load_in_4bit=load_in_4bit)
    transcript: list[dict[str, str]] = []

    for step in range(1, max_steps + 1):
        action = generate_action(
            processor=processor,
            model=model,
            system_prompt=system_prompt,
            user_task=task,
            transcript=transcript,
            max_new_tokens=max_new_tokens,
            uses_multimodal_stack=uses_multimodal_stack,
        )

        if action.get("action") == "final":
            return str(action.get("answer", "")).strip()

        if action.get("action") != "tool_call":
            raise ValueError(f"Unexpected action at step {step}: {action}")

        tool_name = str(action.get("tool_name", "")).strip()
        arguments = action.get("arguments", {})

        if not isinstance(arguments, dict):
            raise ValueError(f"Tool arguments must be an object. Received: {arguments}")

        tool_result = call_tool(tool_name, arguments)

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
    parser = argparse.ArgumentParser(description="Run a local Mistral agent against MCP tools.")
    parser.add_argument(
        "--model-dir",
        default=str(DEFAULT_MODEL_DIR),
        help="Path to the local model directory.",
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
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=256,
        help="Maximum tokens to generate for each step.",
    )
    parser.add_argument(
        "--load-in-4bit",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use 4-bit quantization when loading the model. Optional for smaller models, useful for tighter GPU memory limits.",
    )
    args = parser.parse_args()

    prompt_text = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    answer = run_agent(
        model_dir=Path(args.model_dir),
        task=prompt_text,
        max_steps=args.max_steps,
        max_new_tokens=args.max_new_tokens,
        load_in_4bit=args.load_in_4bit,
    )
    print(answer)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr or str(error))
        raise
