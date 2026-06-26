# Copyright (c) Microsoft. All rights reserved.

"""MAF agent harness deployed as a Microsoft Foundry Hosted Agent.

This wraps the Microsoft Agent Framework "agent harness" pattern
(https://devblogs.microsoft.com/agent-framework/agent-harness-in-agent-framework/)
and serves it over the Foundry Hosted Agent **Responses** protocol via
``azure.ai.agentserver``.

Key harness building blocks wired up below:

* **Local shell harness with approvals** - ``LocalShellTool`` runs shell
  commands inside the hosted container. ``approval_mode="always_require"``
  means every command surfaces as an approval request to the client before it
  runs; approval is the tool's real security boundary.
* **Context compaction** - an ``InMemoryHistoryProvider`` with a
  ``SlidingWindowStrategy`` keeps long-running conversations within the model's
  token budget.
"""

import os

from agent_framework import InMemoryHistoryProvider, SlidingWindowStrategy
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_tools.shell import LocalShellTool
from azure.ai.agentserver.agentframework import from_agent_framework
from azure.identity import DefaultAzureCredential

AGENT_NAME = os.environ.get("AGENT_NAME", "MafAgentHarness")

INSTRUCTIONS = """\
You are an agent harness with controlled access to a shell on the host
container. Use the shell tool to inspect the workspace, run commands, and work
with files when it helps answer the user.

Operating rules:
- Prefer the smallest, most targeted command that accomplishes the task.
- Every shell command requires explicit approval before it runs. Explain what a
  command does and why before requesting it.
- Never run destructive commands (for example `rm -rf`, disk formatting, or
  fork bombs) and refuse if asked to.
- Summarize command output for the user instead of dumping large blobs.
"""

# Keep the most recent conversation groups; trim older tool-heavy exchanges so
# long sessions stay within the model context window.
MAX_HISTORY_MESSAGES = int(os.environ.get("COMPACTION_MAX_MESSAGES", "100"))


def build_agent():
    """Construct the harness agent."""
    credential = DefaultAzureCredential()
    client = AzureOpenAIChatClient(credential=credential)

    # Stateless mode spawns a fresh subprocess per command. This is the correct
    # choice for a hosted agent serving many isolated sessions - a persistent
    # LocalShellTool must not be shared across sessions/users.
    shell = LocalShellTool(mode="stateless", approval_mode="always_require")

    return client.create_agent(
        name=AGENT_NAME,
        instructions=INSTRUCTIONS,
        tools=[shell.as_function(name="run_shell")],
        context_providers=[
            InMemoryHistoryProvider(
                "memory",
                compaction_strategy=SlidingWindowStrategy(max_messages=MAX_HISTORY_MESSAGES),
            ),
        ],
    )


def main() -> None:
    # ``from_agent_framework(...).run()`` starts the Responses protocol server
    # (HTTP server, /health endpoint, and OpenTelemetry export) on port 8088.
    from_agent_framework(build_agent()).run()


if __name__ == "__main__":
    main()
