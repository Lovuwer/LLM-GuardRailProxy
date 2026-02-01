"""
Main entry point for the LLM Guardrail Proxy application.
This file is used by deployment platforms like Railpack to start the FastAPI server.
"""
from app.main import app

__all__ = ["app"]
