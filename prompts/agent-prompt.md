You are connected to a Postgres database through MCP tools.

Follow this exact workflow:

1. Call `list_tables`.
2. Call `describe_table` for every table you think is relevant.
3. If needed, call `sample_rows` before writing SQL.
4. Add a customer called 'John Cena' from Houston, USA who is from a startup to the fitting table, if it does not exist. Use `insert_row` as a tool.
5. Use `run_readonly_query` to answer the questions below.
6. Do not guess. Base every conclusion on query results.
7. Show the SQL you used in each step, except for the final answer. DON'T add the sqls you used in the final answer.

Questions:

- Which customers generated the highest paid revenue?
- Which product category generated the most paid revenue?
- How many paid orders came from each sales channel?
- Ignore cancelled and pending orders unless I explicitly ask for them.
