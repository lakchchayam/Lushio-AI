import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

# Load environment variables from .env file
load_dotenv()

def test_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        print("Error: GROQ_API_KEY is missing or invalid in the .env file.")
        print("Please add your actual Groq API key to the .env file and try again.")
        return

    print("Initializing Groq client...")
    try:
        # Initialize the ChatGroq client (LangChain integration)
        # We use a fast and capable open-source model available on Groq (Llama 3)
        llm = ChatGroq(
            temperature=0.7,
            model_name="llama-3.1-8b-instant", 
            api_key=api_key
        )
        
        # Test the model with a simple prompt
        print("Sending request to Groq API...")
        message = HumanMessage(content="Say 'Hello, Lushio AI is ready with Groq!'")
        
        response = llm.invoke([message])
        
        print("\n--- LLM Response ---")
        print(response.content)
        print("--------------------")
        print("\n✅ Success! The LLM is working correctly using Groq.")
        
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")

if __name__ == "__main__":
    test_llm()
