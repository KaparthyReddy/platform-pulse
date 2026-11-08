from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pulse import config

SYSTEM_PROMPT = (
    "You are Platform Pulse, a support assistant for internal customers of a data platform "
    "(Spark, Airflow, Trino, Flink). Ground every claim in tool results and never invent metrics. "
    "Check platform health and incidents first. For any incident, search the runbooks, read the "
    "best match, and cite the runbook name. Answer in under 180 words as plain Slack text: use "
    "*single asterisks* for bold, short bullets, and end with clear next steps. If data is "
    "missing, say so."
)

MAX_TURNS = 8
DEFAULT_QUESTION = (
    "What is the current platform health, and what should I do about any active incidents?"
)


@dataclass
class AgentResult:
    answer: str
    mode: str
    tools_used: list[str] = field(default_factory=list)


def _server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "pulse.mcp_server"],
        env=dict(os.environ),
    )


async def _call_raw(session: ClientSession, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
    result = await session.call_tool(name, arguments)
    parts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
    return "\n".join(parts), bool(result.isError)


async def _call_json(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
    text, is_error = await _call_raw(session, name, arguments)
    if is_error:
        raise RuntimeError(text or f"tool {name} failed")
    return json.loads(text)


def _final_text(response: Any) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


async def _run_llm(session: ClientSession, question: str) -> tuple[str, list[str]]:
    listed = await session.list_tools()
    tools = [
        {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
        for t in listed.tools
    ]
    client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    used: list[str] = []

    for _ in range(MAX_TURNS):
        response = await client.messages.create(
            model=config.MODEL,
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        if response.stop_reason != "tool_use":
            return _final_text(response), used

        messages.append({"role": "assistant", "content": response.content})
        results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type == "tool_use":
                used.append(block.name)
                text, is_error = await _call_raw(session, block.name, dict(block.input))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": results})

    return "I could not finish within the tool-call limit. Try a narrower question.", used


async def _run_offline(session: ClientSession, question: str) -> tuple[str, list[str]]:
    used: list[str] = []

    async def call(name: str, arguments: dict[str, Any]) -> Any:
        used.append(name)
        return await _call_json(session, name, arguments)

    items = await call("get_platform_health", {})
    match = re.search(r"incident\s+#?(\d+)", question, re.IGNORECASE)
    if match:
        incident = await call("get_incident", {"incident_id": int(match.group(1))})
        incidents = [] if "error" in incident else [incident]
    else:
        incidents = await call("list_incidents", {"active_only": True})

    lines = ["*Platform health*"]
    for item in items:
        lines.append(
            f"- {item['service']}: {item['status']} (score {item['score']}, "
            f"open incidents {item['open_incidents']})"
        )
    if not incidents:
        lines.append("No matching incidents.")
    for incident in incidents:
        lines.append(f"\n*{incident['severity']} {incident['service']}: {incident['title']}*")
        lines.append(incident["summary"])
        matches = await call(
            "search_runbooks", {"query": incident["title"], "service": incident["service"]}
        )
        if matches:
            detail = await call("get_runbook", {"name": matches[0]["name"]})
            lines.append(f"Runbook: {detail['name']}")
            lines.append(f"Next step: {detail['mitigation'].splitlines()[0]}")
    lines.append("\n_Offline mode: set ANTHROPIC_API_KEY for question answering._")
    return "\n".join(lines), used


async def ask_async(question: str) -> AgentResult:
    async with (
        stdio_client(_server_params()) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        if config.ANTHROPIC_API_KEY:
            try:
                answer, used = await _run_llm(session, question)
                return AgentResult(answer=answer, mode="llm", tools_used=used)
            except anthropic.APIError:
                pass
        answer, used = await _run_offline(session, question)
        return AgentResult(answer=answer, mode="offline", tools_used=used)


def ask(question: str) -> AgentResult:
    return asyncio.run(ask_async(question))


def triage_incident(incident_id: int) -> AgentResult:
    return ask(
        f"Triage incident {incident_id}: summarize customer impact, likely cause, and next steps "
        "from the matching runbook. Cite the runbook name."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Platform Pulse triage agent.")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    args = parser.parse_args()
    result = ask(args.question)
    print(result.answer)
    print(f"\n[mode={result.mode} tools={', '.join(result.tools_used) or 'none'}]")


if __name__ == "__main__":
    main()
