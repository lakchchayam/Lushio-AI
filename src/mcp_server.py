import os
import logging
from fastmcp import FastMCP
try:
    from src.tools import check_inventory, search_documents
except ImportError:
    from tools import check_inventory, search_documents
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LushioMCPServer")

# Create an MCP server
mcp = FastMCP("Lushio AI Server")

@mcp.tool()
def inventory_lookup(product_name: str) -> str:
    """
    Check the current stock levels and pricing for a specific product.
    
    Args:
        product_name: The name of the product to look up (e.g., 'laptop', 'camera').
        
    Returns:
        A structured string containing 'name', 'stock', 'price', and 'status' (found/not_found).
    """
    logger.info(f"MCP Tool Call: inventory_lookup('{product_name}')")
    # Call the tool directly with the string argument
    result = check_inventory.invoke(product_name)
    return str(result)

@mcp.tool()
def policy_search(query: str) -> str:
    """
    Search the store's knowledge base for policies, FAQs, and general information.
    Use this for questions about returns, shipping, warranty, or store hours.
    
    Args:
        query: The specific question or topic to search for.
        
    Returns:
        A relevant text snippet from the store's documentation or 'No relevant documents found'.
    """
    logger.info(f"MCP Tool Call: policy_search('{query}')")
    # Call the tool directly with the string argument
    result = search_documents.invoke(query)
    return result

if __name__ == "__main__":
    mcp.run()
