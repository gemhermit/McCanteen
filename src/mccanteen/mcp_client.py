"""麦当劳中国 MCP 客户端（Streamable HTTP / JSON-RPC 2.0）。

接入信息（来自官方文档 github.com/M-China/mcd-mcp-server）：
- 地址：https://mcp.mcd.cn
- 协议：Streamable HTTP，POST JSON-RPC 2.0
- 鉴权：Authorization: Bearer <MCP_TOKEN>
- 限流：600 次/分钟（超限返回 429）
- initialize 响应返回 Mcp-Session-Id，后续请求必须复用

仅使用 Python 标准库，零第三方依赖。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class MCPError(RuntimeError):
    """MCP 调用失败（网络 / 鉴权 / 协议错误）。"""


class McdonaldsMCP:
    def __init__(self, token: Optional[str] = None, url: Optional[str] = None, timeout: int = 30):
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        self.url = (url or os.environ.get("MCD_MCP_URL") or "https://mcp.mcd.cn").rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._rpc_id = 0

    # ---------- 协议层 ----------

    def _post(self, payload: Dict[str, Any], with_session: bool = True) -> Dict[str, Any]:
        if not self.token:
            raise MCPError("未配置 MCD_MCP_TOKEN（见 .env.example / mcp-config.example.json）")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }
        if with_session and self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                body = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200]
            raise MCPError(f"HTTP {e.code}: {detail}") from None
        except urllib.error.URLError as e:
            raise MCPError(f"网络错误: {e.reason}") from None
        return self._parse_body(body)

    @staticmethod
    def _parse_body(body: str) -> Dict[str, Any]:
        """响应可能是纯 JSON、SSE 帧（data: {...}）或空 body（通知类请求返回 204/空）。"""
        if not body.strip():
            return {}
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        return json.loads(body)

    def _rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._rpc_id += 1
        resp = self._post(
            {"jsonrpc": "2.0", "id": self._rpc_id, "method": method, "params": params or {}}
        )
        if "error" in resp:
            err = resp["error"]
            raise MCPError(f"RPC {method} 失败: {err.get('code')} {err.get('message')}")
        return resp.get("result", {})

    def initialize(self) -> Dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "mccanteen", "version": "0.1.0"},
            },
        )
        # initialized 通知（无 id，不期待响应）
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def tools_list(self) -> Dict[str, Any]:
        return self._rpc("tools/list")

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._rpc("tools/call", {"name": name, "arguments": arguments or {}})

    # ---------- 业务封装 ----------

    @staticmethod
    def text_of(result: Dict[str, Any]) -> str:
        """MCP tools/call 结果 → 纯文本（content 数组拼接）。"""
        parts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        return "\n".join(p for p in parts if p)

    def smoke_test(self) -> Dict[str, Any]:
        """连通性冒烟：initialize → now-time-info。"""
        init = self.initialize()
        now = self.call_tool("now-time-info")
        return {"initialize": init, "now_time": self.text_of(now)}
