"""
技术指标因子计算模块

权重：35%
包含均线、MACD、KDJ、RSI、布林带、成交量等指标
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple

from config.settings import TECHNICAL_CONFIG
from utils.logger import get_logger
from utils.helpers import normalize_score

logger = get_logger(__name__)


class TechnicalFactor:
    """技术指标因子计算器"""

    def __init__(self):
        self.config = TECHNICAL_CONFIG

    def calculate_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算移动平均线"""
        for period in self.config["ma_periods"]:
            df[f"ma{period}"] = df["close"].rolling(window=period).mean()
        return df

    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 MACD 指标"""
        fast = self.config["macd_fast"]
        slow = self.config["macd_slow"]
        signal = self.config["macd_signal"]

        exp1 = df["close"].ewm(span=fast, adjust=False).mean()
        exp2 = df["close"].ewm(span=slow, adjust=False).mean()
        df["macd_dif"] = exp1 - exp2
        df["macd_dea"] = df["macd_dif"].ewm(span=signal, adjust=False).mean()
        df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2

        return df

    def calculate_kdj(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 KDJ 指标"""
        period = self.config["kdj_period"]

        low_min = df["low"].rolling(window=period).min()
        high_max = df["high"].rolling(window=period).max()

        rsv = (df["close"] - low_min) / (high_max - low_min) * 100
        rsv = rsv.fillna(50)  # 初始值

        df["kdj_k"] = rsv.ewm(com=2, adjust=False).mean()
        df["kdj_d"] = df["kdj_k"].ewm(com=2, adjust=False).mean()
        df["kdj_j"] = 3 * df["kdj_k"] - 2 * df["kdj_d"]

        return df

    def calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 RSI 指标"""
        for period in self.config["rsi_periods"]:
            delta = df["close"].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean()

            rs = avg_gain / avg_loss.replace(0, np.inf)
            df[f"rsi_{period}"] = 100 - (100 / (1 + rs))

        return df

    def calculate_boll(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算布林带"""
        period = self.config["boll_period"]
        std_dev = self.config["boll_std"]

        df["boll_mid"] = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()
        df["boll_upper"] = df["boll_mid"] + std_dev * std
        df["boll_lower"] = df["boll_mid"] - std_dev * std

        return df

    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 ATR（平均真实波幅）"""
        period = self.config["atr_period"]

        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=period).mean()

        return df

    def calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 ADX（平均趋向指数）"""
        period = self.config["adx_period"]

        # 计算 +DM 和 -DM
        df["high_diff"] = df["high"].diff()
        df["low_diff"] = df["low"].diff()

        plus_dm = np.where(
            (df["high_diff"] > df["low_diff"].abs()) & (df["high_diff"] > 0),
            df["high_diff"],
            0
        )
        minus_dm = np.where(
            (df["low_diff"].abs() > df["high_diff"]) & (df["low_diff"] < 0),
            df["low_diff"].abs(),
            0
        )

        # 计算 TR
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([
            high_low,
            pd.Series(high_close, index=df.index),
            pd.Series(low_close, index=df.index)
        ], axis=1).max(axis=1)

        # 平滑处理
        atr = pd.Series(tr).rolling(window=period).mean()
        plus_di = 100 * pd.Series(plus_dm).rolling(window=period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm).rolling(window=period).mean() / atr

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.inf)
        df["adx"] = dx.rolling(window=period).mean()
        df["plus_di"] = plus_di
        df["minus_di"] = minus_di

        return df

    def calculate_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算 OBV（能量潮）"""
        obv = [0]
        for i in range(1, len(df)):
            if df.iloc[i]["close"] > df.iloc[i-1]["close"]:
                obv.append(obv[-1] + df.iloc[i]["vol"])
            elif df.iloc[i]["close"] < df.iloc[i-1]["close"]:
                obv.append(obv[-1] - df.iloc[i]["vol"])
            else:
                obv.append(obv[-1])

        df["obv"] = obv
        return df

    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算所有技术指标"""
        df = df.copy()
        df = df.sort_values("trade_date")

        df = self.calculate_ma(df)
        df = self.calculate_macd(df)
        df = self.calculate_kdj(df)
        df = self.calculate_rsi(df)
        df = self.calculate_boll(df)
        df = self.calculate_atr(df)
        df = self.calculate_adx(df)
        df = self.calculate_obv(df)

        # 计算成交量均线
        df["vol_ma5"] = df["vol"].rolling(window=5).mean()
        df["vol_ma10"] = df["vol"].rolling(window=10).mean()

        return df

    def score_ma_trend(self, df: pd.DataFrame) -> float:
        """
        均线趋势得分（右侧交易：多头排列）

        条件：MA5 > MA10 > MA20 > MA60，且股价在 MA20 之上
        """
        if len(df) < 60:
            return 50.0

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        score = 50.0

        # 检查多头排列
        ma_conditions = [
            latest["ma5"] > latest["ma10"],
            latest["ma10"] > latest["ma20"],
            latest["ma20"] > latest["ma60"],
            latest["close"] > latest["ma20"],
            latest["close"] > latest["ma60"],
        ]

        ma_score = sum(ma_conditions) / len(ma_conditions) * 100

        # 均线方向（与前一天比较）
        if latest["ma5"] > prev["ma5"]:
            score += 10
        if latest["ma10"] > prev["ma10"]:
            score += 10
        if latest["ma20"] > prev["ma20"]:
            score += 10

        return min(100, ma_score * 0.6 + score * 0.4)

    def score_macd(self, df: pd.DataFrame) -> float:
        """
        MACD 得分

        金叉、零轴上方、红柱放大等信号
        """
        if len(df) < 30:
            return 50.0

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        score = 50.0

        # DIF 和 DEA 位置
        if latest["macd_dif"] > 0:
            score += 15  # 零轴上方
        if latest["macd_dif"] > latest["macd_dea"]:
            score += 15  # 金叉状态

        # 金叉信号（刚发生）
        if prev["macd_dif"] <= prev["macd_dea"] and latest["macd_dif"] > latest["macd_dea"]:
            score += 20  # 刚金叉

        # 红柱放大
        if latest["macd_hist"] > 0 and latest["macd_hist"] > prev["macd_hist"]:
            score += 10

        return min(100, score)

    def score_kdj(self, df: pd.DataFrame) -> float:
        """
        KDJ 得分

        J 值从低位拐头向上
        """
        if len(df) < 10:
            return 50.0

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        prev2 = df.iloc[-3] if len(df) > 2 else prev

        score = 50.0

        j = latest["kdj_j"]
        j_prev = prev["kdj_j"]

        # J 值位置
        if j < 20:
            score -= 20  # 超卖区，但可能还未拐头
        elif j > 80:
            score += 10  # 超买区，但有惯性
        elif 40 <= j <= 60:
            score += 20  # 中间区域，健康

        # J 值拐头向上
        if j > j_prev:
            score += 20
        if j_prev > prev2["kdj_j"] and j > j_prev:
            score += 15  # 连续向上

        # 金叉
        if latest["kdj_k"] > latest["kdj_d"]:
            score += 15

        return min(100, max(0, score))

    def score_rsi(self, df: pd.DataFrame) -> float:
        """
        RSI 得分

        RSI > 50 为强势区
        """
        if len(df) < 10:
            return 50.0

        latest = df.iloc[-1]

        rsi_6 = latest.get("rsi_6", 50)
        rsi_12 = latest.get("rsi_12", 50)
        rsi_24 = latest.get("rsi_24", 50)

        score = 50.0

        # RSI 位置
        if rsi_6 > 50:
            score += 15
        if rsi_12 > 50:
            score += 15
        if rsi_24 > 50:
            score += 10

        # 强势区但不超买
        if 50 < rsi_6 < 80:
            score += 10
        elif rsi_6 >= 80:
            score -= 10  # 超买风险

        return min(100, max(0, score))

    def score_boll(self, df: pd.DataFrame) -> float:
        """
        布林带得分

        股价突破中轨或在上轨附近
        """
        if len(df) < 20:
            return 50.0

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        score = 50.0

        close = latest["close"]
        mid = latest["boll_mid"]
        upper = latest["boll_upper"]
        lower = latest["boll_lower"]

        # 股价位置
        if close > mid:
            score += 20  # 中轨上方
        if close > upper * 0.98:
            score += 15  # 接近上轨

        # 突破中轨
        if prev["close"] <= prev["boll_mid"] and close > mid:
            score += 20  # 刚突破中轨

        # 布林带开口（波动率增加）
        bandwidth_prev = (prev["boll_upper"] - prev["boll_lower"]) / prev["boll_mid"]
        bandwidth = (upper - lower) / mid
        if bandwidth > bandwidth_prev:
            score += 10  # 开口扩大

        return min(100, max(0, score))

    def score_volume(self, df: pd.DataFrame) -> float:
        """
        成交量得分

        放量上涨
        """
        if len(df) < 10:
            return 50.0

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        score = 50.0

        vol = latest["vol"]
        vol_ma5 = latest.get("vol_ma5", vol)
        vol_ma10 = latest.get("vol_ma10", vol)

        # 成交量放大
        if vol > vol_ma5:
            score += 15
        if vol > vol_ma10:
            score += 10

        # 量比
        volume_ratio = vol / vol_ma5 if vol_ma5 > 0 else 1
        if 1.5 < volume_ratio < 3:
            score += 15  # 温和放量
        elif volume_ratio >= 3:
            score += 10  # 大量，但可能有风险

        # 放量上涨
        if latest["close"] > prev["close"] and vol > vol_ma5:
            score += 20

        return min(100, max(0, score))

    def score_obv(self, df: pd.DataFrame) -> float:
        """
        OBV 得分

        能量潮向上
        """
        if len(df) < 20:
            return 50.0

        latest = df.iloc[-1]
        prev5 = df.iloc[-5] if len(df) > 5 else df.iloc[0]

        score = 50.0

        # OBV 趋势
        if latest["obv"] > prev5["obv"]:
            score += 25

        # OBV 与股价背离检测（股价跌但 OBV 升，可能是吸筹）
        price_change = latest["close"] - prev5["close"]
        obv_change = latest["obv"] - prev5["obv"]

        if obv_change > 0 and price_change < 0:
            score += 20  # 背离，可能有机会

        return min(100, max(0, score))

    def score_adx(self, df: pd.DataFrame) -> float:
        """
        ADX 得分

        ADX > 25 表示趋势明显
        """
        if len(df) < 20:
            return 50.0

        latest = df.iloc[-1]

        adx = latest.get("adx", 0)
        plus_di = latest.get("plus_di", 0)
        minus_di = latest.get("minus_di", 0)

        score = 50.0

        # ADX 强度
        if adx > 40:
            score += 25  # 强趋势
        elif adx > 25:
            score += 15  # 明显趋势

        # 方向
        if plus_di > minus_di:
            score += 20  # 向上趋势

        return min(100, max(0, score))

    def calculate_composite_score(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        计算技术指标综合得分

        Returns:
            dict: 各维度得分和综合得分
        """
        if df.empty or len(df) < 30:
            return {
                "ma_score": 50.0,
                "macd_score": 50.0,
                "kdj_score": 50.0,
                "rsi_score": 50.0,
                "boll_score": 50.0,
                "volume_score": 50.0,
                "obv_score": 50.0,
                "adx_score": 50.0,
                "technical_score": 50.0,
                "signal_count": 0,
            }

        # 计算所有指标
        df = self.calculate_all_indicators(df)

        # 各维度得分
        ma_score = self.score_ma_trend(df)
        macd_score = self.score_macd(df)
        kdj_score = self.score_kdj(df)
        rsi_score = self.score_rsi(df)
        boll_score = self.score_boll(df)
        volume_score = self.score_volume(df)
        obv_score = self.score_obv(df)
        adx_score = self.score_adx(df)

        # 综合得分（均线 20% + MACD 20% + KDJ 15% + RSI 10% + 布林 10% + 成交量 15% + OBV 5% + ADX 5%）
        technical_score = (
            ma_score * 0.20 +
            macd_score * 0.20 +
            kdj_score * 0.15 +
            rsi_score * 0.10 +
            boll_score * 0.10 +
            volume_score * 0.15 +
            obv_score * 0.05 +
            adx_score * 0.05
        )

        # 统计买入信号数量
        signal_count = sum([
            ma_score >= 60,
            macd_score >= 60,
            kdj_score >= 60,
            rsi_score >= 60,
            boll_score >= 60,
            volume_score >= 60,
        ])

        return {
            "ma_score": ma_score,
            "macd_score": macd_score,
            "kdj_score": kdj_score,
            "rsi_score": rsi_score,
            "boll_score": boll_score,
            "volume_score": volume_score,
            "obv_score": obv_score,
            "adx_score": adx_score,
            "technical_score": technical_score,
            "signal_count": signal_count,
        }


def calculate_technical_score(df: pd.DataFrame) -> Dict[str, float]:
    """计算技术指标综合得分（便捷函数）"""
    factor = TechnicalFactor()
    return factor.calculate_composite_score(df)
