# MCP 调用契约（mcp-contracts）

接入麦当劳中国 MCP 的实测/文档结论。**凡未实测的条目不声明为已验证。**

## 接入（来自官方文档）

| 项 | 值 |
|---|---|
| 地址 | `https://mcp.mcd.cn` |
| 协议 | Streamable HTTP，POST JSON-RPC 2.0 |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 600 次/分钟，超限 429 |
| Token 申请 | https://open.mcd.cn/mcp 控制台 |

## 已确认的协议行为（客户端实现依赖）

1. `initialize` 响应头返回 `Mcp-Session-Id`，后续请求必须复用（`src/mccanteen/mcp_client.py` 已处理）。
2. 初始化后需发送 `notifications/initialized` 通知。
3. 响应体可能是纯 JSON 或 SSE 帧（`data: {...}`），客户端两种情况都解析。
4. `tools/call` 返回 `content` 数组，文本在 `content[].text`。
5. 错误以 JSON-RPC `error` 对象返回；HTTP 401 = Token 无效，429 = 触发限流。

## 价格单位（重要）

- MCP 计价相关字段单位为**分**（`calculate-price` 等）。展示层一律经 `models.fen_to_yuan()` 换算——全项目唯一入口。
- 官方文档未逐一标注字段单位，此结论来自其他参赛项目公开实测记录与官方示例的交叉验证；本项目接入后将以真实返回复核，复核结果将更新到 MCP_INTEGRATION.md 的实测表。

## 本项目调用的工具

| 工具 | 用途 | 状态 |
|---|---|---|
| `now-time-info` | 服务端时间 → 时段判断 | 已接入，待实测 |
| `query-nearby-stores` | 附近门店 | 已接入，待实测 |
| `query-meals` | 门店可售菜单 | 已接入，待实测 |
| `query-meal-detail` | 餐品组成与规格 | 已接入，待实测 |
| `calculate-price` | 真实计价（分） | 已接入，待实测 |
| `query-my-coupons` / `query-store-coupons` | 券存量 | 已接入，待实测 |
| `query-my-account` | 积分账户 | 已接入，待实测 |
| `order-list` | 历史订单 → 麦门人生 | 已接入，待实测 |
| `campaign-calendar` | 活动日历 | 规划中 |
| `create-order` | 下单（**仅在用户明确确认后**） | 规划中，需人工确认流程 |

## 已知限制

- 部分接口（如 `query-my-coupons`）可能返回 Markdown 文本而非结构化 JSON，live 解析适配器需按真实返回校准——这是 fixtures 结构与 live 结构的最大差异点。
- 演示模式（fixtures）与 live 模式的差异仅在数据来源，引擎与卡片层完全一致。
