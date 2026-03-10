#!/usr/bin/env python3
"""
Simple Calculator MCP Server

A Model Context Protocol server that provides basic calculator functionality.
Implements the MCP specification for tool discovery and invocation.
"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
import json
import asyncio
from datetime import datetime
import math

app = FastAPI(title="Calculator MCP Server", version="1.0.0")

# MCP Protocol Models
class InitializeRequest(BaseModel):
    protocol_version: str = Field(default="2024-11-05")
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    client_info: Optional[Dict[str, Any]] = None

class InitializeResponse(BaseModel):
    protocol_version: str = "2024-11-05"
    capabilities: Dict[str, bool] = {
        "tools": True,
        "resources": False,
        "prompts": False,
        "sampling": False,
        "roots": False
    }
    server_info: Dict[str, str] = {
        "name": "calculator-mcp-server",
        "version": "1.0.0",
        "vendor": "Example"
    }

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]

class ListToolsResponse(BaseModel):
    tools: List[ToolDefinition]

class CallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class CallToolResponse(BaseModel):
    content: List[Dict[str, Any]]

# Calculator Tools
CALCULATOR_TOOLS = [
    ToolDefinition(
        name="add",
        description="Add two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    ),
    ToolDefinition(
        name="subtract",
        description="Subtract two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    ),
    ToolDefinition(
        name="multiply",
        description="Multiply two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"}
            },
            "required": ["a", "b"]
        }
    ),
    ToolDefinition(
        name="divide",
        description="Divide two numbers",
        input_schema={
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Dividend"},
                "b": {"type": "number", "description": "Divisor (cannot be zero)"}
            },
            "required": ["a", "b"]
        }
    ),
    ToolDefinition(
        name="sqrt",
        description="Calculate square root of a number",
        input_schema={
            "type": "object",
            "properties": {
                "n": {"type": "number", "description": "Number to calculate square root of"}
            },
            "required": ["n"]
        }
    ),
    ToolDefinition(
        name="power",
        description="Raise a number to a power",
        input_schema={
            "type": "object",
            "properties": {
                "base": {"type": "number", "description": "Base number"},
                "exponent": {"type": "number", "description": "Exponent"}
            },
            "required": ["base", "exponent"]
        }
    )
]

# MCP Endpoints
@app.get("/mcp/calculator")
async def mcp_info():
    """MCP server information endpoint"""
    return {
        "name": "Calculator MCP Server",
        "version": "1.0.0",
        "protocol_version": "2024-11-05",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False,
            "sampling": False,
            "roots": False
        }
    }

@app.post("/mcp/calculator/initialize")
async def initialize(request: InitializeRequest):
    """Initialize MCP session"""
    return InitializeResponse()

@app.post("/mcp/calculator/tools/list")
async def list_tools():
    """List available calculator tools"""
    return ListToolsResponse(tools=CALCULATOR_TOOLS)

@app.post("/mcp/calculator/tools/call")
async def call_tool(request: CallToolRequest):
    """Execute a calculator tool"""
    try:
        args = request.arguments
        result = None

        if request.name == "add":
            result = args["a"] + args["b"]
        elif request.name == "subtract":
            result = args["a"] - args["b"]
        elif request.name == "multiply":
            result = args["a"] * args["b"]
        elif request.name == "divide":
            if args["b"] == 0:
                return CallToolResponse(content=[{
                    "type": "text",
                    "text": "Error: Division by zero"
                }])
            result = args["a"] / args["b"]
        elif request.name == "sqrt":
            if args["n"] < 0:
                return CallToolResponse(content=[{
                    "type": "text",
                    "text": "Error: Cannot calculate square root of negative number"
                }])
            result = math.sqrt(args["n"])
        elif request.name == "power":
            result = math.pow(args["base"], args["exponent"])
        else:
            return CallToolResponse(content=[{
                "type": "text",
                "text": f"Error: Unknown tool '{request.name}'"
            }])

        return CallToolResponse(content=[{
            "type": "text",
            "text": str(result)
        }])

    except Exception as e:
        return CallToolResponse(content=[{
            "type": "text",
            "text": f"Error: {str(e)}"
        }])

# SSE Support for streaming
@app.get("/mcp/calculator/sse")
async def sse_endpoint():
    """Server-sent events endpoint for MCP"""
    async def event_generator():
        yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now().isoformat()})}\n\n"
        while True:
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now().isoformat()})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "calculator-mcp-server"}

# CORS headers for browser access
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

if __name__ == "__main__":
    print("Starting Calculator MCP Server on http://localhost:8001")
    print("MCP endpoint: http://localhost:8001/mcp/calculator")
    print("Tools available: add, subtract, multiply, divide, sqrt, power")
    uvicorn.run(app, host="0.0.0.0", port=8001)