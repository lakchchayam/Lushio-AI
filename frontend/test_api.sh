#!/bin/bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"query": "Hello"}'
