# CB Quant 近一周回测测试与断点调试文档

## 目标

验证 CB Quant 回测任务创建区域新增的 `近1周（1w）` 窗口在前后端都可用，并可基于最近一周的历史快照完成回测、结果查看和问题定位。

## 变更范围

- 后端：`WindowName` 新增 `1w`
- 后端：历史切片逻辑支持最近 7 天窗口
- 后端：窗口显示文案支持 `近1周`
- 前端：回测任务创建区域新增 `近1周` 勾选项

## 测试前置条件

1. 本地已有最近一周的可转债历史快照数据。
2. 能正常启动后端服务和前端页面。
3. 至少存在一个可用于回测的候选组合或策略模板。
4. 建议将测试日期固定在最近一周内存在交易日的数据区间，避免因为周末造成“窗口有值但无交易日”误判。

## 建议测试数据范围

- 优先使用“最近 7 个自然日内的全部交易日”
- 如果你要手工指定日期，建议直接用：
  - `end_date`: 当前最新快照日
  - `start_date`: `end_date - 7天`

## 功能测试用例

### 用例 1：前端窗口选择

步骤：

1. 打开回测评估页面。
2. 定位“回测任务创建”区域。
3. 查看窗口复选框。

预期：

- 能看到 `全周期`、`近3年`、`近1年`、`近1周`
- `近1周` 可单独勾选
- 取消其他窗口后，仍可仅保留 `近1周`

### 用例 2：创建近一周回测任务

步骤：

1. 选择一个有效模板。
2. 窗口仅勾选 `近1周`。
3. 设置 `TopN策略`、`当前市场TopN` 等必填项。
4. 点击创建/开始回测。

预期：

- 请求体中的 `windows` 为 `["1w"]`
- 后端成功创建任务
- 任务列表/作业列表中窗口显示为 `近1周`

### 用例 3：近一周回测结果有效

步骤：

1. 等待任务完成。
2. 打开任务详情或分析页。
3. 检查净值曲线、轮动记录和指标区。

预期：

- 曲线点数量只覆盖最近一周内的交易日
- 轮动记录日期只落在最近一周窗口内
- 指标能正常返回，不出现空窗口报错

### 用例 4：与手工日期范围交叉验证

步骤：

1. 先用窗口 `近1周` 跑一次。
2. 再用手工 `start_date = end_date - 7天`、`end_date = 最新交易日` 跑一次。
3. 比较两次结果。

预期：

- 两次使用的数据区间一致或高度一致
- 总收益、回撤、调仓次数基本一致

## 断点调试步骤

## 后端断点

### 断点 1：任务创建入口

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py`

位置：

- `create_jobs(...)`

观察点：

- `request.windows`
- `windows`
- `window_text`

预期：

- 传入 `["1w"]`
- 归一化后仍为 `["1w"]`
- 返回提示文案包含 `近1周`

### 断点 2：窗口文案映射

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py`

位置：

- `_window_label(...)`

观察点：

- `window_name`
- 返回值

预期：

- 输入 `1w`
- 返回 `近1周`

### 断点 3：历史区间切片

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/adapters/crawler_phase_a_adapter.py`

位置：

- `_slice_dataset(...)`

观察点：

- `window_name`
- `normalized[-1][0]`
- `begin`
- `return` 结果的首尾日期

预期：

- `window_name == "1w"`
- `begin = end - 7天`
- 返回的数据只包含最近一周窗口内的交易日

### 断点 4：作业执行入口

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py`

位置：

- `_run_job(...)`

观察点：

- `context["window_name"]`
- `stats["used_range_start"]`
- `stats["used_range_end"]`

预期：

- `window_name == "1w"`
- 实际使用的数据区间是最近一周

### 断点 5：详细分析页回放

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/vnpy/web/services/cb_quant_service.py`

位置：

- `_simulate_detailed_strategy(...)`

观察点：

- `trade_date`
- `candidate`
- `holdings`
- `daily_returns`
- `nav_series`

预期：

- 只遍历最近一周内的交易日
- 候选池、持仓、净值变化符合该窗口的数据

## 前端断点

### 断点 1：页面窗口状态

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/frontend/src/app/(admin)/cb-quant/backtest-evaluation/page.tsx`

位置：

- `windows` state
- `activeWindows`

观察点：

- 勾选 `近1周` 后 `windows["1w"]`
- `activeWindows`

预期：

- `windows["1w"] === true`
- `activeWindows` 包含 `"1w"`

### 断点 2：发起请求前

文件：

- `/Users/karekin/Downloads/coding/project/vnpy/frontend/src/app/(admin)/cb-quant/backtest-evaluation/page.tsx`

位置：

- 创建回测任务的提交函数

观察点：

- 提交 payload 中的 `windows`

预期：

- 请求发出前 `windows: ["1w"]`

## 联调建议

1. 先只勾选 `近1周`，减少变量数量。
2. 首次验证时，手工指定 `start_date/end_date`，便于和窗口切片结果对照。
3. 若结果为空，先检查最近一周是否真的有快照数据。
4. 若任务创建成功但结果异常，优先看 `_slice_dataset(...)` 是否切到了错误日期范围。
5. 若前端勾选后无效，优先看浏览器 Network 请求体里的 `windows` 是否包含 `1w`。

## 常见故障排查

### 现象：前端勾选了近1周，但后端报参数非法

原因：

- 后端 `WindowName` 未支持 `1w`

排查：

- 看 schema 是否已包含 `1w`

### 现象：任务创建成功，但跑出来仍像全年数据

原因：

- 后端切片逻辑未处理 `1w`

排查：

- 断在 `_slice_dataset(...)`，确认 `window_name == "1w"` 分支是否命中

### 现象：近1周任务为空

原因：

- 最近一周无快照
- 最近一周虽有快照，但无交易日数据

排查：

- 检查历史快照表或本地快照文件日期

## 回归测试建议

除 `1w` 外，至少补测以下窗口一次：

- `full`
- `3y`
- `1y`

预期：

- 原有窗口行为不变
- 排行、任务创建、分析页展示不因 `1w` 引入回归问题
