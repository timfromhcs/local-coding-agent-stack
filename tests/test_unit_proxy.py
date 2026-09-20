"""
Unit tests for Proxy Translator: Anthropic Messages API <-> OpenAI Chat Completions.
Zero mocks: tests direct algorithmic and schema conversion across all branches.
"""

import pytest
import json
from src.proxy.translator import (
    anthropic_to_openai_request,
    openai_to_anthropic_response,
    extract_json_tool_call,
    anthropic_tools_to_openai,
)

def test_anthropic_to_openai_simple():
    anthropic_req = {
        "model": "claude-3-5-sonnet-20241022",
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "Hello, world!"}
        ],
        "max_tokens": 100
    }
    openai_req = anthropic_to_openai_request(anthropic_req)

    assert openai_req["max_tokens"] == 100
    assert len(openai_req["messages"]) == 2
    assert openai_req["messages"][0]["role"] == "system"
    assert openai_req["messages"][0]["content"] == "You are a helpful assistant."
    assert openai_req["messages"][1]["role"] == "user"
    assert openai_req["messages"][1]["content"] == "Hello, world!"

def test_anthropic_system_list():
    anthropic_req = {
        "system": [
            {"type": "text", "text": "Part 1 of system prompt."},
            {"type": "text", "text": "Part 2 of system prompt."}
        ],
        "messages": [{"role": "user", "content": "Hi"}],
        "stop_sequences": ["\n\nHuman:"]
    }
    openai_req = anthropic_to_openai_request(anthropic_req)
    assert len(openai_req["messages"]) == 2
    assert "Part 1 of system prompt." in openai_req["messages"][0]["content"]
    assert "Part 2 of system prompt." in openai_req["messages"][0]["content"]
    assert openai_req["stop"] == ["\n\nHuman:"]

def test_anthropic_messages_with_tool_blocks():
    anthropic_req = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Calling tool..."},
                    {"type": "tool_use", "id": "call_123", "name": "get_weather", "input": {"city": "Paris"}}
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_123", "content": "22C sunny"}
                ]
            }
        ]
    }
    openai_req = anthropic_to_openai_request(anthropic_req)
    assert len(openai_req["messages"]) == 2
    asst_msg = openai_req["messages"][0]
    assert asst_msg["role"] == "assistant"
    assert asst_msg["content"] == "Calling tool..."
    assert len(asst_msg["tool_calls"]) == 1
    assert asst_msg["tool_calls"][0]["id"] == "call_123"
    assert asst_msg["tool_calls"][0]["function"]["name"] == "get_weather"

    tool_msg = openai_req["messages"][1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_123"
    assert tool_msg["content"] == "22C sunny"

def test_anthropic_tools_translation():
    assert anthropic_tools_to_openai(None) is None
    assert anthropic_tools_to_openai([]) is None

    anthropic_tools = [
        {
            "name": "read_file",
            "description": "Read file contents",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        }
    ]
    openai_tools = anthropic_tools_to_openai(anthropic_tools)
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "read_file"
    assert openai_tools[0]["function"]["parameters"]["properties"]["path"]["type"] == "string"

def test_parse_tool_calls_from_markdown():
    text = """Let me write this file:
```json
{
  "name": "write_file",
  "parameters": {
    "path": "test.txt",
    "content": "Hello from test"
  }
}
```
"""
    tool_call = extract_json_tool_call(text)
    assert tool_call is not None
    assert tool_call["name"] == "write_file"
    assert tool_call["parameters"]["path"] == "test.txt"

def test_extract_json_tool_call_xml_tags():
    text = '<tool_call>{"name": "fetch", "arguments": {"url": "http://example.com"}}</tool_call>'
    tc = extract_json_tool_call(text)
    assert tc is not None
    assert tc["name"] == "fetch"
    assert tc["arguments"]["url"] == "http://example.com"

def test_extract_json_tool_call_raw_json():
    text = 'Result: {"name": "run_test", "input": {"suite": "all"}} is ready.'
    tc = extract_json_tool_call(text)
    assert tc is not None
    assert tc["name"] == "run_test"

def test_extract_json_tool_call_empty():
    assert extract_json_tool_call("") is None
    assert extract_json_tool_call("just plain text with no tool call") is None
    assert extract_json_tool_call("<tool_call>invalid json</tool_call>") is None

def test_openai_to_anthropic_response_text():
    openai_resp = {
        "id": "chatcmpl-12345",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Here is your response."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 8,
            "total_tokens": 23
        }
    }
    anthropic_resp = openai_to_anthropic_response(openai_resp, "claude-3-5-sonnet-20241022")
    assert anthropic_resp["type"] == "message"
    assert anthropic_resp["role"] == "assistant"
    assert anthropic_resp["stop_reason"] == "end_turn"
    assert len(anthropic_resp["content"]) == 1
    assert anthropic_resp["content"][0]["type"] == "text"
    assert anthropic_resp["content"][0]["text"] == "Here is your response."

def test_openai_to_anthropic_response_tool_call():
    openai_resp = {
        "id": "chatcmpl-tool",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Executing command",
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "ls -la"}'
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls"
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10}
    }
    anthropic_resp = openai_to_anthropic_response(openai_resp, "claude-3-5-sonnet-20241022")
    assert anthropic_resp["stop_reason"] == "tool_use"
    assert len(anthropic_resp["content"]) == 2
    assert anthropic_resp["content"][0]["type"] == "text"
    assert anthropic_resp["content"][1]["type"] == "tool_use"
    assert anthropic_resp["content"][1]["id"] == "call_abc"
    assert anthropic_resp["content"][1]["name"] == "bash"
    assert anthropic_resp["content"][1]["input"] == {"command": "ls -la"}

def test_openai_to_anthropic_response_max_tokens():
    openai_resp = {
        "id": "chatcmpl-max",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Truncated"},
                "finish_reason": "length"
            }
        ]
    }
    anthropic_resp = openai_to_anthropic_response(openai_resp, "claude-3-5-sonnet-20241022")
    assert anthropic_resp["stop_reason"] == "max_tokens"
