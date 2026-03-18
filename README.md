<h1 align="center">
  🧠 Lushio AI
</h1>

<p align="center">
  <strong>A Multi-Agent AI Shopping Assistant powered by LangGraph, Groq, Pinecone & MCP</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/LangGraph-Orchestration-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Groq-LLaMA%203.1-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Pinecone-VectorDB-teal?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Docker-Containerized-blue?style=for-the-badge&logo=docker" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

---

## 📌 Overview

**Lushio AI** is an intelligent, multi-agent shopping assistant designed for e-commerce stores. It uses a **Supervisor–Researcher–Writer** agent pattern orchestrated via **LangGraph**, with tools exposed through the **Model Context Protocol (MCP)** server. The system can answer questions about product inventory, stock levels, pricing, store policies, returns, and FAQs — all in natural language.

Whether you ask *"Do you have laptops in stock?"* or *"What is your return policy?"*, Lushio AI knows what tool to call, how to retrieve the answer, and how to respond in a friendly, human-readable format.

---

## ✨ Key Features

| Feature | Description |
|--------|-------------|
| 🤖 **Multi-Agent Pipeline** | Supervisor → Research → Writer pattern via LangGraph |
| 🔌 **MCP Integration** | Tool calls routed through FastMCP server for modular, extensible tooling |
| 🧠 **RAG (Retrieval-Augmented Generation)** | Semantic search over store FAQs & policies using Pinecone vector store |
| ⚡ **Response Caching** | In-memory query cache prevents redundant LLM calls for repeated questions |
| 🔁 **Self-Evaluation Loop** | Evaluator node decides if more research is needed before generating a final answer |
| 🌐 **REST API** | Clean FastAPI backend with Swagger UI at `/docs` |
| 🖥️ **Frontend UI** | Vanilla JS + HTML chat interface served as static files |
| 🐳 **Docker Ready** | Containerized for easy deployment on Render, Railway, or any cloud platform |

---

## 🏗️ Architecture

```
User Query (HTTP POST /ask)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                  LangGraph Workflow                      │
│                                                          │
│   ┌──────────────┐     ┌──────────────┐                  │
│   │  Supervisor  │────▶│  Researcher  │◀─────────┐       │
│   │    Node      │     │    Node      │          │       │
│   └──────────────┘     └──────┬───────┘          │       │
│                               │                  │       │
│                    ┌──────────▼──────────┐       │       │
│                    │   Self-Evaluator    │───────▶│       │
│                    │  (ENOUGH / MORE?)   │  MORE  │       │
│                    └──────────┬──────────┘       │       │
│                         ENOUGH│                  │       │
│                               ▼                  │       │
│                        ┌─────────────┐           │       │
│                        │   Writer    │           │       │
│                        │    Node     │           │       │
│                        └──────┬──────┘           │       │
└───────────────────────────────┼──────────────────┘       │
                                │                          │
                                ▼                          │
                       JSON Response ◀─── MCP Tools ───────┘
                                         │  inventory_lookup
                                         │  policy_search (RAG)
```

### Agent Roles

