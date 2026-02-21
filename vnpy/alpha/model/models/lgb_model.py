from typing import cast

import numpy as np
import polars as pl
import lightgbm as lgb
import matplotlib.pyplot as plt

from vnpy.alpha.dataset import AlphaDataset, Segment
from vnpy.alpha.model import AlphaModel


class LgbModel(AlphaModel):
    """
    `LgbModel` 是基于 LightGBM 的梯度提升树模型实现，适合非线性因子关系建模。
    
    职责：
    1. 完成 LightGBM 训练、预测与特征重要性输出。
    2. 支持高效率大样本训练。
    3. 用于挖掘因子与收益之间的非线性关系。
    
    协作：
    1. 继承 `AlphaModel`。
    2. 与 `AlphaDataset` 联动执行训练和回测评价。
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        num_leaves: int = 31,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
        log_evaluation_period: int = 1,
        seed: int | None = None
    ):
        """
        初始化实例，完成依赖绑定与基础状态准备。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `learning_rate` (`float`)，默认值 `0.1`：输入参数，用于控制该方法的处理行为。
        2. `num_leaves` (`int`)，默认值 `31`：输入参数，用于控制该方法的处理行为。
        3. `num_boost_round` (`int`)，默认值 `1000`：输入参数，用于控制该方法的处理行为。
        4. `early_stopping_rounds` (`int`)，默认值 `50`：输入参数，用于控制该方法的处理行为。
        5. `log_evaluation_period` (`int`)，默认值 `1`：输入参数，用于控制该方法的处理行为。
        6. `seed` (`int | None`)，默认值 `None`：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        self.params: dict = {
            "objective": "mse",
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "seed": seed
        }

        self.num_boost_round: int = num_boost_round
        self.early_stopping_rounds: int = early_stopping_rounds
        self.log_evaluation_period: int = log_evaluation_period

        self.model: lgb.Booster | None = None

    def _prepare_data(self, dataset: AlphaDataset) -> list[lgb.Dataset]:
        """
        执行 `_prepare_data` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `dataset` (`AlphaDataset`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `list[lgb.Dataset]`：返回按约定组织的数据列表。
        """
        ds: list[lgb.Dataset] = []

        # Process training and validation separately
        for segment in [Segment.TRAIN, Segment.VALID]:
            # Get data for learning
            df: pl.DataFrame = dataset.fetch_learn(segment)
            df = df.sort(["datetime", "vt_symbol"])

            # Convert to numpy arrays
            data = df.select(df.columns[2: -1]).to_pandas()
            label = np.array(df["label"])

            # Add training data
            ds.append(lgb.Dataset(data, label=label))

        return ds

    def fit(self, dataset: AlphaDataset) -> None:
        """
        执行 `fit` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `dataset` (`AlphaDataset`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        # Prepare task data
        ds: list[lgb.Dataset] = self._prepare_data(dataset)

        # Execute model training
        self.model = lgb.train(
            self.params,
            ds[0],
            num_boost_round=self.num_boost_round,
            valid_sets=ds,
            valid_names=["train", "valid"],
            callbacks=[
                lgb.early_stopping(self.early_stopping_rounds),      # Early stopping callback
                lgb.log_evaluation(self.log_evaluation_period)       # Logging callback
            ]
        )

    def predict(self, dataset: AlphaDataset, segment: Segment) -> np.ndarray:
        """
        执行 `predict` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. `dataset` (`AlphaDataset`)：输入参数，用于控制该方法的处理行为。
        2. `segment` (`Segment`)：输入参数，用于控制该方法的处理行为。
        
        返回：
        1. `np.ndarray`：返回该方法计算或查询得到的结果。
        """
        # Check if model exists
        if self.model is None:
            raise ValueError("model is not fitted yet!")

        # Get data for inference
        df: pl.DataFrame = dataset.fetch_infer(segment)
        df = df.sort(["datetime", "vt_symbol"])

        # Convert to numpy array
        data: np.ndarray = df.select(df.columns[2: -1]).to_numpy()

        # Return prediction results
        result: np.ndarray = cast(np.ndarray, self.model.predict(data))
        return result

    def detail(self) -> None:
        """
        执行 `detail` 相关业务逻辑。
        
        用途说明：
        1. 封装当前方法对应的单一职责逻辑。
        2. 对外提供稳定接口，供上层流程组合调用。
        
        参数：
        1. 无显式业务参数。
        
        返回：
        1. `None`：无返回值，结果通过内部状态或副作用体现。
        """
        if not self.model:
            return

        for importance_type in ["split", "gain"]:
            ax: plt.Axes = lgb.plot_importance(
                self.model,
                max_num_features=50,
                importance_type=importance_type,
                figsize=(10, 20)
            )
            ax.set_title(f"Feature Importance ({importance_type})")
