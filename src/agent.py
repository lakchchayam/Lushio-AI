import json
import time
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from typing import Annotated, TypedDict, Any, List, Dict, cast
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
import os

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LushioAgent")

# Load environment variables
load_dotenv()

# 1. Define the State
class AgentState(TypedDict):
    query: str
    supervisor_directive: str
    inventory_items: List[Dict[str, Any]]
    research_data: str
    research_iterations: int
    final_answer: Dict[str, Any]

# Pydantic schema for the strictly formatted Writer output
class FinalResponse(BaseModel):
    message: str = Field(description="A friendly, conversational summary of what is in stock or out of stock based on the user's query.")
    products: List[Dict[str, Any]] = Field(description="The exact list of product dictionaries found. E.g. [{'name': 'laptop', 'stock': 15, 'price': 999.99}]")

# Initialize the Groq model
llm = ChatGroq(
    temperature=0.7,
    model_name="llama-3.1-8b-instant",
)

from tools import check_inventory, search_documents
import subprocess
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# --- MCP Integration ---
class MCPToolProxy:
    def __init__(self, server_script: str):
        self.server_script = server_script
        self.python_exe = sys.executable

    async def _call_mcp_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        server_params = StdioServerParameters(
            command=self.python_exe,
            args=[self.server_script],
            env=os.environ.copy()
        )
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info(f"    [🔌 MCP Proxy] Session initialized for '{tool_name}'")
                    result = await session.call_tool(tool_name, args)
                    return result.content[0].text if result.content else str(result)
        except Exception as e:
            logger.error(f"    [❌ MCP Proxy] Error during call_tool('{tool_name}'): {e}")
            return f"Error: {str(e)}"

mcp_proxy = MCPToolProxy(os.path.join(os.path.dirname(__file__), "mcp_server.py"))

@tool
async def mcp_inventory_lookup(product_name: str) -> Dict[str, Any]:
    """Check the inventory stock and price for a given product via MCP."""
    logger.info(f"[🔌 MCP Proxy] Calling inventory_lookup for '{product_name}'")
    result_str = await mcp_proxy._call_mcp_tool("inventory_lookup", {"product_name": product_name})
    try:
        import ast
        return cast(Dict[str, Any], ast.literal_eval(result_str))
    except Exception as e:
        logger.error(f"Parse error for {product_name}: {e}")
        return {"error": "Failed to parse MCP response", "raw": result_str}

@tool
async def mcp_policy_search(query: str) -> str:
    """Search the store's FAQ and policies via MCP."""
    logger.info(f"[🔌 MCP Proxy] Calling policy_search for '{query}'")
    return await mcp_proxy._call_mcp_tool("policy_search", {"query": query})

# 4. Define the Nodes (Agents)

async def supervisor_node(state: AgentState):
    logger.info("[👨‍💼 Node] Supervisor analyzing request...")
    user_query = cast(str, state.get("query", ""))
    
    system_msg = SystemMessage(content="""You are the Orchestration Supervisor.
Analyze the user query and DECIDE which tool the Research Agent must use.
Tools available via MCP:
1. `mcp_inventory_lookup`: Use for stock, prices, or product availability.
2. `mcp_policy_search`: Use for returns, shipping, warranty, or store rules.

Your directive MUST specify:
- The EXACT tool to use.
- The specific parameters/query for that tool.
Keep instructions command-like and precise.""")
    user_msg = HumanMessage(content=user_query)
    
    try:
        # Using ainvoke for async LLM call
        response = await llm.ainvoke([system_msg, user_msg])
        return {"supervisor_directive": response.content, "research_iterations": 0}
    except Exception as e:
        logger.error(f"Supervisor LLM Error: {e}")
        raise ValueError(f"Failed to analyze request: {e}")


