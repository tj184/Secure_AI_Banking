
import os
from functools import lru_cache

from langchain_ollama import ChatOllama
from langchain.agents import create_agent




OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gemma4:e2b"
)


# ==========================================
# SHARED LLM
# ==========================================

@lru_cache(maxsize=1)
def get_llm():
    """
    Creates a shared Ollama chat model.

    All agents use this model instance.
    """

    return ChatOllama(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=0.1,
        num_predict=512,
    )


# ==========================================
# AGENT FACTORY
# ==========================================

def create_banking_agent(system_prompt, tools=None):
    """
    Creates an individual LangGraph-powered agent.

    Args:
        system_prompt: Agent-specific instructions.
        tools: Functions the agent is allowed to use.

    Returns:
        Compiled agent graph.
    """

    return create_agent(
        model=get_llm(),
        tools=tools or [],
        system_prompt=system_prompt,
    )


# ==========================================
# COMMON RESPONSE HANDLER
# ==========================================

def extract_agent_response(result):
    """
    Extracts the final AI response from agent state.
    """

    messages = result.get("messages", [])

    for message in reversed(messages):
        if getattr(message, "type", None) == "ai":
            return message.content

    return "The agent could not generate a response."


def run_agent(agent, query, user_context=None):
    """
    Executes an agent with a user request.

    User context is supplied as additional information.
    """

    context = user_context or {}

    prompt = f"""
CUSTOMER REQUEST:
{query}

CUSTOMER CONTEXT:
{context}

Follow your assigned responsibilities.
Do not perform operations outside your permissions.
Do not invent account information or transaction records.
"""

    result = agent.invoke({
        "messages": [
            {"role": "user", "content": prompt}
        ]
    })

    return extract_agent_response(result)
