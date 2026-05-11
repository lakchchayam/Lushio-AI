# Lushio AI — Enterprise Fitness Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)
![MCP](https://img.shields.io/badge/Protocol-MCP-blueviolet.svg)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)
![GCP](https://img.shields.io/badge/Cloud-GCP%20%7C%20AWS-4285F4.svg)

The public-facing documentation and architecture reference for **Lushio AI** — a production-grade, multi-agent AI platform built for the fitness and wellness industry. The system orchestrates specialized AI agents across enterprise workflows including booking management, personalized coaching, content generation, and business analytics.

> ⚠️ **Note:** Proprietary business logic, API keys, and internal service code are not included in this public repository. This repo contains architectural documentation, system design references, and open-source modules.

## 🌟 System Overview

Lushio AI is a fully integrated agentic intelligence layer deployed across Lushio Fitness's enterprise stack. It processes **100K+ transactions monthly** and serves as the AI backbone for:

- **Stays AI**: Booking intent detection, automated follow-up, and personalized accommodation recommendations
- **Gym AI**: Workout plan generation, progress tracking, and member churn prediction
- **Brand AI**: Social content generation, campaign optimization, and competitive analysis

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CLIENT INTERFACES                      │
│         (Web App · Mobile · Internal Dashboard)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  API GATEWAY (FastAPI)                   │
│         Auth · Rate Limiting · Request Routing           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│            AGENTIC ORCHESTRATION LAYER                   │
│                   (LangGraph)                            │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Supervisor  │  │  Researcher  │  │    Writer     │  │
│  │    Agent     │  │    Agent     │  │    Agent      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         └────────────────┬┴───────────────────┘          │
│                          ▼                               │
│              ┌───────────────────────┐                   │
│              │     MCP Tool Layer    │                   │
│              │  (FastMCP Servers)    │                   │
│              └───────────┬───────────┘                   │
└──────────────────────────┼──────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   [PostgreSQL DB]   [Vector Store]   [External APIs]
   [SQLAlchemy]      [Pinecone/FAISS] [Booking · CRM · Analytics]
```

## ⚙️ Core Technical Components

### 1. Multi-Agent Orchestration (LangGraph)
A **Supervisor-Worker** pattern where the Supervisor agent decomposes incoming requests and delegates to specialized workers. Workers communicate through a shared, typed state graph with automatic retry on failure.

### 2. MCP Tool Layer (FastMCP)
Custom **Model Context Protocol** servers expose business data sources (bookings DB, member profiles, inventory) to agents through a standardized, secure interface. The MCP layer enforces read-only access and injects row-level security filters.

### 3. RAG Knowledge Pipeline
- **Ingestion**: Documents, SOPs, and FAQs ingested via automated pipeline
- **Chunking**: Sliding-window with 200-token overlap
- **Storage**: PGVector (PostgreSQL) for structured retrieval, Pinecone for semantic search
- **Retrieval**: Hybrid BM25 + dense retrieval with query-time reranking
- **Hallucination Control**: Reduced by 35% via source-grounded prompting

### 4. LLM Evaluation & Monitoring
- Automated evaluation runs on every model/prompt change
- **Faithfulness, Context Relevancy, Answer Relevancy** tracked per agent
- Drift detection alerts when metric drops > 5% from baseline

## 📊 Production Metrics

| Metric | Value |
|---|---|
| Monthly transactions processed | 100K+ |
| Production uptime | 99.2% |
| Hallucination rate reduction | 35% |
| Domain accuracy improvement (PEFT) | 28% |
| Inference latency (P95) | < 800ms |
| Active agent workflows | 6 |

## 🛠️ Full Tech Stack

**AI/ML:** LangGraph, LangChain, FastMCP, Gemini, GPT-4o, Claude, FAISS, Pinecone, sentence-transformers, PEFT/SFT  
**Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL, PGVector, Redis  
**Infrastructure:** GCP, AWS, Docker, Kubernetes, CI/CD (GitHub Actions), Terraform  
**Monitoring:** LangSmith, Evidently AI, Prometheus, Grafana

## 📁 Repository Structure

```
├── docs/                    # Architecture diagrams and system design docs
├── mcp-servers/             # Open-source MCP tool implementations
├── eval-framework/          # LLM evaluation harness (open-sourced)
├── prompts/                 # Versioned prompt templates
└── notebooks/               # Architecture exploration notebooks
```

## 📄 Related Open-Source Projects

Projects extracted from the Lushio AI codebase and open-sourced:

- 🔗 [enterprise-agentic-orchestrator](https://github.com/lakchchayam/enterprise-agentic-orchestrator) — The core orchestration engine
- 🔗 [mcp-sql-analyst](https://github.com/lakchchayam/mcp-sql-analyst) — MCP server for database querying
- 🔗 [rag-eval-harness](https://github.com/lakchchayam/rag-eval-harness) — The evaluation framework