async def research_node(state: AgentState):
    logger.info("[🔍 Node] Research Agent gathering information via MCP...")
    directive = cast(str, state.get("supervisor_directive", ""))
    previous_data = cast(str, state.get("research_data", ""))
    items_list = cast(List[Dict[str, Any]], state.get("inventory_items", []))
    iterations = cast(int, state.get("research_iterations", 0))
    
    system_msg = SystemMessage(content="""You are a Research Agent executing tool calls via an MCP Proxy.
You MUST follow the Supervisor Directive exactly. 
Use `mcp_inventory_lookup` for products or `mcp_policy_search` for documentation.
Pass only the necessary arguments. You are responsible for extracting structured data from the tool responses.""")
    
    if items_list or previous_data:
         prompt = f"Supervisor Directive: {directive}\n\nExisting context has some data. If there is still a gap relative to the directive, use the MCP tools again. Otherwise, summarize what you found."
    else:
         prompt = f"Supervisor Directive: {directive}"
         
    directive_msg = HumanMessage(content=prompt)
    
    try:
        llm_with_tools = llm.bind_tools([mcp_inventory_lookup, mcp_policy_search])
        # Using ainvoke for async
        response = await llm_with_tools.ainvoke([system_msg, directive_msg])
    except Exception as e:
        logger.error(f"Research LLM Error: {e}")
        response = AIMessage(content="I encountered an internal error while trying to search the inventory and documents.")
    
    new_text = ""
    if response.tool_calls:
        logger.info(f"    [🤖 Researcher] Invoking {len(response.tool_calls)} tool(s)")
        tool_results_text: List[str] = []
        for tool_call in response.tool_calls:
            try:
                if tool_call["name"] == "mcp_inventory_lookup":
                    # Use ainvoke for async tool call
                    result_dict = await mcp_inventory_lookup.ainvoke(tool_call["args"])
                    logger.debug(f"Inventory Result: {result_dict}")
                    
                    existing_names = [item.get("name") for item in items_list]
                    if result_dict.get("status") == "found" and result_dict.get("name") not in existing_names:
                        items_list.append(result_dict)
                    
                    tool_results_text.append(f"Tool `{tool_call['name']}` returned: {result_dict.get('name')} (Stock: {result_dict.get('stock')})")
                    
                elif tool_call["name"] == "mcp_policy_search":
                    # Use ainvoke for async tool call
                    result_text = await mcp_policy_search.ainvoke(tool_call["args"])
                    logger.debug(f"Document Search Result length: {len(result_text)} chars")
                    tool_results_text.append(f"Tool `{tool_call['name']}` returned:\n{result_text}")
            except Exception as e:
                logger.error(f"Tool execution error for {tool_call['name']}: {e}")
                tool_results_text.append(f"Error executing `{tool_call['name']}`: {e}")
        
        tool_data_str = "\n".join(tool_results_text)
        synth_msg = HumanMessage(content=f"Tool data saved:\n{tool_data_str}\nProvide brief confirmation.")
        final_response = await llm.ainvoke([system_msg, directive_msg, response, synth_msg])
        new_text = final_response.content if final_response.content else str(final_response.tool_calls)
    else:
        new_text = cast(str, response.content)
    
    new_data = str(previous_data) + "\n\n" + str(new_text) if previous_data else str(new_text)
    return {"research_data": new_data, "inventory_items": items_list, "research_iterations": int(iterations) + 1}


async def evaluate_research(state: AgentState):
    query = cast(str, state.get("query", ""))
    data = cast(str, state.get("research_data", ""))
    items_list = cast(List[Dict[str, Any]], state.get("inventory_items", []))
    iterations = cast(int, state.get("research_iterations", 0))
    
    if int(iterations) >= 2:
        logger.info("[⚡ Supervisor] Max iterations reached, moving to Writer.")
        return "writer"
        
    logger.info("[🤔 Supervisor] Evaluating research data...")
    
    system_msg = SystemMessage(content="You are an Evaluator. Look at the original query. If it asks about products, check the 'Gathered Items' list. If it asks about policies/info, check the 'Notes' for relevant facts. If you have enough info to answer the query, reply 'ENOUGH'. Otherwise, reply 'MORE'. Respond ONLY with 'ENOUGH' or 'MORE'.")
    context_msg = HumanMessage(content=f"Original Query: {query}\n\nGathered Items:\n{items_list}\n\nNotes:\n{data}")
    
    try:
        response = await llm.ainvoke([system_msg, context_msg])
        decision = response.content.strip().upper()
    except Exception as e:
        logger.error(f"Evaluating LLM Error: {e}. Defaulting to Writer.")
        decision = "ENOUGH"
    
    if "MORE" in decision:
        logger.info("[⚡ Supervisor] Data INSUFFICIENT, sending back to Researcher.")
        return "research"
    else:
        logger.info("[⚡ Supervisor] Data SUFFICIENT, moving to Writer.")
        return "writer"


