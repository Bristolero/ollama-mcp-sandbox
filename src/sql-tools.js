import { z } from "zod";
import { runQuery, runWriteQuery } from "./db.js";
import { formatResult } from "./tool-utils.js";

const MAX_ROWS = Number(process.env.MAX_ROWS ?? 50);
const BLOCKED_SQL = /\b(update|delete|drop|alter|truncate|create|grant|revoke|copy|comment)\b/i;
const INSERTABLE_TABLES = new Set(["customers", "products", "orders", "order_items"]);

function cleanSql(sql) {
  return sql.trim().replace(/;+\s*$/, "");
}

function validateReadonlySql(sql) {
  const cleaned = cleanSql(sql);

  if (!cleaned) {
    throw new Error("SQL must not be empty.");
  }

  if (cleaned.includes(";")) {
    throw new Error("Only a single SQL statement is allowed.");
  }

  if (!/^(select|with)\b/i.test(cleaned)) {
    throw new Error("Only SELECT or WITH queries are allowed.");
  }

  if (BLOCKED_SQL.test(cleaned)) {
    throw new Error("Write or schema-changing SQL is blocked.");
  }

  return cleaned;
}

async function getInsertableColumns(tableName) {
  const result = await runQuery(
    `
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = $1
      AND is_identity = 'NO'
      AND COALESCE(column_default NOT LIKE 'nextval(%', TRUE)
    ORDER BY ordinal_position
    `,
    [tableName]
  );

  return new Set(result.rows.map((row) => row.column_name));
}

export function registerSqlTools(server) {
  server.tool(
    "list_tables",
    "List the public tables in the Postgres database.",
    {},
    async () => {
      const result = await runQuery(`
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
      `);

      return formatResult(result.rows, result.rowCount);
    }
  );

  server.tool(
    "describe_table",
    "Describe the columns for a public table.",
    {
      table_name: z.string().min(1)
    },
    async ({ table_name }) => {
      const result = await runQuery(
        `
        SELECT
          column_name,
          data_type,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        `,
        [table_name]
      );

      return formatResult(result.rows, result.rowCount);
    }
  );

  server.tool(
    "sample_rows",
    "Fetch a few rows from a chosen public table to understand its contents.",
    {
      table_name: z.string().min(1),
      limit: z.number().int().min(1).max(20).default(5)
    },
    async ({ table_name, limit }) => {
      const tableCheck = await runQuery(
        `
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = $1
        `,
        [table_name]
      );

      if (tableCheck.rowCount === 0) {
        throw new Error(`Unknown table: ${table_name}`);
      }

      const safeIdentifier = `"${table_name.replace(/"/g, "\"\"")}"`;
      const result = await runQuery(`SELECT * FROM ${safeIdentifier} LIMIT ${limit}`);

      return formatResult(result.rows, result.rowCount);
    }
  );

  server.tool(
    "run_readonly_query",
    "Run a single read-only SQL query. Only SELECT or WITH statements are allowed.",
    {
      sql: z.string().min(1)
    },
    async ({ sql }) => {
      const validatedSql = validateReadonlySql(sql);
      const wrappedSql = `SELECT * FROM (${validatedSql}) AS readonly_query LIMIT ${MAX_ROWS}`;
      const result = await runQuery(wrappedSql);

      return formatResult(result.rows, result.rowCount);
    }
  );

  server.tool(
    "insert_row",
    "Insert a single row into one of the demo tables.",
    {
      table_name: z.string().min(1),
      values: z.object({}).catchall(z.any())
    },
    async ({ table_name, values }) => {
      if (!INSERTABLE_TABLES.has(table_name)) {
        throw new Error(`Inserts are only allowed for: ${Array.from(INSERTABLE_TABLES).join(", ")}`);
      }

      const normalizedValues = { ...values };

      if (table_name === "customers" && normalizedValues.created_at == null) {
        normalizedValues.created_at = new Date().toISOString().slice(0, 10);
      }

      const allowedColumns = await getInsertableColumns(table_name);
      const entries = Object.entries(normalizedValues);

      if (entries.length === 0) {
        throw new Error("You must provide at least one column value.");
      }

      for (const [columnName] of entries) {
        if (!allowedColumns.has(columnName)) {
          throw new Error(`Column "${columnName}" is not insertable on table "${table_name}".`);
        }
      }

      const columnSql = entries.map(([columnName]) => `"${columnName.replace(/"/g, "\"\"")}"`).join(", ");
      const valueSql = entries.map((_, index) => `$${index + 1}`).join(", ");
      const params = entries.map(([, value]) => value);
      const result = await runWriteQuery(
        `INSERT INTO "${table_name.replace(/"/g, "\"\"")}" (${columnSql}) VALUES (${valueSql}) RETURNING *`,
        params
      );

      return formatResult(result.rows, result.rowCount);
    }
  );
}