| Agent | Role |
|-------|------|
| **Supervisor** | Analyzes the query and decides which MCP tool to use and with what parameters |
| **Researcher** | Executes MCP tool calls (`inventory_lookup` or `policy_search`), gathers data |
| **Evaluator** | Checks if gathered data is sufficient; loops back to Researcher if not |
| **Writer** | Composes a friendly, human-readable final answer from the gathered data |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | [Groq](https://groq.com) – LLaMA 3.1 8B Instant (ultra-fast inference) |
| **Orchestration** | [LangGraph](https://langgraph.io) – stateful multi-agent graphs |
| **MCP Server** | [FastMCP](https://github.com/jlowin/fastmcp) – Model Context Protocol |
| **RAG / Embeddings** | [Pinecone](https://pinecone.io) + HuggingFace SentenceTransformers |
| **API Backend** | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn |
| **Frontend** | Vanilla HTML, CSS, JavaScript |
| **Containerization** | Docker |
| **Environment** | Python 3.12 |

---

## 📁 Project Structure

```
Lushio-AI/
├── src/
│   ├── agent.py          # LangGraph workflow, FastAPI server, cache logic
│   ├── tools.py          # LangChain tools (check_inventory, search_documents)
│   ├── mcp_server.py     # FastMCP server exposing inventory & policy tools
│   ├── ingest.py         # Script to ingest FAQs into Pinecone vector store
│   └── inventory.json    # Local inventory data (product name, stock, price)
├── frontend/
│   ├── index.html        # Chat UI
│   ├── app.js            # Frontend logic (fetch /ask, render responses)
│   └── style.css         # Styling
├── docs/
│   ├── faq.txt           # Store FAQs and policies (used for RAG ingestion)
│   ├── architecture.tex  # LaTeX source for architecture report
│   └── architecture.pdf  # Compiled architecture documentation
├── tests/                # Unit and integration tests
├── assets/               # Diagrams, screenshots, visualizations
├── Dockerfile            # Docker build configuration
├── requirements.txt      # Python dependencies
├── .gitignore            # Git ignore rules (venv, .env, etc.)
├── LICENSE               # MIT License
└── README.md             # This file
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- A [Groq API key](https://console.groq.com)
- A [Pinecone API key](https://app.pinecone.io)

### 1. Clone the Repository

```bash
git clone https://github.com/lakchchayam/Lushio-AI.git
cd Lushio-AI
```

### 2. Create a Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=lushio-policies
```

### 5. Ingest FAQs into Pinecone

Run the ingestion script to populate your Pinecone vector store with the store's FAQ and policy documents:

```bash
python -m src.ingest
```

### 6. Run the Server

```bash
python -m src.agent
```

The server starts at **http://localhost:8000**

- 📖 **Swagger UI**: http://localhost:8000/docs
- 🖥️ **Frontend Chat UI**: http://localhost:8000/static/index.html

---

## 🐳 Docker Deployment

### Build the Image

```bash
docker build -t lushio-ai .
```

### Run the Container

```bash
docker run -p 8000:8000 \
  -e GROQ_API_KEY=your_groq_api_key \
  -e PINECONE_API_KEY=your_pinecone_api_key \
  -e PINECONE_INDEX_NAME=lushio-policies \
  lushio-ai
```

---

## 📡 API Reference

### `POST /ask`

Send a natural language query and receive a structured response.

**Request Body:**
```json
{
  "query": "Do you have cameras in stock?"
}
```

**Response:**
```json
{
  "query": "Do you have cameras in stock?",
  "items_found": [
    { "name": "camera", "stock": 8, "price": 299.99 }
  ],
  "final_answer": {
    "message": "Great news! We have 8 cameras in stock at $299.99 each.",
    "products": [
      { "name": "camera", "stock": 8, "price": 299.99 }
    ]
  },
  "execution_time_seconds": 2.14
}
```

### `GET /`

Health check and API info.

---

## 🔌 MCP Tools

The MCP server (`src/mcp_server.py`) exposes two tools that the Research Agent calls:

| Tool | Description | Parameter |
|------|-------------|-----------|
| `inventory_lookup` | Returns stock level and price for a product | `product_name: str` |
| `policy_search` | Semantic search over store FAQs & policies | `query: str` |

---

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with verbose output
python -m pytest tests/ -v
```

---

## 📊 How the Self-Evaluation Loop Works

1. **Supervisor** reads the user query and instructs the Researcher on which tool to call.
2. **Researcher** calls the MCP tool and collects data into state.
3. **Evaluator** checks if the data is sufficient to answer the query:
   - Responds `ENOUGH` → routes to **Writer**.
   - Responds `MORE` → loops back to **Researcher** (up to 2 iterations max).
4. **Writer** generates a polished, friendly final response.

This loop prevents hallucination by ensuring the LLM only answers when it has real, retrieved data.

---

## 🔒 Security Notes

- **Never commit your `.env` file** — it is listed in `.gitignore`.
- The CORS configuration allows all origins (`*`) for local development. **Restrict this in production** to your specific frontend domain.
- Rotate your Groq and Pinecone API keys if they are ever exposed.

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 🙋 Author

**Lakch Chayam**  
[GitHub](https://github.com/lakchchayam) · [LinkedIn](https://linkedin.com/in/lakchchayam)

---

<p align="center">Made with ❤️ and a lot of LLM calls</p>
