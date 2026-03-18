import os
import json
import logging
from typing import Any, List, Dict
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

# Configure Logging
logger = logging.getLogger("LushioTools")

def load_inventory() -> Dict:
    """Load the inventory from the local JSON file."""
    inventory_path = os.path.join(os.path.dirname(__file__), "inventory.json")
    with open(inventory_path, "r") as f:
        return json.load(f)

@tool
def check_inventory(product_name: str) -> Dict[str, Any]:
    """Check the inventory stock and price for a given product. Returns a structured dictionary."""
    inventory_data = load_inventory()
    logger.info(f"[⚙️  Tool] check_inventory('{product_name}')")
    
    product_lower = product_name.lower().strip()
    
    for category, items in inventory_data.items():
        for item_name, details in items.items():
            if item_name in product_lower or product_lower in item_name:
                return {
                    "name": item_name,
                    "stock": details["stock"],
                    "price": details["price"],
                    "status": "found"
                }
    
    return {
        "name": product_name,
        "stock": 0,
        "price": 0.0,
        "status": "not_found"
    }

@tool
def search_documents(query: str) -> str:
    """Search the store's FAQ and policies for answers to general questions like returns, shipping, warranty, etc."""
    logger.info(f"[⚙️  Tool] search_documents('{query}')")
    if not os.environ.get("PINECONE_API_KEY"):
        logger.error("PINECONE_API_KEY is not set.")
        return "Error: PINECONE_API_KEY is not set."
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = PineconeVectorStore(index_name="lushio-rag", embedding=embeddings)
    
    docs = vectorstore.similarity_search(query, k=3)
    if not docs:
        return "No relevant documents found."
    
    context = "\n\n".join([doc.page_content for doc in docs])
    return f"Found Information:\n{context}"
