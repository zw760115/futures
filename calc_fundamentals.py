#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calc_fundamentals.py — 自动测算基差 + 产业利润（每日收盘后运行）

数据源（免费公开）:
  akshare futures_spot_price(date, vars_list)  —— 东方财富期现数据
  一次调用同时给出:
    - spot_price             现货价
    - dominant_contract      主力期货合约码
    - dominant_contract_price 主力期货价
    - dom_basis              主力基差 = 现货 − 主力期货
    - dom_basis_rate         基差率

输出:
  data/basis.json   {data_date, generated_at, basis:{CODE:{spot,dominant_contract,dominant_price,basis,basis_rate}}}
  data/profit.json  {data_date, generated_at, profit:{CODE:{value,unit,band,formula,legs,note,source}}}

说明:
  - 自动回溯交易日: 当天期现数据未发布时向前回溯最多 7 天
  - 产业利润公式仅用"期货腿"（全部来自 futures_spot_price 的主力价）+ 公开加工费常数；
    非期货腿（电力/进口成本等）用备注说明，不强行编造；公式为盘面/理论利润估算
  - 数据未覆盖的品种(如期现源无该品种)跳过，不报错
"""

import os
import sys
import json
import datetime as dt

try:
    import akshare as ak
except Exception as e:
    ak = None
    print("[WARN] akshare 未安装:", e, file=sys.stderr)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BASIS = os.path.join(HERE, "data", "basis.json")
OUT_PROFIT = os.path.join(HERE, "data", "profit.json")

# ---- 模板品种代码 ----
CODES = [
    "AU","AG","AL","AO","AP","BR","BU","C","CF","CJ","CS","CU","CY","EB","EG",
    "FG","HC","I","J","JD","JM","JR","L","LC","LH","LR","M","MA","NI","NR","OI",
    "P","PB","PF","PK","PM","PP","PS","PX","RB","RI","RM","RR","RS","SA","SF",
    "SI","SM","SN","SP","SR","SS","TA","UR","V","WH","Y","ZN","B","A",
]

# ---- 产业利润公式（仅期货腿 + 公开加工费常数；单位 元/吨，除贵金属外）----
# legs: 用各品种主力期货价（来自 futures_spot_price 的 dominant_contract_price）
# fee: 加工费/其他固定成本常数（元/吨），取自行业惯例估算，会随行情变动
PROFIT_FORMULAS = {
    "RB": {  # 螺纹钢厂利润
        "legs": ["RB","I","J"],
        "expr": lambda p: p["RB"] - 1.6*p["I"] - 0.5*p["J"] - 1100,
        "fee": 1100,
        "formula": "螺纹 − 1.6×铁矿 − 0.5×焦炭 − 加工费1100",
        "note": "加工费1100为行业估算常数；仅期货腿实时，未含合金/轧制差异",
    },
    "HC": {  # 热卷利润
        "legs": ["HC","I","J"],
        "expr": lambda p: p["HC"] - 1.6*p["I"] - 0.5*p["J"] - 1200,
        "fee": 1200,
        "formula": "热卷 − 1.6×铁矿 − 0.5×焦炭 − 加工费1200",
        "note": "加工费1200为行业估算常数",
    },
    "J": {  # 焦化利润
        "legs": ["J","JM"],
        "expr": lambda p: p["J"] - 1.33*p["JM"] - 300,
        "fee": 300,
        "formula": "焦炭 − 1.33×焦煤 − 加工费300",
        "note": "加工费300为行业估算常数（化产回收未计入）",
    },
    "M": {  # 大豆压榨(盘面, 豆一proxy)
        "legs": ["Y","M","A"],
        "expr": lambda p: 0.18*p["Y"] + 0.785*p["M"] - 1.0*p["A"] - 150,
        "fee": 150,
        "formula": "0.18×豆油 + 0.785×豆粕 − 1.0×豆一(豆二proxy) − 加工费150",
        "note": "压榨用到豆二(B)为进口大豆，期现源未含B；此处用豆一(A)近似，口径略偏",
    },
    "TA": {  # PTA加工利润
        "legs": ["TA","PX"],
        "expr": lambda p: p["TA"] - 0.655*p["PX"] - 600,
        "fee": 600,
        "formula": "PTA − 0.655×PX − 加工费600",
        "note": "0.655为单耗；加工费600为行业估算常数",
    },
    "FG": {  # 玻璃利润
        "legs": ["FG","SA"],
        "expr": lambda p: p["FG"] - 0.20*p["SA"] - 400,
        "fee": 400,
        "formula": "玻璃 − 0.20×纯碱 − 加工费400",
        "note": "吨玻璃耗0.20吨纯碱；加工费400为行业估算常数",
    },
}

# 基差率为正=现货升水(期货贴水)；利润带宽阈值（元/吨）
PROFIT_BAND_HI = 150
PROFIT_BAND_LO = -150


def backdate(start, days=7):
    d = dt.datetime.strptime(start, "%Y%m%d")
    out = []
    for i in range(days):
        out.append(d.strftime("%Y%m%d"))
        d -= dt.timedelta(days=1)
    return out


def fetch_spot(date):
    if ak is None:
        return None
    df = ak.futures_spot_price(date=date, vars_list=CODES)
    if df is None or len(df) == 0:
        return None
    return df


def main():
    start = dt.date.today().strftime("%Y%m%d")
    print(f"目标日期: {start}  回溯最多7天找最近期现数据...")

    df = None
    used = None
    for date in backdate(start, 7):
        try:
            df = fetch_spot(date)
        except Exception as e:
            print(f"  [{date}] 抓取异常: {e}", file=sys.stderr)
            df = None
        if df is not None and len(df):
            used = date
            break
        else:
            print(f"  {date} 无数据, 继续回溯")
    if df is None or not len(df):
        print("[ERROR] 近7天均无期现数据", file=sys.stderr)
        sys.exit(2)

    print(f"✅ 期现数据日期: {used}  覆盖 {len(df)} 个品种")

    # ---- 基差 ----
    basis = {}
    price_map = {}  # code -> dominant_contract_price（供利润公式）
    for _, r in df.iterrows():
        code = str(r["symbol"]).upper()
        try:
            spot = float(r["spot_price"])
            dcp = float(r["dominant_contract_price"])
            db = float(r["dom_basis"])
            brate = float(r["dom_basis_rate"])
        except Exception:
            continue
        if not isfinite_all(spot, dcp, db):
            continue
        basis[code] = {
            "spot": round(spot, 2),
            "dominant_contract": str(r["dominant_contract"]),
            "dominant_price": round(dcp, 2),
            "basis": round(db, 2),
            "basis_rate": round(brate, 5),
        }
        price_map[code] = dcp

    # ---- 产业利润（仅期货腿，来自 price_map）----
    profit = {}
    for code, f in PROFIT_FORMULAS.items():
        legs = f["legs"]
        if any(l not in price_map for l in legs):
            missing = [l for l in legs if l not in price_map]
            print(f"  [利润/{code}] 腿价缺失 {missing}, 跳过")
            continue
        p = {l: price_map[l] for l in legs}
        try:
            val = round(f["expr"](p), 1)
        except Exception as e:
            print(f"  [利润/{code}] 计算失败: {e}", file=sys.stderr)
            continue
        band = "high" if val > PROFIT_BAND_HI else ("low" if val < PROFIT_BAND_LO else "mid")
        profit[code] = {
            "value": val,
            "unit": "元/吨",
            "band": band,
            "formula": f["formula"],
            "legs": {l: round(price_map[l], 2) for l in legs},
            "fee": f["fee"],
            "note": f["note"],
            "source": "akshare futures_spot_price 主力价推算",
        }

    meta = {
        "data_date": used,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    os.makedirs(os.path.dirname(OUT_BASIS), exist_ok=True)
    with open(OUT_BASIS, "w", encoding="utf-8") as f:
        json.dump({**meta, "basis": basis}, f, ensure_ascii=False, indent=2)
    with open(OUT_PROFIT, "w", encoding="utf-8") as f:
        json.dump({**meta, "profit": profit}, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUT_BASIS}（基差 {len(basis)} 品种）")
    print(f"✅ 已写入 {OUT_PROFIT}（产业利润 {len(profit)} 品种）")
    # 样例
    for c in ["RB", "TA", "M"]:
        b = basis.get(c)
        pr = profit.get(c)
        if b: print(f"   {c} 现货={b['spot']} 主力={b['dominant_price']} 基差={b['basis']}（{b['basis_rate']*100:.2f}%）")
        if pr: print(f"   {c} 产业利润={pr['value']} 元/吨 [{pr['band']}] 腿={pr['legs']}")


def isfinite_all(*xs):
    import math
    return all(x is not None and not (isinstance(x, float) and math.isnan(x)) for x in xs)


if __name__ == "__main__":
    main()
