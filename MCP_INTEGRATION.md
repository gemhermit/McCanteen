# MCP_INTEGRATION.md

本文说明麦门食堂（McCanteen）实际使用的麦当劳 MCP Server、工具、调用流程与业务价值。

## 1. MCP Server

| 项 | 值 |
|---|---|
| 服务 | 麦当劳中国 MCP Server（官方） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP（POST JSON-RPC 2.0） |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>` |
| Token 申请 | https://open.mcd.cn/mcp （手机号登录 → 控制台 → 激活） |
| 限流 | 600 次/分钟，超限返回 429 |

客户端实现见 `src/mccanteen/mcp_client.py`（纯标准库，零依赖）：
`initialize`（复用 `Mcp-Session-Id`）→ `notifications/initialized` → `tools/list` / `tools/call`。

## 2. 使用的工具与用途

| 工具 | 用在哪 | 业务价值 |
|---|---|---|
| `now-time-info` | 时段判断（早/午/茶/晚/夜宵） | 「三点几啦饮茶先啦」的时机感 |
| `query-nearby-stores` | 附近门店 | 推荐必须可执行：就近能点到 |
| `query-meals` | 门店真实可售菜单 | 不推荐买不到的餐品 |
| `query-meal-detail` | 餐品组成与规格 | 解释「为什么是它」 |
| `calculate-price` | 候选方案真实计价 | **价格必须真实**：用券后价格由接口回填，不靠模型估算 |
| `query-my-coupons` / `query-store-coupons` | 用户券存量 | 券加权 + 沉默成本的数据底座 |
| `query-my-account` | 积分账户 | 积分也是另一种有保质期的钱 |
| `order-list` | 历史订单 | 反重复 + 麦门人生档案 |
| `campaign-calendar` | 活动日历 | 规划中：活动节奏建议 |
| `create-order` | 下单 | 规划中：**仅在用户明确确认后**调用 |

## 3. 调用流程

### 流程 A：今天吃什么（决断）

```
用户：「今天吃啥，预算 30，刚加完班」
 → now-time-info               → 时段 = 夜宵/晚餐
 → query-nearby-stores         → 就近门店
 → query-meals(门店)           → 时段可售菜单
 → query-my-coupons            → 券存量
 → 本地打分（decide.py）        → 3 个候选（券加权/反重复/处境匹配）
 → calculate-price(逐候选带券)  → 真实用券后价格
 → 输出结论 + 可选饭卡 PNG
```

### 流程 B：止损雷达

```
query-my-coupons + query-my-account
 → 按 24h / 48h / 7d 分桶
 → 沉默成本 = 48h 内过期券面值合计
 → 结论：「N 张券 48 小时内过期，面值 ¥X——正在蒸发的钱」
```

### 流程 C：麦门人生

```
order-list（近一年）
 → 统计：麦龄/单数/客单价/单品/时段画像
 → RPG 映射：等级（麦芽→麦门之主）/ 四属性 / 成就
 → 角色卡 PNG（1200×1600）
```

## 4. 关键契约与踩坑

详见 `references/mcp-contracts.md`，要点：

1. **initialize 必须复用 `Mcp-Session-Id`**，否则后续调用失败。
2. **响应可能是 SSE 帧**（`data: {...}`），客户端两种格式都解析。
3. **价格单位是分**：`calculate-price` 等字段以分计价，展示前统一经 `fen_to_yuan()` 换算——全项目唯一入口，杜绝「元/分」幻觉。
4. **部分接口可能返回 Markdown 文本**（其他参赛项目公开实测记录），live 解析需按真实返回校准。

## 5. 业务价值

| 能力 | 回答的问题 | 数据来源 |
|---|---|---|
| 决断引擎 | 「现在、这个预算、这个处境，点什么？」 | 菜单 + 券 + 时段 |
| 止损雷达 | 「我正在白扔多少钱？」 | 券存量 + 积分账户 |
| 麦门人生 | 「我这一年到底怎么吃的？」 | 历史订单 |

三条链路共用同一套 MCP 数据底座，分别对应**决策、止损、回顾**三个时间维度。

## 6. 实测状态（诚实声明）

| 项目 | 状态 |
|---|---|
| MCP 客户端协议实现（initialize/session/SSE 解析） | 已实现，**待真实 Token 实测** |
| fixtures 演示链路（全部引擎 + 卡片 + 101 项测试） | ✅ 已实测通过 |
| live 数据解析适配（coupons/orders 等字段映射） | ⚠️ 待实测校准（接口可能返回 Markdown） |
| `create-order` 下单闭环 | ⚠️ 规划中，未实测；上线前必须实现「明确确认才下单」 |

> 未配置 `MCD_MCP_TOKEN` 时，全部能力基于 `fixtures/` 演示数据运行，卡片与输出会明确标注「演示数据仅供参考」。
