import numpy as np
import polars as pl
from sklearn.linear_model import Lasso      # type: ignore

from vnpy.alpha import (
    AlphaDataset,
    AlphaModel,
    Segment,
    logger
)


class LassoModel(AlphaModel):
    """
    基于 L1 正则的线性因子模型。

    适用场景：
    1. 因子数量较多、需要自动压缩无效因子的横截面建模。
    2. 需要较强可解释性（系数可直接对应因子方向与强弱）。
    """

    def __init__(
        self,
        alpha: float = 0.0005,
        max_iter: int = 1000,
        random_state: int | None = None,
    ) -> None:
        """
        初始化 Lasso 超参数与模型状态。

        `alpha` 控制稀疏强度；值越大，非零因子越少。
        """
        self.alpha: float = alpha
        self.max_iter: int = max_iter
        self.random_state: int | None = random_state

        self.model: Lasso = None

        self.feature_names: list[str] = []

    def fit(self, dataset: AlphaDataset) -> None:
        """
        训练模型参数。

        训练口径：
        1. 使用 `TRAIN + VALID` 合并样本训练，扩大样本量。
        2. 以 `(datetime, vt_symbol)` 去重并排序，保证样本顺序稳定。
        3. 默认 `fit_intercept=False`，假设特征已在数据处理阶段完成标准化/中心化。
        """
        # 读取训练集与验证集样本。
        df_train: pl.DataFrame = dataset.fetch_learn(Segment.TRAIN)
        df_valid: pl.DataFrame = dataset.fetch_learn(Segment.VALID)

        # 合并样本并去重，避免同一时间同一标的重复训练。
        df_train = pl.concat([df_train, df_valid])
        df_train = df_train.unique(subset=["datetime", "vt_symbol"])
        df_train = df_train.sort(["datetime", "vt_symbol"])

        # 提取因子列名（跳过 datetime/vt_symbol，最后一列为 label）。
        self.feature_names = df_train.columns[2:-1]

        # 转换为 sklearn 所需的 numpy 输入。
        X: np.ndarray = df_train.select(self.feature_names).to_numpy()
        y: np.ndarray = np.array(df_train["label"])

        # 构建并拟合 Lasso。
        self.model = Lasso(
            alpha=self.alpha,
            max_iter=self.max_iter,
            random_state=self.random_state,
            fit_intercept=False,
            copy_X=False
        )
        self.model.fit(X, y)

    def predict(self, dataset: AlphaDataset, segment: Segment) -> np.ndarray:
        """
        对指定数据分段输出预测值。

        返回数组顺序与 `fetch_infer(segment)` 按时间、标的排序后的样本顺序一致，
        可直接拼回信号表做截面选股或回测。
        """
        # 未训练模型时禁止预测。
        if self.model is None:
            raise ValueError("model is not fitted yet!")

        # 读取推理样本并排序，确保输出可对齐。
        df: pl.DataFrame = dataset.fetch_infer(segment)
        df = df.sort(["datetime", "vt_symbol"])

        # 转换为模型输入矩阵。
        data: np.ndarray = df.select(df.columns[2: -1]).to_numpy()

        # 输出连续预测值。
        result: np.ndarray = self.model.predict(data)

        return result

    def detail(self) -> None:
        """
        输出模型可解释信息（非零因子系数）。

        仅打印有效系数并按绝对值降序，便于快速识别当前主导因子。
        """
        # 读取模型系数。
        coef: np.ndarray = self.model.coef_

        # 绑定“因子名 -> 系数”。
        data: list[tuple[str, float]] = list(zip(self.feature_names, coef, strict=False))

        # 过滤零系数因子（被 L1 压缩掉）。
        data = [x for x in data if x[1]]

        # 按绝对值排序，突出影响最大的因子。
        data.sort(key=lambda x: abs(x[1]), reverse=True)

        # 进一步去掉数值极小的噪声系数。
        data = [x for x in data if round(x[1], 6) != 0]

        # 打印因子重要性摘要。
        logger.info(f"LASSO模型特征总数量: {len(data)}")

        for name, importance in data:
            logger.info(f"{name}: {importance:.6f}")
