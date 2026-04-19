# TenX Assistant Runtime 迁移说明

## 概要

TenX Hunter 的应用内助手已从 CopilotKit 迁移为：

- 前端聊天 UI：`assistant-ui`
- 消息与工具调用运行时：`Vercel AI SDK`
- 服务端流式路由：Next App Router `app/api/chat/route.ts`
- 模型接入：AI SDK Anthropic provider + MiniMax Anthropic 兼容接口

这次迁移刻意遵循“先稳定消息流，再逐步增强”的路线：

- 先做稳定的 chat streaming
- 保留工具调用能力
- 不先引入复杂的 agent-driven UI
- TenX 的业务动作继续复用现有 API，而不是把业务状态机塞进聊天框

## 2026-04-18 选型依据

本次重构对照了以下官方资料：

- `npx assistant-ui@latest create -t minimal`
- assistant-ui 官方文档里的 `useChatRuntime + AssistantChatTransport`
- AI SDK 官方文档里的 `streamText(...) + convertToModelMessages(...) + toUIMessageStreamResponse()`

校准时确认到的版本基线：

- `@assistant-ui/react@0.12.25`
- `@assistant-ui/react-ai-sdk@1.3.19`
- `@assistant-ui/react-markdown@0.12.9`
- `ai@6.0.168`
- `@ai-sdk/react@3.0.170`
- `@ai-sdk/anthropic@3.0.71`

## 当前架构

### 前端

- 页面入口：
  - `frontend/src/app/(admin)/tenx-hunter/[market]/page.tsx`
  - `frontend/src/app/(admin)/tenx-hunter/[market]/research/[symbol]/page.tsx`
- 助手面板：
  - `frontend/src/components/tenx-hunter/TenxCopilotPanel.tsx`
- 线程 UI：
  - `frontend/src/components/tenx-hunter/TenxAssistantThread.tsx`

### 服务端

- 聊天路由：
  - `frontend/src/app/api/chat/route.ts`
- DeerFlow 适配端点：
  - `vnpy/web/api/tenx_hunter.py`
  - `vnpy/web/services/deerflow_service.py`

其职责是：

- 接收 `assistant-ui` 经由 `AssistantChatTransport` 发来的 `messages/system/tools`
- 调用 AI SDK 的 `streamText(...)`
- 用 `frontendTools(tools)` 桥接前端工具
- 返回 `toUIMessageStreamResponse()`

### 模型配置

继续沿用现有 MiniMax Anthropic 兼容配置：

- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`

默认值：

- `MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1`
- `MINIMAX_MODEL=MiniMax-M2.7`

## 当前实现策略

### 上下文注入

不再使用 CopilotKit 的 `useCopilotReadable(...)`。

当前改为在前端通过 `useAssistantInstructions(...)` 注入：

- 当前市场
- 当前 workspace 摘要
- 候选池前几名
- 主题摘要
- 观察池摘要
- 当前 research card 摘要

这样做的原因是：

- 路径更简单
- 更接近 AI SDK / assistant-ui 的稳定基线
- 先保证消息流和工具调用可靠

### 工具调用

不再使用 CopilotKit 的 `useCopilotAction(...)`。

当前改为 assistant-ui 的 `Tools()` API 注册前端工具：

- `openResearchCard`
- `addToWatchlist`
- `removeFromWatchlist`
- `createAlert`

这些工具仍然复用 TenX 现有业务接口：

- `POST /api/v1/tenx-hunter/watchlist`
- `POST /api/v1/tenx-hunter/alerts`

其中：

- `openResearchCard` 在前端执行，并保留“等待当前响应结束后再跳页”的行为
- 观察池和提醒操作仍在浏览器侧触发，然后 `router.refresh()`
- `removeFromWatchlist` 现在带有真实浏览器确认步骤，不再只依赖提示词约束

### 会话持久化

当前已补上页面级本地持久化：

- 每个 TenX 页面按 `market + pathname` 生成独立 localStorage key
- 助手响应完成后会把整段消息历史写回本地
- 页面刷新后会自动恢复最近一段会话
- 点击“新对话”会清空当前页面对应的本地会话缓存

## 与旧方案的核心差别

旧方案：

- CopilotKit 自带聊天 runtime 与 UI
- `useCopilotReadable / useCopilotAction`
- `/api/copilotkit`
- 一大段 CopilotKit 专属样式与 message-id normalization 逻辑

新方案：

- assistant-ui 只负责 UI 与线程状态
- AI SDK 只负责消息流、模型调用和工具协议
- `/api/chat` 作为统一流式入口
- 工具通过 `Tools()` API 明确注册
- TenX 业务 API 继续独立存在，不被聊天 runtime 绑死

## 为什么这条路线更稳

- UI、runtime、业务动作三层解耦更清楚
- 前端统一走 AI SDK 消息流，不再依赖 CopilotKit 的特殊 runtime 行为
- 业务动作依然是现有 TenX API，方便继续审计和权限控制
- 后续如果要接 DeerFlow / LangGraph，可以把它们放在 `/api/chat` 后面，而不是重写前端

## DeerFlow 实验接入

当前已经补上一条实验性 DeerFlow 接入链路：

- 当 `TENX_DEERFLOW_ENABLED=true` 时，`frontend/src/app/api/chat/route.ts` 会优先请求 Python 侧的 `/api/v1/tenx-hunter/deerflow/chat`
- Python 侧通过 `vnpy.web.services.deerflow_service.DeerFlowService` 直接调用 DeerFlow Gateway 的 `/api/threads` 与 `/api/threads/{thread_id}/runs/wait`
- 如果 DeerFlow 未安装、未启用或调用失败，前端 `/api/chat` 会自动回退到现有的 AI SDK + MiniMax 直连模式

当前已经进一步升级为原生 DeerFlow 流式/历史接入：

- `frontend/src/app/api/chat/route.ts` 优先请求 Python 侧 `/api/v1/tenx-hunter/deerflow/stream`
- Python 侧流式代理 DeerFlow Gateway 的 `/api/threads/{thread_id}/runs/stream`
- 前端会把 DeerFlow 的 `messages / updates / values` SSE 事件桥接成 AI SDK UI stream
- 页面初始化时会优先读取 `/api/v1/tenx-hunter/deerflow/state` 恢复 DeerFlow 线程消息
- 后端也暴露了 `/api/v1/tenx-hunter/deerflow/history` 供后续做更完整的 checkpoint 历史浏览

当前相关环境变量：

- `TENX_DEERFLOW_ENABLED=true|false`
- `TENX_DEERFLOW_API_URL=http://127.0.0.1:8002`
- `TENX_DEERFLOW_URL=http://127.0.0.1:2026`

注意：

- 这是一版“低风险尝试接入”，目标是先把 DeerFlow 放进 `/api/chat` 后面，而不是一次性重写前端协议
- 当前已经接上 DeerFlow Gateway 的原生 stream/state/history，但 UI 仍是现有 assistant-ui 线程壳
- 现在可以看到 DeerFlow 的中间状态芯片、推理流和线程恢复
- 如果后续要做更完整的技能面板、artifact 面板、checkpoint 浏览器和多线程列表，还需要继续扩展前端呈现层

## 验证方式

```bash
cd frontend
npm run typecheck
npm test -- --runInBand src/components/__tests__/TenxCopilotPanel.test.tsx
npm run build
```

## 后续建议

下一阶段再补：

- thread list / 多会话切换
- 更细的工具权限与确认流
- DeerFlow / 自研 agent 接入 `/api/chat`
- 更丰富的 tool result card，而不是只显示基础状态卡
