import pg from "pg";

const { Pool } = pg;

export const pool = new Pool({
  host: process.env.POSTGRES_HOST ?? "localhost",
  port: Number(process.env.POSTGRES_PORT ?? 5432),
  database: process.env.POSTGRES_DB ?? "mcp_demo",
  user: process.env.POSTGRES_USER ?? "mcp_user",
  password: process.env.POSTGRES_PASSWORD ?? "mcp_password"
});

export async function runQuery(sql, params = []) {
  const client = await pool.connect();

  try {
    await client.query("BEGIN READ ONLY");
    const result = await client.query(sql, params);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}

export async function runWriteQuery(sql, params = []) {
  const client = await pool.connect();

  try {
    await client.query("BEGIN");
    const result = await client.query(sql, params);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK");
    throw error;
  } finally {
    client.release();
  }
}
