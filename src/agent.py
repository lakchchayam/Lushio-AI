import json
import time
import logging
import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from typing import TypedDict, Any, List, Dict, cast
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LushioAgent")

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    temperature=0.7,
    google_api_key=os.getenv("GEMINI_API_KEY") or "AIzaSyDcDBFDKXvUidx8Nfr8s-gb8ijLhZEohmw",
)

# ── State ─────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    query: str
    supervisor_directive: str
    inventory_items: List[Dict[str, Any]]
    research_data: str
    research_iterations: int
    final_answer: Dict[str, Any]

# ── Tools (direct calls — no MCP subprocess overhead) ────────────────────────
def _load_inventory() -> Dict:
    path = os.path.join(os.path.dirname(__file__), "inventory.json")
    with open(path) as f:
        return json.load(f)

@tool
def check_inventory(product_name: str) -> Dict[str, Any]:
    """Check inventory stock and price for a given product."""
    data = _load_inventory()
    q = product_name.lower().strip()
    for category, items in data.items():
        for name, details in items.items():
            if name in q or q in name:
                logger.info(f"[Tool] check_inventory → found '{name}'")
                return {"name": name, "stock": details["stock"], "price": details["price"], "status": "found"}
    logger.info(f"[Tool] check_inventory → '{product_name}' not found")
    return {"name": product_name, "stock": 0, "price": 0.0, "status": "not_found"}

@tool
def search_documents(query: str) -> str:
    """Search store FAQ and policies (returns canned answer when Pinecone not configured)."""
    pinecone_key = os.getenv("PINECONE_API_KEY")
    if not pinecone_key:
        return "Policy info: We offer 30-day returns on all items. Standard shipping takes 3-5 business days. Warranty: 1 year on electronics."
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_pinecone import PineconeVectorStore
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vs = PineconeVectorStore(index_name="lushio-rag", embedding=embeddings)
        docs = vs.similarity_search(query, k=3)
        return "\n\n".join(d.page_content for d in docs) if docs else "No relevant documents found."
    except Exception as e:
        logger.error(f"Pinecone search failed: {e}")
        return "Policy info: We offer 30-day returns. Standard shipping 3-5 days. 1-year warranty on electronics."

TOOLS = [check_inventory, search_documents]

# ── Nodes ─────────────────────────────────────────────────────────────────────
async def supervisor_node(state: AgentState):
    logger.info("[Supervisor] Analyzing request…")
    sys_msg = SystemMessage(content="""You are the Orchestration Supervisor for a retail AI system.
Analyze the user query and give a ONE-LINE directive to the Research Agent.
Specify EXACTLY which tool to use:
- check_inventory(product_name) — for stock / price queries
- search_documents(query)       — for returns, shipping, warranty questions
Be direct and command-like.""")
    resp = await llm.ainvoke([sys_msg, HumanMessage(content=state["query"])])
    return {"supervisor_directive": resp.content, "research_iterations": 0}


async def research_node(state: AgentState):
    logger.info("[Research] Gathering data…")
    directive = state.get("supervisor_directive", "")
    items: List[Dict[str, Any]] = list(state.get("inventory_items", []))
    prev_data: str = state.get("research_data", "")

    sys_msg = SystemMessage(content="""You are a Research Agent. Execute the Supervisor's directive using the available tools.
Use check_inventory for product queries. Use search_documents for policy questions.
Call the tool with the correct argument.""")

    llm_tools = llm.bind_tools(TOOLS)
    resp = await llm_tools.ainvoke([sys_msg, HumanMessage(content=directive)])

    new_text = ""
    if resp.tool_calls:
        tool_outputs: List[str] = []
        for tc in resp.tool_calls:
            name = tc["name"]
            args = tc["args"]
            logger.info(f"[Research] Calling tool: {name}({args})")
            try:
                if name == "check_inventory":
                    result = await check_inventory.ainvoke(args)
                    existing = [i["name"] for i in items]
                    if result.get("status") == "found" and result["name"] not in existing:
                        items.append(result)
                    tool_outputs.append(f"check_inventory → {result}")
                elif name == "search_documents":
                    result = await search_documents.ainvoke(args)
                    tool_outputs.append(f"search_documents → {result}")
            except Exception as e:
                logger.error(f"Tool error {name}: {e}")
                tool_outputs.append(f"{name} error: {e}")
        new_text = "\n".join(tool_outputs)
    else:
        new_text = resp.content or ""

    combined = (prev_data + "\n\n" + new_text).strip()
    return {
        "research_data": combined,
        "inventory_items": items,
        "research_iterations": state.get("research_iterations", 0) + 1,
    }


