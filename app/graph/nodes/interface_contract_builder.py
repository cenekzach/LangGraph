from __future__ import annotations

import logging

from app.graph.nodes.common import safe_json_dumps
from app.graph.state import WorkflowState
from app.mcp.filesystem_client import FilesystemMCPClient

logger = logging.getLogger(__name__)

INTERFACE_CONTRACT_PATH = "/workspace/artifacts/interface_contract.json"


def interface_contract_builder_node(
    state: WorkflowState,
    fs_client: FilesystemMCPClient,
) -> WorkflowState:
    logger.info("interface_contract_builder:start")
    requirements = (state.get("requirements_summary") or "").lower()

    contract = {
        "entrypoint": "game.py",
        "cli_flags": ["--actions", "--exit"],
        "deterministic_replay": True,
        "interactive_contract": {
            "numeric_only_input": True,
            "action_menu_required": True,
            "object_submenu_required": any(k in requirements for k in ["object", "submenu", "two-stage", "two stage"]),
        },
        "win_signal_patterns": ["you escaped", "door unlocks", "you win", "victory", "success"],
    }
    fs_client.write_file(INTERFACE_CONTRACT_PATH, safe_json_dumps(contract))
    logger.info("interface_contract_builder:wrote path=%s", INTERFACE_CONTRACT_PATH)

    return {
        **state,
        "interface_contract_path": INTERFACE_CONTRACT_PATH,
        "interface_contract_summary": (
            f"entrypoint={contract['entrypoint']} flags={','.join(contract['cli_flags'])} "
            f"numeric_only={contract['interactive_contract']['numeric_only_input']}"
        ),
    }
