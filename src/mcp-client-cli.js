import "dotenv/config";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

function buildTransport() {
  return new StdioClientTransport({
    command: "node",
    args: ["src/server.js"],
    cwd: process.cwd(),
    env: {
      ...process.env
    },
    stderr: "inherit"
  });
}

async function withClient(fn) {
  const client = new Client({
    name: "mcp-postgres-cli",
    version: "1.0.0"
  });

  const transport = buildTransport();

  try {
    await client.connect(transport);
    await fn(client);
  } finally {
    await transport.close().catch(() => {});
  }
}

function printJson(value) {
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

async function main() {
  const [command, ...rest] = process.argv.slice(2);

  if (!command || command === "help") {
    printJson({
      commands: [
        "node src/mcp-client-cli.js tools",
        "node src/mcp-client-cli.js call <tool_name> <json_arguments>"
      ]
    });
    return;
  }

  await withClient(async (client) => {
    if (command === "tools") {
      const result = await client.listTools();
      printJson(result);
      return;
    }

    if (command === "call") {
      const [toolName, rawArgs = "{}"] = rest;

      if (!toolName) {
        throw new Error("Missing tool name for `call`.");
      }

      const parsedArgs = JSON.parse(rawArgs);
      const result = await client.callTool({
        name: toolName,
        arguments: parsedArgs
      });

      printJson(result);
      return;
    }

    throw new Error(`Unknown command: ${command}`);
  });
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