async def evaluate_research(state: AgentState) -> str:
    if state.get("research_iterations", 0) >= 2:
        return "writer"
    sys_msg = SystemMessage(content="Evaluate if we have enough data. Reply ONLY 'ENOUGH' or 'MORE'.")
    ctx = f"Query: {state['query']}\nItems: {state['inventory_items']}\nData: {state['research_data']}"
    try:
        resp = await llm.ainvoke([sys_msg, HumanMessage(content=ctx)])
        return "research" if "MORE" in resp.content.upper() else "writer"
    except Exception:
        return "writer"


async def writer_node(state: AgentState):
    logger.info("[Writer] Composing answer…")
    sys_msg = SystemMessage(content="""You are a friendly Writer Agent for a retail store.
Write a concise, helpful answer based ONLY on the data provided.
Mention stock levels and prices when available. Do NOT invent any information.""")
    ctx = HumanMessage(content=f"Query: {state['query']}\nItems: {state['inventory_items']}\nResearch: {state['research_data']}")
    try:
        resp = await llm.ainvoke([sys_msg, ctx])
        message = resp.content.strip()
    except Exception as e:
        message = f"Error composing response: {e}"

    products = [
        {"name": i.get("name"), "stock": i.get("stock", 0), "price": i.get("price", 0.0)}
        for i in state.get("inventory_items", [])
    ]
    return {"final_answer": {"message": message, "products": products}}


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_workflow():
    wf = StateGraph(AgentState)
    wf.add_node("supervisor", supervisor_node)
    wf.add_node("research",   research_node)
    wf.add_node("writer",     writer_node)
    wf.add_edge(START, "supervisor")
    wf.add_edge("supervisor", "research")
    wf.add_conditional_edges("research", evaluate_research, {"research": "research", "writer": "writer"})
    wf.add_edge("writer", END)
    return wf.compile()

workflow_app = build_workflow()

# ── FastAPI ───────────────────────────────────────────────────────────────────
app_instance = FastAPI(title="Lushio AI Multi-Agent API")
app_instance.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app_instance.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")

QUERY_CACHE: Dict[str, Any] = {}

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    items_found: List[Dict[str, Any]]
    final_answer: Dict[str, Any]
    execution_time_seconds: float

@app_instance.get("/")
async def root():
    return {"message": "Lushio AI Multi-Agent API", "frontend": "/static/index.html", "endpoints": {"ask": "/ask (POST)"}}

@app_instance.post("/ask", response_model=QueryResponse)
async def ask_agent(request: QueryRequest):
    logger.info(f"Query: {request.query}")
    start = time.time()
    key = request.query.strip().lower()

    if key in QUERY_CACHE:
        cached = dict(QUERY_CACHE[key])
        cached["execution_time_seconds"] = round(time.time() - start, 2)
        return cached

    try:
        state = await workflow_app.ainvoke({
            "query": request.query,
            "inventory_items": [],
            "research_data": "",
            "research_iterations": 0,
        })
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze request: {e}")

    result = {
        "query": request.query,
        "items_found": cast(List[Dict[str, Any]], state.get("inventory_items", [])),
        "final_answer": cast(Dict[str, Any], state.get("final_answer", {})),
        "execution_time_seconds": round(time.time() - start, 2),
    }
    QUERY_CACHE[key] = result
    logger.info(f"Done in {result['execution_time_seconds']}s")
    return result

if __name__ == "__main__":
    uvicorn.run(app_instance, host="0.0.0.0", port=8080)
