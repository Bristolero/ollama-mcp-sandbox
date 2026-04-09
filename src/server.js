import "dotenv/config";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { pool } from "./db.js";
import { registerOsTools } from "./os-tools.js";
import { registerSqlTools } from "./sql-tools.js";

const server = new McpServer({
  name: "postgres-learning-mcp",
  version: "1.0.0"
});

registerSqlTools(server);
registerOsTools(server);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(async (error) => {
  console.error("Failed to start MCP server:", error);
  await pool.end().catch(() => {});
  process.exit(1);
});
