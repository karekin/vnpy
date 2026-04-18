# TenX CopilotKit 迁移说明

## 概要

TenX Hunter 的 Copilot 已从“自定义聊天面板 + 手写 Next API route”迁移为：

- 前端：`CopilotKit` + `CopilotChat`
- Runtime：`@copilotkit/runtime` Next App Router endpoint
- 模型：MiniMax `MiniMax-M2.7`
- 协议：Anthropic 兼容接口

目标不是单纯把聊天框换皮，而是把 TenX 的工作台状态和业务动作接入到应用内 Copilot。

## 当前架构

### 前端挂载点

- Workspace 页面：
  - `frontend/src/app/(admin)/tenx-hunter/[market]/page.tsx`
- Research Card 页面：
  - `frontend/src/app/(admin)/tenx-hunter/[market]/research/[symbol]/page.tsx`
- Copilot 组件：
  - `frontend/src/components/tenx-hunter/TenxCopilotPanel.tsx`

### Runtime 入口

- `frontend/src/app/api/copilotkit/[[...route]]/route.ts`

使用 `copilotRuntimeNextJSAppRouterEndpoint(...)` 暴露 CopilotKit runtime，并通过 `AnthropicAdapter` 连接 MiniMax。

### 全局样式

- `frontend/src/app/layout.tsx`

这里引入了：

- `@copilotkit/react-ui/styles.css`

## 模型配置

当前优先读取以下环境变量：

- `MINIMAX_API_KEY`
- `MINIMAX_BASE_URL`
- `MINIMAX_MODEL`

默认值：

- `MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic`
- `MINIMAX_MODEL=MiniMax-M2.7`

本地开发依赖：

- `../.env.tushare.local`
- `frontend/.env.local`

## 已接入的 Copilot 状态

通过 `useCopilotReadable(...)` 暴露：

- 工作台摘要：
  - 市场
  - universe
  - 更新时间
  - freshness/source
- 候选池重点对象：
  - symbol
  - theme
  - stage
  - score
  - evidenceCount
  - nextEvent
- 主题列表：
  - name
  - heat
  - trend
  - driver
  - relatedSymbols
- 观察池摘要
- Research Card 单票上下文

这些状态不再通过手工拼接 prompt 字符串注入，而是通过 CopilotKit 的 readable state 提供给 runtime。

## 已接入的 Copilot 动作

通过 `useCopilotAction(...)` 注册：

- `openResearchCard`
- `addToWatchlist`
- `removeFromWatchlist`
- `createAlert`

动作底层仍复用 TenX 现有业务接口：

- `GET /api/v1/tenx-hunter/workspace`
- `GET /api/v1/tenx-hunter/research/{symbol}`
- `POST /api/v1/tenx-hunter/watchlist`
- `PATCH /api/v1/tenx-hunter/watchlist/{symbol}`
- `POST /api/v1/tenx-hunter/alerts`

## 与旧方案的区别

旧方案：

- `TenxCopilotPanel` 自己维护消息状态
- 自定义 `/api/tenx-hunter/copilot`
- AI Elements 只是低层消息/输入组件

新方案：

- `CopilotKit` 统一管理聊天状态
- `CopilotChat` 接管 UI
- `/api/copilotkit` 成为主入口
- `useCopilotReadable / useCopilotAction` 直接连接页面状态与动作

## 验证方式

### 前端

```bash
cd frontend
npx tsc --noEmit --incremental false
```

### 后端

```bash
python -m pytest tests/test_tenx_*.py tests/test_web_services_module.py -q
```

### 运行时探活

前端：

- `http://127.0.0.1:3002/tenx-hunter/cn`

后端：

- `http://127.0.0.1:8000/api/v1/tenx-hunter/workspace?market=CN`

## 后续建议

下一阶段建议继续完善：

- 给 `createAlert` / `removeFromWatchlist` 补充真正的 human-in-the-loop 确认流
- 给 Copilot 输出增加更多生成式 UI，而不是只显示纯文本和 action card
- 清理 TenX 中不再使用的旧 AI Elements 代码和旧 helper
