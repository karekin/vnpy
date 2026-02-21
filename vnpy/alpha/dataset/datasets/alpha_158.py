import polars as pl

from vnpy.alpha import AlphaDataset


class Alpha158(AlphaDataset):
    """
    `Alpha158` 是 Alpha158 因子数据集实现，提供扩展因子维度的研究输入。
    
    职责：
    1. 组织 Alpha158 因子特征与标签。
    2. 统一时间对齐与样本过滤逻辑。
    3. 为模型横向比较提供一致数据接口。
    
    协作：
    1. 继承 `AlphaDataset`。
    2. 与 `AlphaModel` 训练/验证流程联动。
    """

    def __init__(
        self,
        df: pl.DataFrame,
        train_period: tuple[str, str],
        valid_period: tuple[str, str],
        test_period: tuple[str, str]
    ) -> None:
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `df` (`pl.DataFrame`)：输入参数，用于控制该方法的处理行为。
        2. `train_period` (`tuple[str, str]`)：输入参数，用于控制该方法的处理行为。
        3. `valid_period` (`tuple[str, str]`)：输入参数，用于控制该方法的处理行为。
        4. `test_period` (`tuple[str, str]`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        super().__init__(
            df=df,
            train_period=train_period,
            valid_period=valid_period,
            test_period=test_period,
        )

        # Candlestick pattern features
        self.add_feature("kmid", "(close - open) / open")
        self.add_feature("klen", "(high - low) / open")
        self.add_feature("kmid_2", "(close - open) / (high - low + 1e-12)")
        self.add_feature("kup", "(high - ts_greater(open, close)) / open")
        self.add_feature("kup_2", "(high - ts_greater(open, close)) / (high - low + 1e-12)")
        self.add_feature("klow", "(ts_less(open, close) - low) / open")
        self.add_feature("klow_2", "((ts_less(open, close) - low) / (high - low + 1e-12))")
        self.add_feature("ksft", "(close * 2 - high - low) / open")
        self.add_feature("ksft_2", "(close * 2 - high - low) / (high - low + 1e-12)")

        # Price change features
        for field in ["open", "high", "low", "vwap"]:
            self.add_feature(f"{field}_0", f"{field} / close")

        # Time series features
        windows: list[int] = [5, 10, 20, 30, 60]

        for w in windows:
            self.add_feature(f"roc_{w}", f"ts_delay(close, {w}) / close")

        for w in windows:
            self.add_feature(f"ma_{w}", f"ts_mean(close, {w}) / close")

        for w in windows:
            self.add_feature(f"std_{w}", f"ts_std(close, {w}) / close")

        for w in windows:
            self.add_feature(f"beta_{w}", f"ts_slope(close, {w}) / close")

        for w in windows:
            self.add_feature(f"rsqr_{w}", f"ts_rsquare(close, {w})")

        for w in windows:
            self.add_feature(f"resi_{w}", f"ts_resi(close, {w}) / close")

        for w in windows:
            self.add_feature(f"max_{w}", f"ts_max(high, {w}) / close")

        for w in windows:
            self.add_feature(f"min_{w}", f"ts_min(low, {w}) / close")

        for w in windows:
            self.add_feature(f"qtlu_{w}", f"ts_quantile(close, {w}, 0.8) / close")

        for w in windows:
            self.add_feature(f"qtld_{w}", f"ts_quantile(close, {w}, 0.2) / close")

        for w in windows:
            self.add_feature(f"rank_{w}", f"ts_rank(close, {w})")

        for w in windows:
            self.add_feature(f"rsv_{w}", f"(close - ts_min(low, {w})) / (ts_max(high, {w}) - ts_min(low, {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"imax_{w}", f"ts_argmax(high, {w}) / {w}")

        for w in windows:
            self.add_feature(f"imin_{w}", f"ts_argmin(low, {w}) / {w}")

        for w in windows:
            self.add_feature(f"imxd_{w}", f"(ts_argmax(high, {w}) - ts_argmin(low, {w})) / {w}")

        for w in windows:
            self.add_feature(f"corr_{w}", f"ts_corr(close, ts_log(volume + 1), {w})")

        for w in windows:
            self.add_feature(f"cord_{w}", f"ts_corr(close / ts_delay(close, 1), ts_log(volume / ts_delay(volume, 1) + 1), {w})")

        for w in windows:
            self.add_feature(f"cntp_{w}", f"ts_mean(close > ts_delay(close, 1), {w})")

        for w in windows:
            self.add_feature(f"cntn_{w}", f"ts_mean(close < ts_delay(close, 1), {w})")

        for w in windows:
            self.add_feature(f"cntd_{w}", f"ts_mean(close > ts_delay(close, 1), {w}) - ts_mean(close < ts_delay(close, 1), {w})")

        for w in windows:
            self.add_feature(f"sump_{w}", f"ts_sum(ts_greater(close - ts_delay(close, 1), 0), {w}) / (ts_sum(ts_abs(close - ts_delay(close, 1)), {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"sumn_{w}", f"ts_sum(ts_greater(ts_delay(close, 1) - close, 0), {w}) / (ts_sum(ts_abs(close - ts_delay(close, 1)), {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"sumd_{w}", f"(ts_sum(ts_greater(close - ts_delay(close, 1), 0), {w}) - ts_sum(ts_greater(ts_delay(close, 1) - close, 0), {w})) / (ts_sum(ts_abs(close - ts_delay(close, 1)), {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"vma_{w}", f"ts_mean(volume, {w}) / (volume + 1e-12)")

        for w in windows:
            self.add_feature(f"vstd_{w}", f"ts_std(volume, {w}) / (volume + 1e-12)")

        for w in windows:
            self.add_feature(f"wvma_{w}", f"ts_std(ts_abs(close / ts_delay(close, 1) - 1) * volume, {w}) / (ts_mean(ts_abs(close / ts_delay(close, 1) - 1) * volume, {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"vsump_{w}", f"ts_sum(ts_greater(volume - ts_delay(volume, 1), 0), {w}) / (ts_sum(ts_abs(volume - ts_delay(volume, 1)), {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"vsumn_{w}", f"ts_sum(ts_greater(ts_delay(volume, 1) - volume, 0), {w}) / (ts_sum(ts_abs(volume - ts_delay(volume, 1)), {w}) + 1e-12)")

        for w in windows:
            self.add_feature(f"vsumd_{w}", f"(ts_sum(ts_greater(volume - ts_delay(volume, 1), 0), {w}) - ts_sum(ts_greater(ts_delay(volume, 1) - volume, 0), {w})) / (ts_sum(ts_abs(volume - ts_delay(volume, 1)), {w}) + 1e-12)")

        # Set label
        self.set_label("ts_delay(close, -3) / ts_delay(close, -1) - 1")
