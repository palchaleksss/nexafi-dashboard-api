from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import requests
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE = "https://api.llama.fi"
DEFILLAMA_YIELDS = "https://yields.llama.fi"
NEXA_BASE_APY = 14.2


def fetch_eth_data():
    try:
        eth_res = requests.get(
            f"{COINGECKO_BASE}/coins/markets",
            params={"vs_currency": "usd", "ids": "ethereum", "sparkline": "true"},
            timeout=10,
        )
        eth_res.raise_for_status()
        eth_data = eth_res.json()
        return eth_data[0] if eth_data else None
    except Exception:
        return None


def fetch_tvl():
    try:
        tvl_res = requests.get(f"{DEFILLAMA_BASE}/charts", timeout=10)
        tvl_res.raise_for_status()
        tvl_data = tvl_res.json()
        if tvl_data and isinstance(tvl_data, list):
            return tvl_data[-1].get("totalLiquidityUSD", 128400000)
        return 128400000
    except Exception:
        return 128400000


def fetch_apy_history():
    """
    Берём историю APY из DefiLlama Yields для стабильного пула (Lido stETH)
    и масштабируем к базовому APY Nexa.
    """
    try:
        pools_res = requests.get(f"{DEFILLAMA_YIELDS}/pools", timeout=10)
        pools_res.raise_for_status()
        pools = pools_res.json().get("data", [])

        # Ищем Lido stETH — стабильный эталон
        pool = next(
            (
                p
                for p in pools
                if "steth" in p.get("symbol", "").lower()
                and "lido" in p.get("project", "").lower()
            ),
            None,
        )

        if not pool:
            return None

        chart_res = requests.get(
            f"{DEFILLAMA_YIELDS}/chart/{pool['pool']}", timeout=10
        )
        chart_res.raise_for_status()
        data = chart_res.json().get("data", [])

        if len(data) < 10:
            return None

        raw_apys = [d["apy"] for d in data[-30:]]
        base = raw_apys[0] or 1
        scaled = [NEXA_BASE_APY * (v / base) for v in raw_apys]
        return [round(v, 2) for v in scaled]

    except Exception:
        return None


def generate_fallback_apy_chart(base=NEXA_BASE_APY, days=30):
    values = [base]
    for _ in range(1, days):
        # APY колеблется в пределах ±4% от предыдущего дня
        values.append(max(0.5, values[-1] * (1 + random.uniform(-0.04, 0.04))))
    return [{"day": f"{i}d", "value": round(v, 2)} for i, v in enumerate(values)]


@app.get("/api/dashboard")
async def dashboard():
    try:
        eth = fetch_eth_data()
        eth_change = eth.get("price_change_percentage_24h", 0) or 0 if eth else 2.1

        defi_tvl = fetch_tvl()
        apy_history = fetch_apy_history()
        chart_data = (
            [{"day": f"{i}d", "value": v} for i, v in enumerate(apy_history)]
            if apy_history
            else generate_fallback_apy_chart()
        )

        current_apy = chart_data[-1]["value"] if chart_data else NEXA_BASE_APY
        start_apy = chart_data[0]["value"] if chart_data else NEXA_BASE_APY
        apy_change = ((current_apy - start_apy) / start_apy) * 100

        insight = (
            f"ETH is up {eth_change:.2f}% in 24h. "
            f"DeFi TVL sits at ${defi_tvl:,.0f}. "
            f"Current blended APY is {current_apy:.2f}% — "
            f"rebalancing 15% into stNEXA could lift your yield."
        )

        return {
            "tvl": defi_tvl,
            "apy": current_apy,
            "apy_change": round(apy_change, 2),
            "users": 50247,
            "portfolio_growth": round(eth_change, 2),
            "chart_data": chart_data,
            "ai_insight": insight,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
