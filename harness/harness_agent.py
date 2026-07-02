"""MAF agent harness — a lean, shell-enabled harness agent with a simple REPL.

A starting point inspired by the Microsoft Agent Framework harness sample
(``microsoft/agent-framework/python/samples/02-agents/harness``), trimmed down to
the essentials: ``create_harness_agent`` + ``FoundryChatClient`` + a local shell
tool, driven by a minimal async read-eval-print loop (no Textual UI).

``create_harness_agent`` assembles a batteries-included agent: automatic tool
calling, per-service-call history persistence, context-window compaction, a todo
list for planning, plan/execute mode tracking, web search, and tool-approval
handling. We additionally wire a ``LocalShellTool`` so the agent can run shell
commands and probe its environment; every command is gated behind an approval
prompt that this REPL surfaces to you on the terminal.

Environment variables:
    FOUNDRY_PROJECT_ENDPOINT — Azure AI Foundry project endpoint URL, e.g.
        https://<account>.services.ai.azure.com/api/projects/<project>
    FOUNDRY_MODEL            — Model deployment name (e.g. kimi-k2-6)

Authentication:
    Run ``az login`` before starting (AzureCliCredential). Swap in
    DefaultAzureCredential for managed-identity environments.

Usage:
    python harness_agent.py
    Type a message and press Enter. Commands: /exit (or /quit) to leave.
"""

import asyncio
import os
import sys
from pathlib import Path

from agent_framework import Message, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_tools.shell import (
    LocalShellTool,
    ShellEnvironmentProvider,
    ShellEnvironmentProviderOptions,
)
from azure.identity import AzureCliCredential
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
"""


def _tool_name(content) -> str:
    """Best-effort readable name for a function/approval content item."""
    fc = getattr(content, "function_call", None) or content
    name = getattr(fc, "name", None)
    return str(name) if name else "tool"


async def _prompt(text: str) -> str:
    """Read a line from stdin without blocking the event loop."""
    return (await asyncio.to_thread(input, text)).strip()


async def _run_turn(agent, session, user_text: str) -> None:
    """Run one user turn to completion, surfacing shell approval prompts."""
    # First pass sends the user's text; later passes send approval responses.
    messages: list | str = user_text

    while True:
        approval_requests: list = []
        printed_any = False

        stream = agent.run(messages, stream=True, session=session)
        async for update in stream:
            for content in getattr(update, "contents", None) or []:
                ctype = getattr(content, "type", None)
                if ctype == "function_call":
                    print(f"\n  → calling {_tool_name(content)}...", flush=True)
                elif ctype == "function_approval_request":
                    approval_requests.append(content)
            text = getattr(update, "text", None)
            if text:
                print(text, end="", flush=True)
                printed_any = True

        if printed_any:
            print()

        if not approval_requests:
            return

        # Surface each pending shell/tool approval to the user, then re-run with
        # the approval responses so the agent can continue.
        responses = []
        for request in approval_requests:
            answer = await _prompt(f"🔐 Approve `{_tool_name(request)}`? [y/N] ")
            approved = answer.lower() in ("y", "yes")
            responses.append(request.to_function_approval_response(approved=approved))
        messages = [Message(role="user", contents=responses)]


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
        session = agent.create_session()

        print("🤖 MAF Agent Harness — type a task, or /exit to quit.\n")
        while True:
            try:
                user_text = await _prompt("you> ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_text:
                continue
            if user_text.lower() in ("/exit", "/quit"):
                break
            try:
                await _run_turn(agent, session, user_text)
            except Exception as ex:  # noqa: BLE001 - surface errors, keep REPL alive
                print(f"\n❌ {ex.__class__.__name__}: {ex}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
