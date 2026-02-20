# VeighNa Web Frontend (Next.js)

这是为 `vnpy` 项目补充的 Web 终端前端，风格参考 VeighNa Trader 桌面版界面（深色、多面板、交易工作台布局）。

## 功能模块（前端原型）

- 交易终端：委托面板、行情、委托、成交、资金、持仓、日志
- 合约查询：搜索栏 + 大表格查询区
- CTA回测：参数配置、指标面板、曲线/柱状图区域
- CTA策略：策略卡片、停止委托、日志区
- 数据管理：目录树、导入参数、K线数据表
- 算法交易：算法配置、任务列表、配置区
- 风控：风控参数与监控列表
- 报价墙：卡片式行情跟踪
- Station：网关/应用模块启动视图

## 启动

```bash
cd frontend
npm install
npm run dev
```

打开: [http://localhost:3000](http://localhost:3000)

## 对接 vnpy WebTrader API

项目里已预留接口封装：

- `src/lib/vnpy-api.ts`
- `src/hooks/use-vnpy-feed.ts`

默认读取：

```bash
NEXT_PUBLIC_VNPY_BASE_URL=http://127.0.0.1:8000
```

可在 `frontend/.env.local` 中覆盖。

