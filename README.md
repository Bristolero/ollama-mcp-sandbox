# MCP Learning Project

This project is a local MCP playground with two kinds of tools:

- SQL tools for a Dockerized Postgres demo database
- OS tools for simple local computer actions such as opening Steam

It also includes local Python agent runners that use a Hugging Face model to call the MCP tools through a small Node bridge.

## What is in this repo

- `docker-compose.yml`: starts Postgres 16
- `sql/init.sql`: creates demo tables and seed data
- `src/server.js`: starts the MCP server
- `src/sql-tools.js`: SQL-related MCP tools
- `src/os-tools.js`: OS-related MCP tools
- `src/mcp-client-cli.js`: small CLI bridge that lets the Python agent call MCP tools
- `agent/download_model.py`: downloads a Hugging Face model into `models/`
- `agent/local_qwen_agent.py`: recommended local text-model agent runner
- `agent/local_mistral_agent.py`: experimental local Mistral-family agent runner
- `prompts/agent-prompt.md`: prompt for database analysis
- `prompts/start_steam.md`: prompt for opening Steam
- `mcp-config.example.json`: example MCP host config

## MCP tools in this project

### SQL tools

- `list_tables`
- `describe_table`
- `sample_rows`
- `run_readonly_query`
- `insert_row`

### OS tools

- `open_steam`
- `open_steam_game`

## Recommended setup order

### 1. Install Node dependencies

If PowerShell blocks `npm`, use the Windows shim:

```powershell
cmd /c npm install
```

### 2. Create the database environment file

```powershell
Copy-Item .env.example .env
```

### 3. Start Postgres

```powershell
docker compose up -d
```

This creates a local database on `localhost:5432` and automatically loads `sql/init.sql`.

### 4. Create a Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 5. Install CUDA-enabled PyTorch

Use the official PyTorch installer for:

- Windows
- Pip
- CUDA

Official installer:

- https://pytorch.org/get-started/locally/

If you want a clean reinstall pattern in this project venv:

```powershell
python -m pip uninstall -y torch torchvision torchaudio
python -m pip cache purge
python -m pip install --index-url https://download.pytorch.org/whl/cu130 torch==2.10.0
```

Then verify GPU access:

```powershell
python -c "import torch; print({'torch': torch.__version__, 'cuda_available': torch.cuda.is_available(), 'cuda': torch.version.cuda, 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None})"
```

This project is text-first by default. Do not install `torchvision` unless a chosen model explicitly requires it.

### 6. Install the remaining Python packages

```powershell
python -m pip install -r requirements-agent.txt
```

## Recommended model path

The cleanest fit for this repo is a small text instruct model.

Recommended:

- `Qwen/Qwen3-4B-Instruct-2507`

Download it with:

```powershell
python agent/download_model.py --model-id Qwen/Qwen3-4B-Instruct-2507 --target-dir models/qwen3-4b-instruct-2507
```

If Hugging Face asks for authentication first:

```powershell
huggingface-cli login
```

## Start the MCP server

```powershell
cmd /c npm run start
```

## Run the local Qwen agent

For the database prompt:

```powershell
python agent/local_qwen_agent.py --prompt-file prompts/agent-prompt.md --max-steps 16
```

For the Steam prompt:

```powershell
python agent/local_qwen_agent.py --prompt-file prompts/start_steam.md --max-steps 8
```

## Direct MCP bridge commands

List available tools:

```powershell
node src/mcp-client-cli.js tools
```

Call a SQL tool directly:

```powershell
node src/mcp-client-cli.js call list_tables "{}"
```

Run a read-only SQL query:

```powershell
node src/mcp-client-cli.js call run_readonly_query "{\"sql\":\"select * from customers limit 3\"}"
```

Insert a customer:

```powershell
node src/mcp-client-cli.js call insert_row "{\"table_name\":\"customers\",\"values\":{\"full_name\":\"John Cena\",\"city\":\"West Newbury\",\"country\":\"United States\",\"segment\":\"Enterprise\"}}"
```

Open Steam:

```powershell
node src/mcp-client-cli.js call open_steam "{}"
```

## Prompts

### Database prompt

`prompts/agent-prompt.md` tells the agent to:

- inspect available tables
- inspect relevant schemas
- query the database
- answer the business questions from query results

### Steam prompt

`prompts/start_steam.md` tells the agent to:

- inspect available tools
- call `open_steam` if available
- return a short final confirmation

## How this project works

The local Python agent does not talk to Postgres or Windows directly.

Instead:

1. the Python model decides what to do
2. `src/mcp-client-cli.js` calls the MCP server
3. the MCP server executes the tool
4. the tool result is fed back into the model

That is the core MCP pattern: the model sees tools, not raw system access.

## Using it with another MCP host

If you want to use the server in another MCP-compatible host, use `mcp-config.example.json` as your starting point.

Typical flow:

1. register the server
2. reload the host
3. paste one of the prompt files
4. watch the host call the tools

## Notes

- `insert_row` writes real rows into the demo database
- `open_steam` is Windows-only
- `open_steam_game` expects a Steam app id
- `local_mistral_agent.py` is still in the repo, but `local_qwen_agent.py` is the cleaner path for this project

## OpenAI note

If you later want to use this with OpenAI through the Responses API, the current OpenAI docs say MCP servers are used through a `tools` entry of type `mcp`, and the server must be reachable over Streamable HTTP or HTTP/SSE on the public internet. This repo currently uses a local stdio MCP server, which is great for local learning and host integrations, but not a direct public API deployment shape.

Sources:

- https://platform.openai.com/docs/guides/tools-connectors-mcp?lang=javascript
- https://platform.openai.com/docs/mcp/
