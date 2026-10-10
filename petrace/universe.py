# -*- coding: utf-8 -*-
"""
petrace.universe - the verified index catalog.

Every upstream id below was confirmed live before being written down. An index
may legitimately have no PE source at all (that is a declared gap, surfaced in
the UI, not an error).

Upstream ids - all verified 2026-10-10
--------------------------------------
danjuan   danjuanfunds.com  PE/PB history, WEEKLY, 2016-10-09 -> (38 codes live)
legulegu  legulegu.com via akshare stock_index_pe_lg, MONTHLY, 2005-> (12 live)
csindex   csindex.com.cn official perf feed, DAILY PE-TTM + close from 2004.
          Its `peg` field is the PE-TTM (verification in sources.csindex_pe).
          PE depth starts 2011-06-28 for most codes, later for some.
multpl    multpl.com monthly tables, S&P 500 PE, very deep history

price     a chain of fallbacks, each entry (source, spec):
            ("sina_cn", "sh000300")     A股 daily, up to 6000 bars, from ~2002
            ("tencent", ("hkHSI","week",2000))   HK from 1989
            ("sina_us", ".INX")         US daily from 2004
            ("sina_gi", "DAX")          non-US developed, ~1000 bars only
            ("em", "1.000300")          eastmoney - kept last; host hard-blocks
          price_best() walks the chain and skips any source whose last bar is
          stale, so a dead-but-HTTP-200 feed can never be silently used.

IMPORTANT - do not splice legulegu onto danjuan.
The two publish different PE levels for the same index (measured over their
observed overlap: 沪深300 -4.2%, 中证500 -17.3%, 中证1000 -27.9%). Joining them
would manufacture a step change that never happened in the market. They are
therefore offered as two separate, individually labelled series.
"""

REGIONS = ["中国A股", "中国香港", "美国", "欧洲", "亚太"]

# Shorthand builders for the common price chains.
def _cn(code, cs=None):
    """A-share chain: Sina daily first (deepest), Tencent daily, then the CSI
    official feed. The CSIndex entry costs no extra request when the index also
    has a CSIndex PE series - both come from the same cached payload."""
    chain = [("sina_cn", code), ("tencent", (code, "day", 2000))]
    if cs:
        chain.append(("csindex", cs))
    return chain


def _hk(code):
    """HK chain: weekly first (1989->), daily as fallback."""
    return [("tencent", (code, "week", 2000)), ("tencent", (code, "day", 2000))]


def _us(sym, tx):
    return [("sina_us", sym), ("tencent", (tx, "week", 2000))]


def _etf(sym):
    """Price taken from a tracking ETF because the index itself has no free
    price feed. Always paired with a `price_note` so the UI can say so."""
    return [("sina_us", sym)]


def _etf_cn(sym):
    """Same, for a Shanghai/Shenzhen listed ETF (sina_cn feed)."""
    return [("sina_cn", sym)]


