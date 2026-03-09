# LangGraph DevOps PoC (Single Node Validation)

This repository contains a minimal **LangGraph proof of concept** for a DevOps helper agent with one purpose in this iteration: **syntax validation**.

## What this PoC does

- Builds a LangGraph workflow with exactly **one node**: `validation_node`.
- Sends code/config text to a model endpoint (OpenAI-compatible, such as local vLLM).
- Returns a focused syntax report:
  - detected format,
  - syntax issues,
  - corrected snippet,
  - quick local validation commands.

## Local setup (Ubuntu VM)

1. Create and activate a virtualenv:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -e .
   ```

3. Configure environment variables:

   ```bash
   cp .env.example .env
   # then edit .env if needed
   ```

4. Run the single-node validation flow:

   ```bash
   python poc_single_node.py "{\"a\": 1,}" --format-hint json
   ```

## vLLM notes

This PoC uses `ChatOpenAI` with OpenAI-compatible settings:

- `OPENAI_API_BASE` (default: `http://127.0.0.1:8000/v1`)
- `OPENAI_API_KEY` (default: `local-dev`)
- `OPENAI_MODEL` (default: `meta-llama/Llama-3.1-8B-Instruct`)

If your vLLM endpoint or model name differs, update `.env`.

## Files

- `poc_single_node.py`: single-node graph and CLI entrypoint.
- `.env.example`: local vLLM/OpenAI-compatible environment template.
- `pyproject.toml`: dependencies and console script (`langgraph-devops-poc`).

## Next step for MCP integration

Once this baseline works, the next step is to connect MCP tools so the graph can fetch artifacts (CI logs, Kubernetes events, repo files) and validate snippets directly from those sources.

## Questions to shape the next iteration

1. Which model should be the default for your RTX4090 setup?
2. Which MCP integration should we add first (GitHub, Kubernetes, CI logs, ticketing)?
3. Should the validation result also be emitted as strict JSON for downstream automation?
