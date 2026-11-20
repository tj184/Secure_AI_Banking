
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from agents import get_llm

from agents.account_agent import account_agent
from agents.transaction_agent import transaction_agent
from agents.payment_agent import payment_agent
from agents.support_agent import support_agent


# ==========================================
# SUPERVISOR STATE
# ==========================================

class SupervisorState(TypedDict):

    query: str
    user_context: dict
    selected_agent: str
    response: str


# ==========================================
# SUPERVISOR PROMPT
# ==========================================

SUPERVISOR_PROMPT = """
You are the Supervisor Agent of SecureBank AI.

Your job is to identify the customer's intent
and select the most appropriate specialized agent.

AVAILABLE AGENTS:

1. account
   For account balances, account details and account status.

2. transaction
   For transaction history, spending analysis and expenses.

3. payment
   For money transfers, payment requests and beneficiaries.

4. support
   For general banking questions and customer assistance.

ROUTING RULES:

- Account balance questions -> account
- Account information -> account
- Transaction history -> transaction
- Spending calculations -> transaction
- Expense analysis -> transaction
- Money transfer requests -> payment
- Payment preparation -> payment
- General banking questions -> support
- Banking terminology -> support

IMPORTANT:

Return ONLY one of these exact words:

account
transaction
payment
support

Do not provide explanations.
Do not generate additional text.
"""


# ==========================================
# ROUTE CLASSIFICATION
# ==========================================

def classify_request(state: SupervisorState):

    llm = get_llm()

    response = llm.invoke([
        {
            "role": "system",
            "content": SUPERVISOR_PROMPT
        },
        {
            "role": "user",
            "content": state["query"]
        }
    ])

    selected = str(response.content).strip().lower()

    # Normalize the model output.
    valid_agents = {
        "account",
        "transaction",
        "payment",
        "support"
    }

    # Deterministic fallback.
    if selected not in valid_agents:

        query = state["query"].lower()

        if any(word in query for word in [
            "transfer", "send money", "pay ",
            "payment", "beneficiary"
        ]):
            selected = "payment"

        elif any(word in query for word in [
            "transaction", "spent", "spending",
            "expense", "expenditure"
        ]):
            selected = "transaction"

        elif any(word in query for word in [
            "balance", "account number",
            "account status"
        ]):
            selected = "account"

        else:
            selected = "support"

    return {
        "selected_agent": selected
    }


# ==========================================
# SPECIALIZED AGENT NODES
# ==========================================

def account_node(state: SupervisorState):

    result = account_agent(
        query=state["query"],
        user_context=state["user_context"]
    )

    return {"response": result}


def transaction_node(state: SupervisorState):

    result = transaction_agent(
        query=state["query"],
        user_context=state["user_context"]
    )

    return {"response": result}


def payment_node(state: SupervisorState):

    result = payment_agent(
        query=state["query"],
        user_context=state["user_context"]
    )

    return {"response": result}


def support_node(state: SupervisorState):

    result = support_agent(
        query=state["query"],
        user_context=state["user_context"]
    )

    return {"response": result}


# ==========================================
# CONDITIONAL ROUTING
# ==========================================

def route_to_agent(state: SupervisorState):

    return state["selected_agent"]


# ==========================================
# BUILD SUPERVISOR GRAPH
# ==========================================

def build_supervisor():

    workflow = StateGraph(SupervisorState)

    # Register nodes.
    workflow.add_node("classify", classify_request)

    workflow.add_node("account", account_node)

    workflow.add_node("transaction", transaction_node)

    workflow.add_node("payment", payment_node)

    workflow.add_node("support", support_node)

    # Entry point.
    workflow.add_edge(START, "classify")

    # Route based on supervisor classification.
    workflow.add_conditional_edges(
        "classify",
        route_to_agent,
        {
            "account": "account",
            "transaction": "transaction",
            "payment": "payment",
            "support": "support"
        }
    )

    # All agents return to the end.
    workflow.add_edge("account", END)

    workflow.add_edge("transaction", END)

    workflow.add_edge("payment", END)

    workflow.add_edge("support", END)

    return workflow.compile()


# ==========================================
# PUBLIC EXECUTION FUNCTION
# ==========================================

def run_supervisor(query, user_context=None):

    supervisor = build_supervisor()

    initial_state = {
        "query": query,
        "user_context": user_context or {},
        "selected_agent": "",
        "response": ""
    }

    result = supervisor.invoke(initial_state)

    return {
        "selected_agent": result["selected_agent"],
        "response": result["response"]
    }
