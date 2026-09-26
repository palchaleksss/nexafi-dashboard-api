from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFILLAMA_BASE = "https://api.llama.fi"


@app.get("/api/dashboard")
async def dashboard():
    try:
        eth_res = requests.get(
            f"{COINGECKO_BASE}/coins/markets",
            params={
                "vs_currency": "usd",
                "ids": "ethereum",
                "sparkline": "true"
            },
            timeout=10
        )
        eth_data = eth_res.json()

        tvl_res = requests.get(f"{DEFILLAMA_BASE}/charts", timeout=10)
        tvl_data = tvl_res.json()

        eth_change = eth_data[0]["price_change_percentage_24h"] if eth_data else 0
        sparkline = eth_data[0].get("sparkline_in_7d", {}).get("price", []) if eth_data else []
        defi_tvl = tvl_data[-1]["totalLiquidityUSD"] if tvl_data else 0

        chart_data = []
        if sparkline:
            step = max(1, len(sparkline) // 30)
            for i in range(0, len(sparkline), step):
                chart_data.append({
                    "day": f"{i}h",
                    "value": round(sparkline[i], 2)
                })
            chart_data = chart_data[:30]

        insight = (
            f"ETH is up {eth_change:.2f}% in 24h. "
            f"DeFi TVL sits at ${defi_tvl:,.0f}. "
            "Rebalancing 15% into stNEXA could lift your blended APY."
        )

        return {
            "tvl": defi_tvl,
            "apy": 14.2,
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
