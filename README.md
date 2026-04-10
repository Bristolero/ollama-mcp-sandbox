# MCP Learning Project

This project is a local MCP playground with three moving parts:

- a Dockerized Postgres demo database
- a small Node MCP server plus CLI bridge
- a Python agent that uses Ollama over HTTP instead of loading Hugging Face models directly

The old in-process Hugging Face model flow has been replaced. The local agent now talks to an Ollama container, and Ollama is responsible for serving the Qwen model.

## Architecture

1. `docker compose` starts Postgres, Adminer, and Ollama
2. `src/server.js` exposes MCP tools over stdio
3. `src/mcp-client-cli.js` lets the Python agent call those tools
4. `agent/local_qwen_agent.py` sends chat requests to Ollama
5. the agent decides when to call MCP tools and uses their results to finish the task

That keeps model serving separate from the Python agent process and removes the old `transformers` + local model download path.

## What is in this repo

- `docker-compose.yml`: starts Postgres, Adminer, and Ollama
- `sql/init.sql`: creates demo tables and seed data
- `src/server.js`: starts the MCP server
- `src/sql-tools.js`: SQL-related MCP tools
- `src/os-tools.js`: OS-related MCP tools
- `src/mcp-client-cli.js`: small CLI bridge that lets the Python agent call MCP tools
- `agent/local_qwen_agent.py`: Ollama-backed local agent runner
- `agent/prepare_ollama_model.py`: pulls the base Ollama model and creates the project model alias
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

### 2. Start the containers

```powershell
docker compose up -d
```

This starts:

- Postgres on `localhost:5432`
- Adminer on `http://localhost:8080`
- Ollama on `http://localhost:11434`

### 3. Create a Python virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 4. Install Python requirements

The Ollama-backed agent uses only the Python standard library, so this is mostly a no-op but keeps the setup flow consistent:

```powershell
python -m pip install -r requirements-agent.txt
```

### 5. Prepare the Ollama model

```powershell
python agent/prepare_ollama_model.py
```

By default this does two things:

- pulls Ollama's `qwen3:4b`
- creates the project alias `qwen/qwen3-4b-instruct-2507`

The agent uses that alias by default so the project still targets the requested Qwen 4B setup while staying inside Ollama's model-serving workflow.

If you want to recreate the alias:

```powershell
python agent/prepare_ollama_model.py --recreate
```

If your Ollama server is not on the default host:

```powershell
python agent/prepare_ollama_model.py --ollama-url http://localhost:11434
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

If you want to point the agent at a different Ollama endpoint or model:

```powershell
python agent/local_qwen_agent.py --ollama-url http://localhost:11434 --model qwen/qwen3-4b-instruct-2507
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
- the Ollama model alias is created locally and stored in the Ollama volume

## References

- Ollama Docker image: https://hub.docker.com/r/ollama/ollama
- Ollama API docs: https://docs.ollama.com/api
