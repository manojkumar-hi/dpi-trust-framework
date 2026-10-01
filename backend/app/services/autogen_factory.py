import os
import uuid
import httpx
from datetime import datetime, timezone
from typing import Any, Callable

from autogen_agentchat.agents import AssistantAgent
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.services.agent_templates.registry import get_template
from app.services.identity_service import get_identity_for_agent

def _build_dpi_autogen_tool(
    tool_name: str,
    tool_description: str,
    action_type: str,
    base_url: str,
    vp_jwt: str,
    challenge_id: str,
    source_agent_did: str,
    target_agent_did: str,
    httpx_client: httpx.AsyncClient | None = None
) -> FunctionTool:
    """Wraps a tool to execute through the DPI Gateway over HTTP."""
    async def dpi_tool_wrapper(**kwargs: Any) -> str:
        request_data = {
            "challenge_id": challenge_id,
            "source_agent_did": source_agent_did,
            "target_agent_did": target_agent_did,
            "action_type": action_type,
            "resource_id": "none",
            "payload": kwargs,
            "delegation_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "authentication_proof": {
                "type": "VerifiablePresentation",
                "vp_jwt": vp_jwt
            }
        }
        headers = {"Idempotency-Key": str(uuid.uuid4())}
        
        if httpx_client:
            response = await httpx_client.post("/gateway/action", json=request_data, headers=headers)
        else:
            async with httpx.AsyncClient(base_url=base_url) as client:
                response = await client.post("/gateway/action", json=request_data, headers=headers)
                
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get("status") == "SUCCESS":
                res = result_data.get("result")
                return str(res.get("result") if isinstance(res, dict) and "result" in res else res)
            return f"Action failed: {result_data.get('error')}"
        return f"Error {response.status_code}: {response.text}"

    return FunctionTool(
        dpi_tool_wrapper,
        name=tool_name,
        description=tool_description
    )


def create_domain_agent(
    db: Session,
    agent_id: uuid.UUID,
    base_url: str,
    vp_jwt: str,
    challenge_id: str,
    target_agent_did: str,
    httpx_client: httpx.AsyncClient | None = None
) -> AssistantAgent:
    """
    Factory to instantiate a domain-specific AutoGen AssistantAgent.
    Loads the Agent from the DB, resolves its template, and wraps its tools via DPI Gateway.
    """
    agent = db.get(Agent, agent_id)
    if not agent:
        raise ValueError("Agent not found")
    
    if not agent.template_id or not agent.template_version:
        raise ValueError("Agent is not a template-based agent")

    template = get_template(agent.template_id)
    if not template or template.template_version != agent.template_version:
        raise ValueError("Template not found or version mismatch")

    identity = get_identity_for_agent(db, agent_id)
    if not identity:
        raise ValueError("Agent identity not found")

    tools = []
    for tool_def in template.tools:
        # Wrap each tool with the DPI Gateway wrapper
        dpi_tool = _build_dpi_autogen_tool(
            tool_name=tool_def.name,
            tool_description=tool_def.description,
            action_type=tool_def.capability_code,
            base_url=base_url,
            vp_jwt=vp_jwt,
            challenge_id=challenge_id,
            source_agent_did=identity.did,
            target_agent_did=target_agent_did,
            httpx_client=httpx_client
        )
        tools.append(dpi_tool)

    model_client = OpenAIChatCompletionClient(
        model="llama3-8b-8192",
        api_key=os.environ.get("GROQ_API_KEY", "dummy"),
        base_url="https://api.groq.com/openai/v1",
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "unknown",
        }
    )

    return AssistantAgent(
        name=agent.name.replace(" ", "_"),
        system_message=template.system_prompt,
        model_client=model_client,
        tools=tools,
        reflect_on_tool_use=True
    )
