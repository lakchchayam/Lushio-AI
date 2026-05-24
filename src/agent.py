import json
import time
import logging
import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from typing import Any, List, Dict, cast
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LushioAgent")

# Load environment variables
load_dotenv()

# Initialize Gemini 2.5 Flash - fastest model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
    google_api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "AIzaSyDcDBFDKXvUidx8Nfr8s-gb8ijLhZEohmw",
)

# ---- Inventory Tool (direct, no MCP overhead) ----
def load_inventory() -> Dict:
    inventory_path = os.path.join(os.path.dirname(__file__), "inventory.json")
    with open(inventory_path, "r") as f:
        return json.load(f)

def check_inventory_direct(product_name: str) -> Dict[str, Any]:
    inventory_data = load_inventory()
    product_lower = product_name.lower().strip()
    for category, items in inventory_data.items():
        for item_name, details in items.items():
            if item_name in product_lower or product_lower in item_name:
                return {"name": item_name, "stock": details["stock"], "price": details["price"], "status": "found"}
    return {"name": product_name, "stock": 0, "price": 0.0, "status": "not_found"}

def get_all_inventory() -> List[Dict[str, Any]]:
    """Return all products from inventory"""
    inventory_data = load_inventory()
    products = []
    for category, items in inventory_data.items():
        for item_name, details in items.items():
            products.append({"name": item_name, "stock": details["stock"], "price": details["price"], "category": category})
    return products

# Simple in-memory cache
QUERY_CACHE: Dict[str, Any] = {}

# ---- FastAPI App ----
app_instance = FastAPI(title="Lushio AI Inventory API")

app_instance.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_path):
    app_instance.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    items_found: List[Dict[str, Any]]
    final_answer: Dict[str, Any]
    execution_time_seconds: float

@app_instance.get("/")
async def root():
    return {
        "message": "Welcome to Lushio AI Inventory API",
        "frontend": "/static/index.html",
        "endpoints": {"ask": "/ask (POST)", "docs": "/docs (GET)"}
    }

@app_instance.post("/ask", response_model=QueryResponse)
async def ask_agent(request: QueryRequest):
    logger.info(f"Incoming: {request.query}")
    start_time = time.time()

    # Cache check
    cache_key = request.query.strip().lower()
    if cache_key in QUERY_CACHE:
        cached = QUERY_CACHE[cache_key]
        return {**cached, "execution_time_seconds": round(time.time() - start_time, 2)}

    # Get all inventory for context
    all_products = get_all_inventory()
    inventory_context = json.dumps(all_products, indent=2)

    # Single LLM call with full inventory context
    system_msg = SystemMessage(content=f"""You are Lushio AI, a friendly inventory assistant.
You have access to the REAL inventory database below. ONLY use data from this database - never make up products or stock levels.

CURRENT INVENTORY:
{inventory_context}

Instructions:
- Answer questions based ONLY on the inventory data above
- Be friendly and concise
- If a product is not in the inventory, clearly say it's not available
- Mention the price and stock count when relevant""")

    user_msg = HumanMessage(content=request.query)

    try:
        response = await llm.ainvoke([system_msg, user_msg])
        message = response.content.strip()
    except Exception as e:
        logger.error(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze request: {e}")

    # Find matching products mentioned in the query
    query_lower = request.query.lower()
    matched_items = []
    for product in all_products:
        if any(word in query_lower for word in product["name"].split()):
            matched_items.append(product)
    # If no specific match, return all if query is about general availability
    if not matched_items and any(word in query_lower for word in ["all", "sab", "everything", "available", "stock", "inventory"]):
        matched_items = all_products

    result = {
        "query": request.query,
        "items_found": matched_items,
        "final_answer": {"message": message, "products": matched_items},
        "execution_time_seconds": round(time.time() - start_time, 2)
    }

    QUERY_CACHE[cache_key] = result
    logger.info(f"Completed in {result['execution_time_seconds']}s")
    return result

if __name__ == "__main__":
    uvicorn.run(app_instance, host="0.0.0.0", port=8080)
