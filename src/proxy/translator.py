"""
Anthropic Messages API <-> OpenAI Chat Completions API Translation Layer.
Translates requests and responses, including tool calls, schemas, and results.
"""

import json
import re
import uuid
from typing import Dict, Any, List, Optional, Tuple

def extract_json_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract a tool call from model output if the model emitted raw JSON or markdown code block.
    Supports formats:
      - ```json\n{"name": "...", "parameters": {...}}\n```
      - {"name": "...", "arguments": {...}}
      - <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    """
    if not text:
        return None

    # Check for <tool_call> tags
    tag_match = re.search(r"<tool_call>([\s\S]*?)</tool_call>", text)
    if tag_match:
        try:
            data = json.loads(tag_match.group(1).strip())
            if "name" in data:
                return data
        except Exception:
            pass

    # Check for markdown json code block
    block_match = re.search(r"```(?:json)?\s*(\{\s*\"name\"[\s\S]*?\})\s*```", text)
    if block_match:
        try:
            data = json.loads(block_match.group(1))
            if "name" in data:
                return data
        except Exception:
            pass

    # Check for raw JSON object with name & input/parameters/arguments
    raw_match = re.search(r'(\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"(?:parameters|arguments|input)"\s*:\s*\{[\s\S]*?\}\s*\})', text)
    if raw_match:
        try:
            data = json.loads(raw_match.group(1))
            if "name" in data:
                return data
        except Exception:
            pass

    return None

def anthropic_tools_to_openai(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Convert Anthropic tool definitions to OpenAI tool definitions."""
    if not tools:
        return None

    openai_tools = []
    for t in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}})
            }
        })
    return openai_tools

def anthropic_to_openai_request(anthropic_body: Dict[str, Any], default_model: str = "local-model") -> Dict[str, Any]:
    """Convert Anthropic Messages API request body to OpenAI Chat Completions body."""
    openai_messages = []

    # 1. System prompt
    system_val = anthropic_body.get("system")
    if system_val:
        if isinstance(system_val, list):
            sys_text = "\n".join(b.get("text", "") for b in system_val if b.get("type") == "text")
        else:
            sys_text = str(system_val)
        openai_messages.append({"role": "system", "content": sys_text})

    # 2. Messages
    for msg in anthropic_body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = []
            tool_calls = []
            for block in content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name", ""),
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })
                elif btype == "tool_result":
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(block.get("content", ""))
                    })

            if text_parts or tool_calls:
                msg_obj: Dict[str, Any] = {
                    "role": role,
                    "content": "\n".join(text_parts) if text_parts else None
                }
                if tool_calls:
                    msg_obj["tool_calls"] = tool_calls
                openai_messages.append(msg_obj)

    out: Dict[str, Any] = {
        "model": anthropic_body.get("model", default_model),
        "messages": openai_messages,
        "temperature": anthropic_body.get("temperature", 0.7),
        "max_tokens": anthropic_body.get("max_tokens", 2048),
        "stream": anthropic_body.get("stream", False),
    }

    if "stop_sequences" in anthropic_body:
        out["stop"] = anthropic_body["stop_sequences"]

    tools = anthropic_body.get("tools")
    if tools:
        openai_tools = anthropic_tools_to_openai(tools)
        if openai_tools:
            out["tools"] = openai_tools

    return out

def openai_to_anthropic_response(openai_resp: Dict[str, Any], req_model: str = "local-model") -> Dict[str, Any]:
    """Convert OpenAI Chat Completions response to Anthropic Messages API format."""
    choice = openai_resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    finish_reason = choice.get("finish_reason", "stop")
    content_text = msg.get("content") or ""
    if not content_text.strip() and msg.get("reasoning_content"):
        content_text = msg.get("reasoning_content").strip()

    anthropic_content = []
    stop_reason = "end_turn"

    # Check for native OpenAI tool_calls
    tool_calls = msg.get("tool_calls")
    if tool_calls:
        if content_text:
            anthropic_content.append({"type": "text", "text": content_text})
        for tc in tool_calls:
            fn = tc.get("function", {})
            try:
                fn_args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                fn_args = {"raw": fn.get("arguments", "")}
            anthropic_content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:12]}"),
                "name": fn.get("name", ""),
                "input": fn_args
            })
        stop_reason = "tool_use"
    else:
        # Check if model formatted tool call inside raw content
        parsed_call = extract_json_tool_call(content_text)
        if parsed_call:
            fn_name = parsed_call.get("name", "")
            fn_args = parsed_call.get("parameters") or parsed_call.get("arguments") or parsed_call.get("input") or {}
            # Clean content prefix if any
            clean_text = content_text[:content_text.find(fn_name)].strip()
            if clean_text and not clean_text.endswith("```"):
                anthropic_content.append({"type": "text", "text": clean_text})
            anthropic_content.append({
                "type": "tool_use",
                "id": f"toolu_{uuid.uuid4().hex[:12]}",
                "name": fn_name,
                "input": fn_args
            })
            stop_reason = "tool_use"
        else:
            anthropic_content.append({"type": "text", "text": content_text})
            if finish_reason == "length":
                stop_reason = "max_tokens"
            else:
                stop_reason = "end_turn"

    usage = openai_resp.get("usage", {})
    return {
        "id": f"msg_{uuid.uuid4().hex[:16]}",
        "type": "message",
        "role": "assistant",
        "model": req_model,
        "content": anthropic_content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", len(content_text.split()))
        }
    }