async def writer_node(state: AgentState):
    logger.info("[✍️  Node] Writer Agent composing final answer...")
    user_query = cast(str, state.get("query", ""))
    items_list = cast(List[Dict[str, Any]], state.get("inventory_items", []))
    research_text = cast(str, state.get("research_data", ""))
    
    system_msg = SystemMessage(content="You are a Writer Agent. Write a friendly, concise answer. If there are items, mention their stock. If the user asked a general/policy question, answer it using the Research Data provided. Do NOT output JSON. Do NOT invent details.")
    context_msg = HumanMessage(content=f"Query: {user_query}\nItems found:\n{items_list}\nResearch Data:\n{research_text}")
    
    try:
        response = await llm.ainvoke([system_msg, context_msg])
        message = response.content.strip()
    except Exception as e:
        logger.error(f"Writer LLM Error: {e}")
        message = "There was an error generating your response, but here is what we found in our database."
    
    products = []
    for item in items_list:
        products.append({
            "name": item.get("name", "unknown"),
            "stock": item.get("stock", 0),
            "price": item.get("price", 0.0)
        })
    
    return {"final_answer": {"message": message, "products": products}}


# 5. Build the Graph
def build_workflow():
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("research", research_node)
    workflow.add_node("writer", writer_node)
    
    workflow.add_edge(START, "supervisor")
    workflow.add_edge("supervisor", "research")
    workflow.add_conditional_edges("research", evaluate_research, {"research": "research", "writer": "writer"})
    workflow.add_edge("writer", END)
    
    return workflow.compile()

# --- FastAPI Setup ---
app_instance = FastAPI(title="Lushio AI Multi-Agent API")

# Add CORS Middleware to allow requests from the frontend HTML file
app_instance.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for local testing)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

workflow_app = build_workflow()

# Mount Static Files for Frontend
# Current file is in src/, so we go up one level to find the frontend directory
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app_instance.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    logger.warning(f"Frontend path {frontend_path} not found!")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    items_found: List[Dict[str, Any]]
    final_answer: Dict[str, Any]
    execution_time_seconds: float

# Very simple dictionary-based exact-match cache for demonstration
# In production, use Redis or semantic-caching libraries (like GPTCache)
QUERY_CACHE = {}

@app_instance.get("/")
async def root():
    # If index.html exists, suggest opening /static/index.html
    return {
        "message": "Welcome to Lushio AI Multi-Agent API",
        "frontend": "/static/index.html",
        "endpoints": {
            "ask": "/ask (POST)",
            "docs": "/docs (GET)"
        }
    }

@app_instance.post("/ask", response_model=QueryResponse)
async def ask_agent(request: QueryRequest):
    logger.info(f"Incoming request: {request.query}")
    start_time = time.time()
    
    # Cache Check
    normalized_query = request.query.strip().lower()
    if normalized_query in QUERY_CACHE:
        logger.info("[⚡ CACHE HIT] Returning cached response.")
        cached_response = QUERY_CACHE[normalized_query]
        # Format to 2 decimal places using string formatting to avoid round() lint issues
        execution_time = float(f"{(time.time() - start_time):.2f}")
        return {
            "query": request.query,
            "items_found": cast(List[Dict[str, Any]], cached_response.get("items_found", [])),
            "final_answer": cast(Dict[str, Any], cached_response.get("final_answer", {})),
            "execution_time_seconds": execution_time
        }
    
    initial_state = {
        "query": request.query,
        "inventory_items": [],
        "research_data": "",
        "research_iterations": 0
    }
    
    try:
        # Use ainvoke for async graph call
        final_state = await workflow_app.ainvoke(initial_state)
    except ValueError as val_e:
        logger.error(f"Agent validation error: {str(val_e)}")
        raise HTTPException(status_code=400, detail=str(val_e))
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred while processing your request. Please try again later.")
    
    execution_time = float(f"{(time.time() - start_time):.2f}")
    logger.info(f"Request completed in {execution_time}s")
    
    response_data = {
        "query": request.query,
        "items_found": cast(List[Dict[str, Any]], final_state.get("inventory_items", [])),
        "final_answer": cast(Dict[str, Any], final_state.get("final_answer", {})),
        "execution_time_seconds": execution_time
    }
    
    # Save to Cache
    QUERY_CACHE[normalized_query] = response_data
    
    return response_data

if __name__ == "__main__":
    print("\n🚀 Starting Lushio AI FastAPI Server...")
    uvicorn.run(app_instance, host="0.0.0.0", port=8000)
