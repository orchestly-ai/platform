#!/usr/bin/env python3
"""
MCP Service Wrapper Template

This template shows how to wrap your existing service APIs as MCP tools.
Replace YOUR_SERVICE with your actual service (fintech, hr-tech, healthcare, etc.)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx
import uvicorn
import os

# Configuration for your existing service
YOUR_SERVICE_NAME = "fintech-expense"  # Change this
YOUR_SERVICE_URL = os.getenv("EXPENSE_SERVICE_URL", "http://localhost:9001")  # Your actual service URL
MCP_PORT = 8004  # Port for this MCP wrapper

app = FastAPI(title=f"{YOUR_SERVICE_NAME} MCP Server")

class MCPRequest(BaseModel):
    """Standard MCP request format"""
    id: str
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    """Standard MCP response format"""
    id: str
    result: Dict[str, Any]

class ToolCallRequest(BaseModel):
    """Tool invocation request"""
    name: str
    arguments: Dict[str, Any]

# MCP Server Info
@app.get(f"/mcp/{YOUR_SERVICE_NAME.replace('-', '_')}")
async def server_info():
    """Return MCP server information"""
    return {
        "name": f"{YOUR_SERVICE_NAME}-server",
        "version": "0.1.0",
        "protocolVersion": "0.1.0",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        }
    }

# MCP Initialize
@app.post(f"/mcp/{YOUR_SERVICE_NAME.replace('-', '_')}/initialize")
async def initialize(request: MCPRequest):
    """Initialize the MCP connection"""
    return MCPResponse(
        id=request.id,
        result={
            "protocolVersion": "0.1.0",
            "capabilities": {
                "tools": True,
                "resources": False,
                "prompts": False
            },
            "serverInfo": {
                "name": f"{YOUR_SERVICE_NAME}-server",
                "version": "0.1.0"
            }
        }
    )

# List Available Tools - CUSTOMIZE THIS FOR YOUR SERVICE
@app.post(f"/mcp/{YOUR_SERVICE_NAME.replace('-', '_')}/tools/list")
async def list_tools(request: MCPRequest):
    """
    List all available tools from your service.

    CUSTOMIZE THIS: Add your service's actual APIs as tools
    """
    tools = [
        # Example: Expense Service Tools
        {
            "name": "create_expense_report",
            "description": "Create a new expense report",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "employee_id": {
                        "type": "string",
                        "description": "Employee ID"
                    },
                    "department": {
                        "type": "string",
                        "description": "Department name"
                    },
                    "expenses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "date": {"type": "string", "format": "date"},
                                "category": {"type": "string"},
                                "amount": {"type": "number"},
                                "description": {"type": "string"}
                            }
                        },
                        "description": "List of expenses"
                    }
                },
                "required": ["employee_id", "expenses"]
            }
        },
        {
            "name": "approve_expense",
            "description": "Approve or reject an expense report",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "report_id": {
                        "type": "string",
                        "description": "Expense report ID"
                    },
                    "approved": {
                        "type": "boolean",
                        "description": "Approval decision"
                    },
                    "comments": {
                        "type": "string",
                        "description": "Approval comments"
                    }
                },
                "required": ["report_id", "approved"]
            }
        },
        {
            "name": "get_expense_summary",
            "description": "Get expense summary for a period",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date"
                    },
                    "department": {
                        "type": "string",
                        "description": "Filter by department (optional)"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        },
        {
            "name": "match_receipt",
            "description": "Match a receipt to a transaction using AI",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "receipt_image_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "URL of receipt image"
                    },
                    "transaction_id": {
                        "type": "string",
                        "description": "Transaction ID to match"
                    }
                },
                "required": ["receipt_image_url"]
            }
        }
    ]

    return MCPResponse(
        id=request.id,
        result={"tools": tools}
    )

# Execute Tool - CUSTOMIZE THIS FOR YOUR SERVICE
@app.post(f"/mcp/{YOUR_SERVICE_NAME.replace('-', '_')}/tools/call")
async def call_tool(request: ToolCallRequest):
    """
    Execute a tool by calling your actual service API.

    CUSTOMIZE THIS: Route to your actual service endpoints
    """

    async with httpx.AsyncClient() as client:
        try:
            if request.name == "create_expense_report":
                # Call your actual expense service API
                response = await client.post(
                    f"{YOUR_SERVICE_URL}/api/expense-reports",
                    json={
                        "employeeId": request.arguments.get("employee_id"),
                        "department": request.arguments.get("department"),
                        "expenses": request.arguments.get("expenses")
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"Expense report created successfully!\n"
                                   f"Report ID: {result.get('reportId', 'N/A')}\n"
                                   f"Total: ${result.get('total', 0)}\n"
                                   f"Status: {result.get('status', 'Pending')}"
                        }]
                    }
                else:
                    # For demo, return mock response
                    return {
                        "content": [{
                            "type": "text",
                            "text": "Expense report created (mock)!\n"
                                   "Report ID: EXP-2026-001\n"
                                   "Total: $1,234.56\n"
                                   "Status: Pending Approval"
                        }]
                    }

            elif request.name == "approve_expense":
                # Call your actual expense approval API
                response = await client.put(
                    f"{YOUR_SERVICE_URL}/api/expense-reports/{request.arguments.get('report_id')}/approve",
                    json={
                        "approved": request.arguments.get("approved"),
                        "comments": request.arguments.get("comments", "")
                    }
                )

                # Mock response for demo
                status = "Approved" if request.arguments.get("approved") else "Rejected"
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Expense report {request.arguments.get('report_id')} {status}!\n"
                               f"Comments: {request.arguments.get('comments', 'None')}"
                    }]
                }

            elif request.name == "get_expense_summary":
                # Call your actual expense summary API
                params = {
                    "startDate": request.arguments.get("start_date"),
                    "endDate": request.arguments.get("end_date")
                }
                if request.arguments.get("department"):
                    params["department"] = request.arguments["department"]
                if request.arguments.get("category"):
                    params["category"] = request.arguments["category"]

                response = await client.get(
                    f"{YOUR_SERVICE_URL}/api/expense-reports/summary",
                    params=params
                )

                # Mock response for demo
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Expense Summary ({request.arguments.get('start_date')} to {request.arguments.get('end_date')}):\n"
                               f"Total Expenses: $45,678.90\n"
                               f"Number of Reports: 23\n"
                               f"Average per Report: $1,986.04\n"
                               f"Top Categories:\n"
                               f"  - Travel: $18,234.56\n"
                               f"  - Meals: $12,456.78\n"
                               f"  - Office Supplies: $8,234.12\n"
                               f"Pending Approval: 5 reports ($6,789.00)"
                    }]
                }

            elif request.name == "match_receipt":
                # Call your actual receipt matching API (if exists)
                # This might use AI/ML services in your backend
                receipt_url = request.arguments.get("receipt_image_url")
                transaction_id = request.arguments.get("transaction_id")

                # Mock response for demo
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Receipt Analysis Complete:\n"
                               f"Receipt URL: {receipt_url}\n"
                               f"Merchant: Starbucks\n"
                               f"Amount: $12.45\n"
                               f"Date: 2026-01-27\n"
                               f"Confidence: 94%\n"
                               f"Matched to Transaction: {transaction_id or 'TXN-2026-0127-001'}\n"
                               f"Category: Meals & Entertainment"
                    }]
                }

            else:
                raise HTTPException(status_code=404, detail=f"Tool '{request.name}' not found")

        except httpx.RequestError as e:
            # If actual service is not available, return mock response
            return {
                "content": [{
                    "type": "text",
                    "text": f"Service temporarily unavailable (using mock): {str(e)}"
                }]
            }

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": f"{YOUR_SERVICE_NAME}-mcp-server"}

if __name__ == "__main__":
    print(f"💼 Starting {YOUR_SERVICE_NAME} MCP Server...")
    print(f"   Endpoint: http://localhost:{MCP_PORT}/mcp/{YOUR_SERVICE_NAME.replace('-', '_')}")
    print(f"   Wrapping service at: {YOUR_SERVICE_URL}")
    print(f"   Available tools:")
    print(f"     - create_expense_report")
    print(f"     - approve_expense")
    print(f"     - get_expense_summary")
    print(f"     - match_receipt")
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)