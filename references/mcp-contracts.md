# MCP 调用契约（mcp-contracts）

接入麦当劳中国 MCP 的**实测**结论（2026-10-15，mcd-mcp v1.0.0，真实 Token 跑通）。
凡未实测的条目不声明为已验证。

## 接入（官方文档 + 实测确认）

| 项 | 值 |
|---|---|
| 地址 | `https://mcp.mcd.cn` |
| 协议 | Streamable HTTP，POST JSON-RPC 2.0 |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 600 次/分钟，超限 429 |
| Token 申请 | https://open.mcd.cn/mcp 控制台 |

## 实测确认的协议行为（踩过的坑）

1. **服务器不返回 `Mcp-Session-Id`**（无会话机制）。initialize 之后直接调用 `tools/call` 即可，不要等 session 头。
2. **通知类请求返回空 body**（`notifications/initialized` 返回 200/空）。解析器必须容忍空响应，否则 JSON 解析直接崩——本项目第一版就死在这。
3. **响应有两种包装**：
   - ①「API Response Information」Markdown 描述 + `## Original Response` 后内嵌 JSON（now-time-info / account / stores / store-coupons / order-list / meals / calculate-price）；
   - ② 纯 Markdown（`query-my-coupons` 的券列表，`## 标题` + `- **字段**: 值` 结构）。
   解析器见 `src/mccanteen/live.py`，均有离线测试覆盖。
4. **金额单位是分**：`calculate-price` 的 `subtotal` / `originalSubtotal`。展示前统一经 `models.fen_to_yuan()` 换算。
5. **`calculate-price` 的 items 字段名是 `productCode`**（不是 `code`），且 `quantity` 必填 ≥1；用错字段名不报错，**静默返回全 0**——非常危险的坑。
6. **`calculate-price` 单次调用可传多个商品**，一次拿回全部名称与价格（`productList[]`）。这是 live 菜单的最高效路径。
7. **单次调用商品数过多会被服务器断连**（实测 60 个报 WinError 10054）。本项目按 20 个/块分块，失败自动拆成 8 个/小块重试。
8. **`query-meals` 只返回 code + tags**（128 个 code、15 个分类），**没有名称和价格**；名称与价格来自 `calculate-price` 批量计价。
9. **`list-nutrition-foods` 的 data 是字符串**，自定义格式：`名称,null,能量kJ,能量kcal,蛋白质,脂肪,碳水,钠,钙`。
10. **`query-my-coupons`（Markdown）与 `query-store-coupons`（JSON）会返回同一张券**，需按标题去重合并；门店券带 `products[].productCode` 可精确关联菜单，账户券带有效期星期/时段窗。
11. **券的「用券价格」不是面值**。买一送一的面值只能近似（≈ 用券价格）；套餐券的面值需要菜单原价对照，而**早餐券在午/晚餐时段查不到对应菜单商品**（菜单随时段变化）——此时必须标记「面值待核实」，不能按 0 计入沉默成本。
12. **`order-list` 的 `realTotalAmount` 是元为单位的字符串**（如 "20.5"）。

## 本项目调用的工具

| 工具 | 用途 | 状态 |
|---|---|---|
| `now-time-info` | 服务端时间 → 时段判断 | ✅ 已实测 |
| `query-nearby-stores` | 附近门店（`searchType=1`） | ✅ 已实测 |
| `query-meals` | 门店可售菜单（code + 分类） | ✅ 已实测 |
| `calculate-price` | 批量计价（名称 + 价格，单位分） | ✅ 已实测 |
| `list-nutrition-foods` | 营养库（kcal / 蛋白质） | ✅ 已实测 |
| `query-my-coupons` | 账户券（Markdown） | ✅ 已实测 |
| `query-store-coupons` | 门店券（JSON，带商品关联） | ✅ 已实测 |
| `query-my-account` | 积分账户 | ✅ 已实测 |
| `order-list` | 历史订单 | ✅ 已实测 |
| `campaign-calendar` | 活动日历 | 规划中 |
| `create-order` | 下单（**仅在用户明确确认后**） | 规划中，需人工确认流程 |

## live 数据集：8 类调用拿全

`LiveData.fetch` 的调用序列（实测 15 次 = 8 类 + 7 个计价分块）：

```
now-time-info → query-nearby-stores → query-meals
→ calculate-price × N 块（20 个/块）→ list-nutrition-foods
→ query-my-coupons → query-store-coupons → query-my-account → order-list
```

## 已知限制

- 菜单随时段变化：早餐商品只在早餐档出现在 `query-meals` 结果里，早餐券因此常常无法对照原价（面值待核实）；
- live 餐品无法从菜单接口判断时段可得性（`query-meal-detail` 无时段字段），故 live 候选默认全时段，仅早餐券的时段窗可用于反向约束；
- 低于 ¥5 的计价结果视为加购/配料项（酱料、特调件），不进候选池；
- 演示模式（fixtures）与 live 模式差异仅在数据来源，引擎与卡片层完全一致。
