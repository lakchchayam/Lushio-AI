import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from typing import List
from pinecone import Pinecone, ServerlessSpec

# Load environment variables (needs PINECONE_API_KEY)
load_dotenv()

PINECONE_INDEX_NAME = "lushio-rag"
# Path relative to src/
DOC_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "faq.txt")

def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the embedding model. Using a free local SentenceTransformer model."""
    # This downloads the model locally the first time.
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def ingest_documents():
    """Load faq.txt, split it, embed it, and upload to Pinecone."""
    print(f"Loading document: {DOC_PATH}")
    loader = TextLoader(DOC_PATH)
    docs = loader.load()

    print("Splitting text into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    splits = text_splitter.split_documents(docs)
    print(f"Created {len(splits)} document chunks.")

    # Validate Pinecone API key
    if not os.environ.get("PINECONE_API_KEY"):
        raise ValueError("PINECONE_API_KEY not found in environment variables. Please set it in .env")

    print(f"Initializing embeddings and connecting to Pinecone index: '{PINECONE_INDEX_NAME}'...")
    embeddings = get_embeddings()
    
    # Initialize Pinecone Client
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    
    # Create index if it doesn't exist
    if PINECONE_INDEX_NAME not in pc.list_indexes().names():
        print(f"Index '{PINECONE_INDEX_NAME}' does not exist. Creating it now... (this may take a minute)")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=384, # all-MiniLM-L6-v2 produces 384-dimensional embeddings
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        
        # Wait for index to be ready
        while not pc.describe_index(PINECONE_INDEX_NAME).status["ready"]:
            print("Waiting for index to be ready...")
            time.sleep(2)

    # Create/Initialize vector store
    PineconeVectorStore.from_documents(
        documents=splits,
        embedding=embeddings,
        index_name=PINECONE_INDEX_NAME
    )
    print("✅ Ingestion complete! Documents are now stored in Pinecone.")

if __name__ == "__main__":
    ingest_documents()