INDICES = [
    # ------------------------------------------------------------- 中国 A 股
    dict(id="SH000300", name="沪深300", region="中国A股", country="中国", developed=False,
         danjuan="SH000300", legulegu="沪深300", csindex="000300",
         price=_cn("sh000300", "000300"),
         note="A股核心大盘宽基"),
    dict(id="SH000016", name="上证50", region="中国A股", country="中国", developed=False,
         danjuan="SH000016", legulegu="上证50", csindex="000016",
         price=_cn("sh000016", "000016"),
         note="沪市超大盘蓝筹"),
    dict(id="SH000905", name="中证500", region="中国A股", country="中国", developed=False,
         danjuan="SH000905", legulegu="中证500", csindex="000905",
         price=_cn("sh000905", "000905"),
         note="A股中盘代表"),
    dict(id="SH000852", name="中证1000", region="中国A股", country="中国", developed=False,
         danjuan="SH000852", legulegu="中证1000", csindex="000852",
         price=_cn("sh000852", "000852"),
         note="A股小盘代表"),
    dict(id="SH000688", name="科创50", region="中国A股", country="中国", developed=False,
         danjuan="SH000688", csindex="000688", price=_cn("sh000688", "000688"),
         note="科创板头部50家（PE自2020-07起）"),
    dict(id="SZ399006", name="创业板指", region="中国A股", country="中国", developed=False,
         danjuan="SZ399006", price=_cn("sz399006"), note="创业板龙头100家"),
    dict(id="SH000903", name="中证100", region="中国A股", country="中国", developed=False,
         danjuan="SH000903", legulegu="中证100", csindex="000903",
         price=_cn("sh000903", "000903"), note="大盘蓝筹"),
    dict(id="SH000010", name="上证180", region="中国A股", country="中国", developed=False,
         danjuan="SH000010", legulegu="上证180", csindex="000010",
         price=_cn("sh000010", "000010"), note="沪市大盘"),
    dict(id="SZ399001", name="深证成指", region="中国A股", country="中国", developed=False,
         danjuan="SZ399001", price=_cn("sz399001"), note="深市核心宽基"),
    dict(id="SZ399330", name="深证100", region="中国A股", country="中国", developed=False,
         danjuan="SZ399330", legulegu="深证100", price=_cn("sz399330"), note="深市大盘"),
    dict(id="SZ399324", name="深证红利", region="中国A股", country="中国", developed=False,
         danjuan="SZ399324", legulegu="深证红利", price=_cn("sz399324"), note="深市高股息"),
    dict(id="SH000015", name="上证红利", region="中国A股", country="中国", developed=False,
         danjuan="SH000015", legulegu="上证红利", csindex="000015",
         price=_cn("sh000015", "000015"), note="沪市高股息"),
    dict(id="SH000922", name="中证红利", region="中国A股", country="中国", developed=False,
         danjuan="SH000922", csindex="000922", price=_cn("sh000922", "000922"),
         note="A股高股息代表"),
    dict(id="SH000925", name="基本面50", region="中国A股", country="中国", developed=False,
         danjuan="SH000925", csindex="000925", price=_cn("sh000925", "000925"),
         note="基本面加权大盘"),
    dict(id="SH000919", name="300价值", region="中国A股", country="中国", developed=False,
         danjuan="SH000919", csindex="000919", price=_cn("sh000919", "000919"),
         note="沪深300价值风格"),
    dict(id="SZ399317", name="国证A指", region="中国A股", country="中国", developed=False,
         danjuan="SZ399317", price=_cn("sz399317"), note="全市场综合"),
    dict(id="SZ399550", name="央视50", region="中国A股", country="中国", developed=False,
         danjuan="SZ399550", price=_cn("sz399550"), note="央视财经50样本"),
    dict(id="SH000170", name="50AH优选", region="中国A股", country="中国", developed=False,
         danjuan="SH000170", price=_cn("sh000170"), note="A+H两地优选"),
    dict(id="SH000991", name="全指医药", region="中国A股", country="中国", developed=False,
         danjuan="SH000991", csindex="000991", price=_cn("sh000991", "000991"),
         note="医药行业"),
    dict(id="SH000932", name="主要消费", region="中国A股", country="中国", developed=False,
         danjuan="SH000932", csindex="000932", price=_cn("sh000932", "000932"),
         note="主要消费行业"),
    dict(id="SH000993", name="全指信息", region="中国A股", country="中国", developed=False,
         danjuan="SH000993", csindex="000993", price=_cn("sh000993", "000993"),
         note="信息技术行业"),
    dict(id="SH000009", name="上证380", region="中国A股", country="中国", developed=False,
         legulegu="上证380", csindex="000009", price=_cn("sh000009", "000009"),
         note="沪市中小盘"),
    dict(id="SZ399673", name="创业板50", region="中国A股", country="中国", developed=False,
         price=_cn("sz399673"), legulegu="创业板50", note="创业板头部50家（仅月度PE）"),
    dict(id="SH000906", name="中证800", region="中国A股", country="中国", developed=False,
         legulegu="中证800", csindex="000906", price=_cn("sh000906", "000906"),
         note="大中盘综合"),
    dict(id="CSI716567", name="MSCI中国", region="中国A股", country="中国", developed=False,
         danjuan="CSI716567", price=_etf("MCHI"),
         price_note="ETF代理：MCHI（iShares MSCI中国ETF）",
         note="MSCI中国指数（价格以 MCHI ETF 代理）"),
    dict(id="CSI930652", name="中证电子", region="中国A股", country="中国", developed=False,
         danjuan="CSI930652", csindex="930652", price=[("csindex", "930652")],
         note="电子行业"),
    dict(id="CSI931087", name="科技龙头", region="中国A股", country="中国", developed=False,
         danjuan="CSI931087", csindex="931087", price=[("csindex", "931087")],
         note="科技龙头50（PE自2019-03起）"),

    # ------------------------------------------------------------- 中国香港
    dict(id="HKHSI", name="恒生指数", region="中国香港", country="中国香港", developed=True,
         danjuan="HKHSI", price=_hk("hkHSI"), note="港股核心宽基"),
    dict(id="HKHSCEI", name="恒生国企指数", region="中国香港", country="中国香港", developed=True,
         danjuan="HKHSCEI", price=_hk("hkHSCEI"), note="H股/中资企业"),
    dict(id="HKHSTECH", name="恒生科技", region="中国香港", country="中国香港", developed=True,
         danjuan="HKHSTECH", price=_hk("hkHSTECH"), note="港股科技龙头（2020-07起）"),
    dict(id="CSIH11136", name="中国互联", region="中国香港", country="中国香港", developed=True,
         danjuan="CSIH11136", csindex="H11136", price=[("csindex", "H11136")],
         note="中概互联网"),
    dict(id="HSFML25", name="香港大盘", region="中国香港", country="中国香港", developed=True,
         danjuan="HSFML25", price=[("sina_cn", "sz159920")],
         price_note="ETF代理：sz159920（华夏恒生ETF）",
         note="港股大盘（价格以恒生ETF代理）"),
    dict(id="SPHCMSHP", name="香港中小", region="中国香港", country="中国香港", developed=True,
         danjuan="SPHCMSHP", note="港股中小盘（暂无价格源）"),
    dict(id="HKHSSCNE", name="香港新经济", region="中国香港", country="中国香港", developed=True,
         danjuan="HKHSSCNE", note="港股新经济（2018-11起，暂无价格源）"),

    # ----------------------------------------------------------------- 美国
    dict(id="SP500", name="标普500", region="美国", country="美国", developed=True,
         danjuan="SP500", price=_us(".INX", "us.INX"), multpl="s-p-500-pe-ratio",
         note="美国大盘核心；另有 multpl 月度长历史"),
    dict(id="NDX", name="纳斯达克100", region="美国", country="美国", developed=True,
         danjuan="NDX", price=_us(".NDX", "us.NDX"), note="美国科技龙头"),
    dict(id="DJI", name="道琼斯工业平均", region="美国", country="美国", developed=True,
         price=[("sina_us", ".DJI"), ("tencent", ("us.DJI", "week", 2000))],
         note="美国蓝筹30家（无PE源）"),
    dict(id="SPACEVCP", name="标普价值", region="美国", country="美国", developed=True,
         danjuan="SPACEVCP", price=_etf("SPYV"),
         price_note="ETF代理：SPYV（SPDR 标普500价值ETF）",
         note="标普500价值风格（价格以 SPYV ETF 代理）"),
    dict(id="SPCQVCP", name="标普质量", region="美国", country="美国", developed=True,
         danjuan="SPCQVCP", price=_etf("SPHQ"),
         price_note="ETF代理：SPHQ（Invesco 标普500质量ETF）",
         note="标普500质量风格（价格以 SPHQ ETF 代理）"),
    dict(id="CSPSADRP", name="标普红利", region="美国", country="美国", developed=True,
         danjuan="CSPSADRP", price=_etf("NOBL"),
         price_note="ETF代理：NOBL（ProShares 标普红利贵族ETF）",
         note="标普红利贵族（价格以 NOBL ETF 代理，跟踪同一指数）"),

    # ----------------------------------------------------------------- 欧洲
    dict(id="GDAXI", name="德国DAX", region="欧洲", country="德国", developed=True,
         danjuan="GDAXI", price=[("sina_gi", "DAX")], note="德国蓝筹40家"),
    dict(id="FTSE", name="英国富时100", region="欧洲", country="英国", developed=True,
         price=[("sina_gi", "UKX")], note="英国大盘（无PE源）"),
    dict(id="FCHI", name="法国CAC40", region="欧洲", country="法国", developed=True,
         price=[("sina_gi", "CAC")], note="法国蓝筹40家（无PE源）"),
    dict(id="SX5E", name="欧洲斯托克50", region="欧洲", country="欧元区", developed=True,
         price=[("sina_gi", "SX5E")], note="欧元区蓝筹50家（无PE源）"),
    dict(id="AEX", name="荷兰AEX", region="欧洲", country="荷兰", developed=True,
         price=[("sina_gi", "AEX")], note="荷兰蓝筹25家（无PE源）"),
    dict(id="IBEX", name="西班牙IBEX35", region="欧洲", country="西班牙", developed=True,
         price=[("sina_gi", "IBEX")], note="西班牙蓝筹35家（无PE源）"),
    dict(id="MIB", name="意大利富时MIB", region="欧洲", country="意大利", developed=True,
         price=[("sina_gi", "FTSEMIB")], note="意大利蓝筹40家（无PE源）"),

    # ------------------------------------------------------------- 亚太其他
    dict(id="N225", name="日经225", region="亚太", country="日本", developed=True,
         price=[("sina_gi", "NKY")], note="日本大盘225家（无PE源）"),
    dict(id="KS11", name="韩国KOSPI", region="亚太", country="韩国", developed=True,
         price=[("sina_gi", "KOSPI")], note="韩国综合（无PE源）"),
    dict(id="AS51", name="澳洲标普200", region="亚太", country="澳大利亚", developed=True,
         price=[("sina_gi", "AS51")], note="澳洲大盘200家（无PE源）"),
    dict(id="TWII", name="台湾加权指数", region="亚太", country="中国台湾", developed=True,
         price=[("sina_gi", "TWJQ")], note="台湾加权（无PE源）"),
    dict(id="935600", name="MSCI印度", region="亚太", country="印度", developed=False,
         danjuan="935600", price=_etf("INDA"),
         price_note="ETF代理：INDA（iShares MSCI印度ETF，跟踪同一指数）",
         note="印度市场代表（价格以 INDA ETF 代理）"),
]

BY_ID = {x["id"]: x for x in INDICES}


def by_id(index_id: str):
    return BY_ID.get(index_id)


def developed() -> list[dict]:
    return [x for x in INDICES if x.get("developed")]


def region_order(region: str) -> int:
    try:
        return REGIONS.index(region)
    except ValueError:
        return len(REGIONS)


def sort_key(ix: dict):
    return (region_order(ix.get("region", "")), ix["name"])
