"""
ML 选股模型模块

基于 LightGBM 的机器学习选股模型
参考 Qlib 等开源项目的特征工程和模型训练方法

功能:
- 特征工程：技术指标、基本面因子、资金流向
- 模型训练：LightGBM 多因子模型
- 预测评分：股票收益预测
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MLPrediction:
    """ML 预测结果"""
    ts_code: str
    stock_name: str
    predict_score: float  # 预测得分 0-100
    predict_return: float  # 预期收益率
    confidence: str  # 置信度：高/中/低
    rank: int = 0


class MLFeatureEngine:
    """ML 特征工程"""

    def __init__(self):
        # 特征配置
        self.feature_config = {
            # 技术指标
            "ma_features": ["ma5", "ma10", "ma20", "ma60"],
            "macd_features": ["macd_dif", "macd_dea", "macd_hist"],
            "kdj_features": ["kdj_k", "kdj_d", "kdj_j"],
            "rsi_features": ["rsi6", "rsi12", "rsi24"],
            "boll_features": ["boll_upper", "boll_mid", "boll_lower"],

            # 基本面
            "fundamental_features": ["pe_ttm", "pb", "roe", "revenue_growth", "profit_growth"],

            # 资金流向
            "capital_features": ["net_inflow", "north_hold_change", "large_order_ratio"],

            # 动量特征
            "momentum_features": ["return_5d", "return_10d", "return_20d"],

            # 波动率特征
            "volatility_features": ["volatility_20d", "atr_ratio"],
        }

    def create_features(
        self,
        price_df: pd.DataFrame,
        fundamental_data: Optional[Dict] = None,
        capital_data: Optional[Dict] = None,
    ) -> pd.DataFrame:
        """
        创建特征矩阵

        Args:
            price_df: 价格数据 DataFrame
            fundamental_data: 基本面数据
            capital_data: 资金流向数据

        Returns:
            pd.DataFrame: 特征矩阵
        """
        if price_df.empty:
            return pd.DataFrame()

        features = pd.DataFrame(index=price_df.index)

        # 1. MA 特征
        for ma in [5, 10, 20, 60]:
            if f'ma{ma}' in price_df.columns:
                features[f'ma{ma}'] = price_df[f'ma{ma}']
            else:
                features[f'ma{ma}'] = price_df['close'].rolling(ma).mean()

        # MA 排列特征
        features['ma_aligned'] = (
            (features['ma5'] > features['ma10']).astype(int) &
            (features['ma10'] > features['ma20']).astype(int)
        )

        # 2. MACD 特征
        if 'macd_dif' in price_df.columns:
            features['macd_dif'] = price_df['macd_dif']
            features['macd_dea'] = price_df.get('macd_dea', 0)
            features['macd_hist'] = price_df.get('macd_hist', 0)
        else:
            # 计算 MACD
            exp1 = price_df['close'].ewm(span=12, adjust=False)
            exp2 = price_df['close'].ewm(span=26, adjust=False)
            features['macd_dif'] = exp1.mean() - exp2.mean()
            features['macd_dea'] = features['macd_dif'].ewm(span=9, adjust=False).mean()
            features['macd_hist'] = features['macd_dif'] - features['macd_dea']

        # 3. KDJ 特征
        if 'kdj_k' in price_df.columns:
            features['kdj_k'] = price_df['kdj_k']
            features['kdj_d'] = price_df.get('kdj_d', 0)
            features['kdj_j'] = price_df.get('kdj_j', 0)

        # 4. RSI 特征
        if 'rsi' in price_df.columns:
            features['rsi'] = price_df['rsi']

        # 5. 布林带特征
        if 'boll_upper' in price_df.columns:
            features['boll_upper'] = price_df['boll_upper']
            features['boll_mid'] = price_df.get('boll_mid', 0)
            features['boll_lower'] = price_df.get('boll_lower', 0)
        else:
            # 计算布林带
            features['boll_mid'] = price_df['close'].rolling(20).mean()
            std = price_df['close'].rolling(20).std()
            features['boll_upper'] = features['boll_mid'] + 2 * std
            features['boll_lower'] = features['boll_mid'] - 2 * std

        # 6. 动量特征
        for period in [5, 10, 20]:
            features[f'return_{period}d'] = price_df['close'].pct_change(period) * 100

        # 7. 波动率特征
        features['volatility_20d'] = price_df['close'].pct_change().rolling(20).std() * 100

        if 'atr' in price_df.columns:
            features['atr_ratio'] = price_df['atr'] / price_df['close'] * 100
        else:
            high_low = price_df['high'] - price_df['low']
            features['atr_ratio'] = (high_low.rolling(14).mean() / price_df['close'] * 100)

        # 8. 成交量特征
        features['volume_ratio'] = price_df['vol'] / price_df['vol'].rolling(5).mean()
        features['amount_ratio'] = price_df.get('amount', price_df['vol']) / price_df.get('amount', price_df['vol']).rolling(5).mean()

        # 9. 基本面特征（如果有）
        if fundamental_data:
            features['pe_ttm'] = fundamental_data.get('pe_ttm', 20)
            features['pb'] = fundamental_data.get('pb', 2)
            features['roe'] = fundamental_data.get('roe', 10)
            features['revenue_growth'] = fundamental_data.get('revenue_growth', 0)
            features['profit_growth'] = fundamental_data.get('profit_growth', 0)

        # 10. 资金流向特征（如果有）
        if capital_data:
            features['net_inflow'] = capital_data.get('net_inflow', 0)
            features['north_hold_change'] = capital_data.get('north_hold_change', 0)
            features['large_order_ratio'] = capital_data.get('large_order_ratio', 0)

        # 填充 NaN 值
        features = features.fillna(method='ffill').fillna(0)

        return features


class MLStockPredictor:
    """ML 股票预测器"""

    def __init__(self, model=None):
        self.model = model
        self.feature_engine = MLFeatureEngine()

        # 特征重要性（预定义）
        self.feature_importance = {
            'ma_aligned': 0.15,
            'macd_dif': 0.10,
            'kdj_k': 0.08,
            'rsi': 0.08,
            'return_5d': 0.12,
            'return_10d': 0.10,
            'return_20d': 0.08,
            'volatility_20d': 0.05,
            'volume_ratio': 0.08,
            'pe_ttm': 0.05,
            'roe': 0.05,
            'north_hold_change': 0.06,
        }

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
        **kwargs
    ) -> Dict:
        """
        训练模型

        Args:
            X_train: 训练特征
            y_train: 训练标签（未来收益率）
            X_val: 验证特征
            y_val: 验证标签
            **kwargs: LightGBM 训练参数

        Returns:
            dict: 训练结果
        """
        try:
            import lightgbm as lgb
        except ImportError:
            logger.warning("LightGBM 未安装，使用简化模型")
            return self._train_simple_model(X_train, y_train, X_val, y_val)

        # LightGBM 参数
        params = {
            'objective': 'regression',
            'metric': 'mse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'seed': 42,
        }
        params.update(kwargs)

        # 创建数据集
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data) if X_val is not None else None

        # 训练
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=1000,
            valid_sets=[val_data] if val_data else [train_data],
            early_stopping_rounds=50,
            verbose_eval=100,
        )

        # 评估
        result = {
            'model': self.model,
            'feature_importance': dict(zip(X_train.columns, self.model.feature_importance())),
        }

        if X_val is not None and y_val is not None:
            pred = self.model.predict(X_val)
            result['val_mse'] = float(np.mean((pred - y_val) ** 2))
            result['val_ic'] = float(np.corrcoef(pred, y_val)[0, 1]) if len(y_val) > 1 else 0

        return result

    def _train_simple_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> Dict:
        """简化模型训练（使用 sklearn）"""
        try:
            from sklearn.ensemble import RandomForestRegressor

            rf = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            rf.fit(X_train, y_train)

            self.model = rf

            result = {
                'model': rf,
                'feature_importance': dict(zip(X_train.columns, rf.feature_importances_)),
            }

            if X_val is not None and y_val is not None:
                pred = rf.predict(X_val)
                result['val_mse'] = float(np.mean((pred - y_val) ** 2))
                result['val_ic'] = float(np.corrcoef(pred, y_val)[0, 1]) if len(y_val) > 1 else 0

            return result

        except ImportError:
            logger.warning("sklearn 未安装，使用规则模型")
            return {'model': None, 'feature_importance': self.feature_importance}

    def predict(self, features: pd.DataFrame) -> List[MLPrediction]:
        """
        预测股票收益

        Args:
            features: 特征矩阵

        Returns:
            List[MLPrediction]: 预测结果列表
        """
        if self.model is None:
            # 使用规则评分
            return self._rule_based_predict(features)

        # 模型预测
        predictions = self.model.predict(features)

        # 转换为预测对象
        result = []
        for idx, pred in enumerate(predictions):
            # 预测得分（映射到 0-100）
            score = self._normalize_prediction(pred)

            # 置信度
            if score >= 70:
                confidence = "高"
            elif score >= 55:
                confidence = "中"
            else:
                confidence = "低"

            result.append(MLPrediction(
                ts_code=features.index[idx] if idx < len(features.index) else f"stock_{idx}",
                stock_name="",
                predict_score=score,
                predict_return=pred,
                confidence=confidence,
            ))

        return result

    def _rule_based_predict(self, features: pd.DataFrame) -> List[MLPrediction]:
        """规则基础预测（当没有模型时使用）"""
        result = []

        for idx, row in features.iterrows():
            score = 50.0

            # MA 排列
            if row.get('ma_aligned', 0) > 0:
                score += 15

            # MACD
            if row.get('macd_dif', 0) > 0:
                score += 10

            # 动量
            if row.get('return_5d', 0) > 0:
                score += 10
            if row.get('return_10d', 0) > 0:
                score += 8
            if row.get('return_20d', 0) > 0:
                score += 5

            # 成交量
            if row.get('volume_ratio', 1) > 1.5:
                score += 10

            # 波动率（低波动率加分）
            if row.get('volatility_20d', 5) < 3:
                score += 5

            score = min(100, max(0, score))

            confidence = "高" if score >= 70 else "中" if score >= 55 else "低"

            result.append(MLPrediction(
                ts_code=idx if isinstance(idx, str) else f"stock_{idx}",
                stock_name="",
                predict_score=score,
                predict_return=(score - 50) / 5,  # 简化映射
                confidence=confidence,
            ))

        return result

    def _normalize_prediction(self, pred: float) -> float:
        """将预测值归一化到 0-100"""
        # 假设预测收益率在 -20% 到 +20% 之间
        normalized = 50 + pred * 2.5
        return min(100, max(0, normalized))

    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        if self.model is not None:
            if hasattr(self.model, 'feature_importances_'):
                return dict(zip(
                    self.feature_engine.feature_config.get('all_features', []),
                    self.model.feature_importances_
                ))
            elif hasattr(self.model, 'feature_importance'):
                return self.model.feature_importance()
        return self.feature_importance


def create_ml_predictor() -> MLStockPredictor:
    """创建 ML 预测器实例"""
    return MLStockPredictor()


def get_ml_score(
    price_df: pd.DataFrame,
    fundamental_data: Optional[Dict] = None,
    capital_data: Optional[Dict] = None,
) -> Dict[str, float]:
    """
    获取 ML 评分（便捷函数）

    Args:
        price_df: 价格数据
        fundamental_data: 基本面数据
        capital_data: 资金流向数据

    Returns:
        dict: ML 评分结果
    """
    predictor = create_ml_predictor()
    features = predictor.feature_engine.create_features(
        price_df, fundamental_data, capital_data
    )

    if features.empty:
        return {"ml_score": 50.0, "ml_confidence": "中"}

    predictions = predictor.predict(features)

    if not predictions:
        return {"ml_score": 50.0, "ml_confidence": "中"}

    # 取最新预测
    latest = predictions[-1]
    return {
        "ml_score": latest.predict_score,
        "ml_confidence": latest.confidence,
        "ml_predict_return": latest.predict_return,
    }
