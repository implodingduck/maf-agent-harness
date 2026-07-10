"""MAF agent harness — a shell-enabled harness agent with a Textual console UI.

A starting point inspired by the Microsoft Agent Framework harness sample
(``microsoft/agent-framework/python/samples/02-agents/harness``): ``create_harness_agent``
+ ``FoundryChatClient`` + a local shell tool, driven by the sample's rich
Textual-based console (``run_agent_async`` + ``build_default_observers``).

Rather than vendoring the console package, we reference it directly from the
upstream repo, checked out sparsely as a git submodule under
``external/agent-framework`` (pinned to the ``python-1.9.0`` tag). Run
``scripts/setup-console.sh`` once to materialize it, then it is importable as the
top-level ``console`` package (see ``_CONSOLE_PARENT`` below).

``create_harness_agent`` assembles a batteries-included agent: automatic tool
calling, per-service-call history persistence, context-window compaction, a todo
list for planning, plan/execute mode tracking, web search, and tool-approval
handling. We additionally wire a ``LocalShellTool`` so the agent can run shell
commands and probe its environment; every command is gated behind an approval
prompt the console surfaces via its ``ToolApprovalObserver``.

Environment variables:
    FOUNDRY_PROJECT_ENDPOINT — Azure AI Foundry project endpoint URL, e.g.
        https://<account>.services.ai.azure.com/api/projects/<project>
    FOUNDRY_MODEL            — Model deployment name (e.g. kimi-k2-6)

Authentication:
    Run ``az login`` before starting (AzureCliCredential). Swap in
    DefaultAzureCredential for managed-identity environments.

Usage:
    scripts/setup-console.sh   # one-time: fetch the console submodule
    python harness_agent.py
    Type a message and press Enter. Use the console's on-screen help for commands.
"""

import asyncio
import os
import sys
from pathlib import Path

# The upstream harness ``console`` package is referenced (not vendored) from a
# sparse git submodule. Put its parent directory on ``sys.path`` so ``import
# console`` resolves to it before we import anything from it below.
_CONSOLE_PARENT = (
    Path(__file__).resolve().parent.parent
    / "external"
    / "agent-framework"
    / "python"
    / "samples"
    / "02-agents"
    / "harness"
)
if not (_CONSOLE_PARENT / "console" / "__init__.py").exists():
    sys.exit(
        "The upstream 'console' package is missing. Initialize the sparse "
        "submodule first:\n    scripts/setup-console.sh\n"
        f"(expected it at {_CONSOLE_PARENT / 'console'})"
    )
sys.path.insert(0, str(_CONSOLE_PARENT))

from agent_framework import create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_tools.shell import (
    LocalShellTool,
    ShellEnvironmentProvider,
    ShellEnvironmentProviderOptions,
)
from azure.identity import AzureCliCredential
from console import build_default_observers, run_agent_async
from dotenv import load_dotenv

# Token budgets configure compaction; tune to the deployed model's context window.
MAX_CONTEXT_WINDOW_TOKENS = 128_000
MAX_OUTPUT_TOKENS = 16_384

# File-based skills live alongside this module in ``skills/`` (each subdirectory
# with a SKILL.md is a skill). The ``pptx`` skill's directory is also exported to
# the shell environment so its SKILL.md can reference the bundled script and
# template by absolute path regardless of the current working directory.
SKILLS_DIR = Path(__file__).resolve().parent / "skills"
os.environ.setdefault("MAF_PPTX_SKILL_DIR", str(SKILLS_DIR / "pptx"))
# Expose the interpreter running the harness so skill scripts run under the same
# environment (and therefore see the same installed packages, e.g. python-pptx)
# even though the shell tool's ``python`` on PATH may differ.
os.environ.setdefault("MAF_PYTHON", sys.executable)

HARNESS_INSTRUCTIONS = """\
## Agent harness instructions

You are an agent harness with access to a shell on the host via the shell tool,
plus web search, a todo list, and plan/execute modes. Connect model reasoning to
real execution: inspect the environment, run commands, edit files, and verify
your work rather than relying on memory alone.

### Working style
- For non-trivial tasks, plan first: outline the steps as a todo list, then work
  through them, narrating what you are doing and why between tool calls.
- Prefer the smallest, most targeted shell command that accomplishes the task.
- Explain what a command does and why before requesting it; every command is
  gated by an approval prompt.
- Never run destructive commands (for example `rm -rf`, disk formatting, or fork
  bombs) and refuse if asked to.
- Summarize command output for the user instead of dumping large blobs.
- Verify claims and results with the tools available to you.
- Write any files you generate (reports, briefs, decks, scratch/intermediate
  files) into the `output/` directory in the current working directory, creating
  it if needed. `output/` is git-ignored so generated artifacts stay out of
  commits. Do not scatter generated files across the repo.
"""


async def main() -> None:
    load_dotenv()

    # Talk to the Azure AI Foundry project. Reads FOUNDRY_PROJECT_ENDPOINT and
    # FOUNDRY_MODEL from the environment (or .env).
    client = FoundryChatClient(credential=AzureCliCredential())

    # LocalShellTool runs commands locally via subprocess. acknowledge_unsafe is
    # required to construct it, but the harness still gates each command behind a
    # tool-approval prompt. The caller owns the executor's async lifecycle.
    async with LocalShellTool(acknowledge_unsafe=True) as shell:
        # Wire the shell as an ordinary function tool instead of via
        # ``shell_executor=``. ``create_harness_agent(shell_executor=...)`` calls
        # ``client.get_shell_tool(...)``, which tags the tool as an OpenAI *hosted
        # local-shell* tool (``kind == "shell"``). The Responses API then expects
        # the model to emit ``local_shell_call`` actions -- a format the Azure AI
        # Foundry model deployments used here do not produce -- so the ``command``
        # argument arrives empty and every approved command runs as a no-op.
        # Declaring the same executor as a plain function tool makes the model send
        # normal JSON arguments, which Foundry relays correctly. We add the
        # ``ShellEnvironmentProvider`` ourselves to keep the environment-probing
        # context that ``shell_executor=`` would otherwise have provided.
        shell_tool = shell.as_function()
        shell_tool.kind = None
        shell_tool.additional_properties = {}
        agent = create_harness_agent(
            client=client,
            max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            name="MafAgentHarness",
            description="A shell-enabled agent harness that plans and executes tasks.",
            agent_instructions=HARNESS_INSTRUCTIONS,
            tools=[shell_tool],
            skills_paths=[str(SKILLS_DIR)],
            context_providers=[
                ShellEnvironmentProvider(
                    shell,
                    ShellEnvironmentProviderOptions(
                        probe_tools=("git", "python", "bash", "az")
                    ),
                )
            ],
        )

        # Hand off to the upstream Textual console. build_default_observers()
        # wires streaming text, tool-call display, token usage, reasoning, and —
        # importantly — the ToolApprovalObserver, which surfaces each shell
        # command as an interactive approval prompt (our security boundary).
        await run_agent_async(
            agent,
            session=agent.create_session(),
            observers=build_default_observers(),
            title="🤖 MAF Agent Harness",
            placeholder="Type a task and press Enter…",
            max_context_window_tokens=MAX_CONTEXT_WINDOW_TOKENS,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )


if __name__ == "__main__":
    asyncio.run(main())
