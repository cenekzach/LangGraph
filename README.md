# LangGraph DevOps PoC (Two-Node Writer + Validator with MCP Filesystem)

This repository now runs a **two-node LangGraph workflow** with an MCP filesystem integration.

## Workflow

```text
START -> writer -> validator
validator -> writer (when validation fails and attempts remain)
validator -> END (when validation passes)
validator -> END (when max attempts is reached)
```

### Node 1: `writer`
- Takes the user request.
- Generates code or structured data using the configured model.
- Saves the artifact through the MCP filesystem server (`tools/call` write tool).
- Returns metadata only (path/type/summary/attempt count), not the full artifact body.

### Node 2: `validator`
- Reads the saved file back through the MCP filesystem server (`tools/call` read tool).
- Validates the persisted content by type:
  - Python: syntax via `ast.parse`
  - JSON: parse with `json.loads`
  - YAML: parse with `yaml.safe_load`
  - CSV: parse and check consistent column counts
  - Markdown/Text: non-empty + extension consistency checks
- Produces actionable feedback when validation fails.

## MCP filesystem integration

The MCP adapter is in `app/mcp/filesystem_client.py` and handles:
- MCP connect/initialize attempt,
- tool discovery (`tools/list`) and binding,
- file write calls,
- file read calls,
- clear exceptions for transport/tool errors.

This module is intentionally thin and explicit so additional MCP servers/adapters can be added later.

## Local setup

1. Bootstrap venv + dependencies:

   ```bash
   source scripts/setup_venv.sh
   ```

2. Configure environment variables:

   ```bash
   cp env.example .env
   # edit values as needed
   ```

3. Run the graph:

   ```bash
   python3 poc_single_node.py "Create a valid JSON file describing a web service"
   ```

## Configuration (environment variables)

- `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `MCP_FS_BASE_URL` (HTTP endpoint for filesystem MCP server)
- `MCP_FS_READ_TOOL`, `MCP_FS_WRITE_TOOL`
- `MCP_WORKSPACE_PREFIX` (optional path prefix)
- `MAX_ATTEMPTS`
- `LOG_LEVEL` (default `INFO`)

## Retry behavior

- Every validator failure writes actionable feedback into state.
- The next writer attempt incorporates that feedback.
- The graph stops with:
  - `success` when validation passes,
  - `failed` when attempts hit `MAX_ATTEMPTS`.

## Logs (`docker logs` friendly)

The app uses Python `logging` with concise structured-style messages to stdout, including:
- graph start,
- writer start and selected path,
- MCP connect + tool discovery,
- filesystem write/read attempts and outcomes,
- validator pass/fail,
- retry decisions,
- final graph outcome.

Run in Docker and inspect with:

```bash
docker logs <container_name>
```
