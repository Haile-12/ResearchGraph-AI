from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from config.settings import settings
from core.query_executor import execute_raw
from db.neo4j_client import get_schema_fallback
from services.vector_service import search_papers_by_similarity
from utils.logger import get_logger

os.environ.setdefault("GOOGLE_API_KEY", settings.gemini_api_key)
logger = get_logger(__name__)

@dataclass
class AgentResult:
    """Result from the ReAct agent pipeline."""
    answer: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    iterations: int = 0

@tool
def cypher_executor(cypher: str) -> str:
    """Execute a Cypher query against the Neo4j database. Input should be a raw Cypher string."""
    cypher = cypher.strip().strip('"').strip("'")
    logger.debug("[Agent Tool] CypherExecutor: %s", cypher[:150])

    dangerous = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"]
    for keyword in dangerous:
        if keyword in cypher.upper():
            return f"ERROR: Write operation '{keyword}' is not permitted."

    try:
        records = execute_raw(cypher)
    except Exception as e:
        return f"ERROR executing query: {e}"

    if not records:
        return "Query returned no results."

    lines = []
    record_list = list(records) if records else []
    for i, record in enumerate(record_list[:25], 1): 
        parts = [f"{k}={str(v)[:500]}" for k, v in record.items() if v is not None] 
        lines.append(f"{i}. {' | '.join(parts)}")

    result_str = "\n".join(lines)
    if len(records) > 25:
        result_str += f"\n... and {len(records) - 25} more records."
    return result_str


@tool
def vector_search_tool(query: str) -> str:
    """Search for relevant research papers using vector similarity. Input should be a natural language description or keyword."""
    logger.debug("[Agent Tool] VectorSearch: %s", query[:100])
    try:
        result = search_papers_by_similarity(query, top_k=5, expand=False)
    except Exception as e:
        return f"ERROR during vector search: {e}"

    if not result.results:
        return "No papers found matching that description."

    lines = []
    for i, paper in enumerate(result.results[:5], 1):
        title   = paper.get("title", "Unknown")
        year    = paper.get("year", "")
        authors = ", ".join(paper.get("authors", [])[:3])
        score   = paper.get("score", 0.0)
        lines.append(f"{i}. '{title}' ({year}) by {authors} [similarity: {score:.3f}]")

    return "\n".join(lines)


@tool
def schema_inspector(query: str) -> str:
    """Inspect the database schema to understand available nodes, relationships, and properties."""
    logger.debug("[Agent Tool] SchemaInspector called")
    return get_schema_fallback()

def run_agent_query(
    question: str,
    conversation_history: str = "",
) -> AgentResult:
    logger.info("Starting agent query for: '%s'", question[:100])

    tools = {
        "cypher_executor": cypher_executor,
        "vector_search_tool": vector_search_tool,
        "schema_inspector": schema_inspector,
    }

    keys = [settings.gemini_api_key]
    if settings.google_api_key:
        keys.append(settings.google_api_key)
    
    import random
    api_key = random.choice(keys)

    from config.prompts import AGENT_SYSTEM_PROMPT
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=0.0, 
        api_key=api_key,
        max_output_tokens=2048,
    ).bind_tools(list(tools.values()))

    # Build memory / system context
    messages = [
        SystemMessage(content=AGENT_SYSTEM_PROMPT.format(
            conversation_history=conversation_history or "No prior history."
        )),
        HumanMessage(content=question)
    ]

    steps = []
    max_steps = 8

    try:
        for i in range(max_steps):
            # 1. Ask model for thought/action
            ai_msg = llm.invoke(messages)
            messages.append(ai_msg)

            # Check if model produced a final answer OR a tool call
            if not ai_msg.tool_calls:
                # No tool calls = final answer
                return AgentResult(
                    answer=_get_text(ai_msg.content),
                    steps=steps,
                    iterations=i + 1
                )

            # 2. Process tool calls
            for tool_call in ai_msg.tool_calls:
                tool_name = tool_call["name"].lower()
                tool_args = tool_call["args"]

                if tool_name not in tools:
                    obs = f"Error: Tool '{tool_name}' not found."
                else:
                    try:
                        selected_tool = tools[tool_name]
                        obs = selected_tool.invoke(tool_args)
                    except Exception as tool_err:
                        logger.error("Error executing tool %s: %s", tool_name, tool_err)
                        obs = f"Error executing tool: {tool_err}"

                # Record step for UI trace
                steps.append({
                    "tool": tool_name,
                    "input": str(tool_args),
                    "output": str(obs)[:1000] 
                })

                # Append tool result to messages
                messages.append(ToolMessage(
                    content=str(obs),
                    tool_call_id=tool_call["id"]
                ))
        
        final_answer = "I reached the maximum reasoning steps without finding a final answer. Please try a simpler query."
        return AgentResult(
            answer=final_answer,
            steps=steps,
            iterations=max_steps
        )

    except Exception as e:
        logger.exception("Agent execution failed: %s", e)
        return AgentResult(
            answer="The reasoning agent encountered an error during analysis.",
            error=str(e),
            steps=steps
        )

def _get_text(content: Any) -> str:
    """Ensure AIMessage content is a string, joining blocks if necessary."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        return "\n".join(text_parts)
    return str(content)
