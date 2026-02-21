from abc import ABCMeta, abstractmethod
from typing import Any

import numpy as np

from vnpy.alpha.dataset import AlphaDataset, Segment


class AlphaModel(metaclass=ABCMeta):
    """
    Alpha 因子模型抽象基类。

    统一约定“如何训练”和“如何在指定数据分段上预测”，
    让不同算法模型可以被同一套研究与回测流程调用。
    """

    @abstractmethod
    def fit(self, dataset: AlphaDataset) -> None:
        """
        在给定数据集上完成模型训练。

        子类应从 `dataset` 中读取训练特征与标签，
        并把训练后的参数保存在模型实例中，供后续 `predict` 使用。
        """
        pass

    @abstractmethod
    def predict(self, dataset: AlphaDataset, segment: Segment) -> np.ndarray:
        """
        对数据集的指定分段执行预测。

        `segment` 通常用于区分训练集/验证集/测试集时间窗口，
        返回值应与该分段样本一一对应，供信号生成与评估使用。
        """
        pass

    def detail(self) -> Any:
        """
        返回模型细节信息。

        子类可重写为输出特征权重、树结构摘要、超参数等可解释信息。
        """
        return
