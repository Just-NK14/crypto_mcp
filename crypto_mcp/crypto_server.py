from fastmcp import FastMCP
from typing import Optional
import plotly.graph_objects as go
from datetime import datetime
import time
import requests


mcp = FastMCP("Crypto Price Tool 🪙")

# A global cache to store the mapping of symbols to API IDs
COIN_LIST_CACHE = {}


def load_coin_list():
    """
    Fetches the list of all coins from the CoinGecko API and caches it.
    This function runs once when the server starts.
    """
    global COIN_LIST_CACHE
    try:
        url = "https://api.coingecko.com/api/v3/coins/list"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        coins = response.json()
        # Create a mapping from a lowercase symbol (e.g., "btc") to an ID (e.g., "bitcoin")
        COIN_LIST_CACHE = {coin['symbol'].lower(): coin['id']
                           for coin in coins}
        print(
            f"Successfully loaded and cached {len(COIN_LIST_CACHE)} cryptocurrencies.")
    except requests.exceptions.RequestException as e:
        print(
            f"Error: Could not load coin list. The tool may not work. Details: {e}")


@mcp.tool
def get_crypto_price(
    symbol: str,
    vs_currencies: str = "usd",
    include_market_cap: Optional[bool] = None,
    include_24hr_vol: Optional[bool] = None,
    include_24hr_change: Optional[bool] = None,
    include_last_updated_at: Optional[bool] = None
) -> dict:
    """
    Fetches the real-time price data of any cryptocurrency by its symbol.

    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC", "ETH", "ADA").
        vs_currencies: Comma-separated currencies to fetch (default: "usd").
        include_market_cap: Include market cap if True.
        include_24hr_vol: Include 24h volume if True.
        include_24hr_change: Include 24h % change if True.
        include_last_updated_at: Include last updated timestamp if True.

    Returns:
        dict: The entire JSON response from the API.
    """
    if not COIN_LIST_CACHE:
        raise ValueError(
            "The coin list is not available. The server may have failed to start correctly.")

    coin_id = COIN_LIST_CACHE.get(symbol.lower())
    if not coin_id:
        raise ValueError(f"Cryptocurrency with symbol '{symbol}' not found.")

    params = {
        "ids": coin_id,
        "vs_currencies": vs_currencies,
    }

    # Only add params if explicitly provided
    if include_market_cap is not None:
        params["include_market_cap"] = str(include_market_cap).lower()
    if include_24hr_vol is not None:
        params["include_24hr_vol"] = str(include_24hr_vol).lower()
    if include_24hr_change is not None:
        params["include_24hr_change"] = str(include_24hr_change).lower()
    if include_last_updated_at is not None:
        params["include_last_updated_at"] = str(
            include_last_updated_at).lower()

    api_url = "https://api.coingecko.com/api/v3/simple/price"
    response = requests.get(api_url, params=params)

    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch price data: {response.status_code}, {response.text}")

    return response.json()

@mcp.tool
def plot_crypto_price_history(symbol: str, days: int) -> str:
    """
    Fetches, plots, and displays the historical price of a cryptocurrency
    with an interactive toggle between line and candlestick chart.
    Candles gracefully fall back to aggregated OHLC when /ohlc doesn't support the 'days' value.

    Args:
        symbol: Cryptocurrency symbol (e.g., "BTC").
        days: Number of past days of historical data.

    Returns:
        Success message when plot is displayed.
    """
    if not COIN_LIST_CACHE:
        raise ValueError("Coin list is not loaded.")

    coin_id = COIN_LIST_CACHE.get(symbol.lower())
    if not coin_id:
        raise ValueError(f"Cryptocurrency '{symbol}' not found.")

    try:
        # Fetch coin details (logo, name)
        details = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}", timeout=5
        ).json()
        logo_url = details.get('image', {}).get('large')
        coin_name = details.get('name', symbol.upper())

        # Fetch line data (works for any days)
        chart_data = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days},
            timeout=10
        ).json()

        prices = chart_data.get('prices', [])
        if not prices:
            return f"No price data found for {symbol} for last {days} days."

        ts_line = [datetime.fromtimestamp(p[0] / 1000) for p in prices]
        val_line = [p[1] for p in prices]

        # Try OHLC endpoint first if 'days' supported; else aggregate from prices
        supported_ohlc_days = {1, 7, 14, 30, 90, 180, 365}
        have_real_ohlc = False
        ohlc_x, ohlc_o, ohlc_h, ohlc_l, ohlc_c = [], [], [], [], []

        if isinstance(days, int) and days in supported_ohlc_days:
            ohlc_resp = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc",
                params={"vs_currency": "usd", "days": days},
                timeout=10
            ).json()
            if isinstance(ohlc_resp, list) and ohlc_resp:
                have_real_ohlc = True
                ohlc_x = [datetime.fromtimestamp(p[0] / 1000) for p in ohlc_resp]
                ohlc_o = [p[1] for p in ohlc_resp]
                ohlc_h = [p[2] for p in ohlc_resp]
                ohlc_l = [p[3] for p in ohlc_resp]
                ohlc_c = [p[4] for p in ohlc_resp]

        if not have_real_ohlc:
            # Fallback: aggregate /market_chart prices into daily candles
            # Group by calendar day; open=first, high=max, low=min, close=last
            buckets = {}
            for t, price in zip(ts_line, val_line):
                day_key = datetime(t.year, t.month, t.day)
                if day_key not in buckets:
                    buckets[day_key] = {
                        "open": price, "high": price, "low": price, "close": price
                    }
                else:
                    b = buckets[day_key]
                    b["high"] = max(b["high"], price)
                    b["low"] = min(b["low"], price)
                    b["close"] = price

            # Sort by date
            sorted_days = sorted(buckets.keys())
            # If user asks for N days, keep at most last N daily buckets
            if isinstance(days, int) and len(sorted_days) > days:
                sorted_days = sorted_days[-days:]

            ohlc_x = sorted_days
            ohlc_o = [buckets[d]["open"] for d in sorted_days]
            ohlc_h = [buckets[d]["high"] for d in sorted_days]
            ohlc_l = [buckets[d]["low"] for d in sorted_days]
            ohlc_c = [buckets[d]["close"] for d in sorted_days]

            # If for some reason we couldn't build candles (e.g., only 1 point), just skip
            if len(ohlc_x) < 2:
                # We'll still show the line chart; candlestick toggle will be disabled visually (no data)
                pass

        # Build figure
        fig = go.Figure()

        # Line trace
        fig.add_trace(go.Scatter(
            x=ts_line,
            y=val_line,
            mode='lines',
            line=dict(color="#00cc96", width=1.5),
            name="Line Chart",
            hovertemplate="%{x|%b %d, %Y %H:%M}<br>Price: $%{y:,.2f}<extra></extra>",
            visible=True
        ))

        # Candlestick trace (only if we have 2+ candles)
        have_candles = len(ohlc_x) >= 2
        fig.add_trace(go.Candlestick(
            x=ohlc_x,
            open=ohlc_o,
            high=ohlc_h,
            low=ohlc_l,
            close=ohlc_c,
            name="Candlestick",
            visible=False if have_candles else False,
            hoverlabel=dict(namelength=-1)
        ))

        fig.update_layout(
            updatemenus=[
                dict(
                    type="buttons",
                    direction="down",
                    x=1.05, y=1,
                    buttons=list([
                        dict(
                            label="Line",
                            method="update",
                            args=[{"visible": [True, False]}],
                            args2=[{"visible": [True, False]}]  
                        ),
                        dict(
                            label="Candle" + ("" if have_candles else " (N/A)"),
                            method="update",
                            args=[{"visible": [False, True]}],
                            args2=[{"visible": [False, True]}]
                        ),
                    ]),
                    showactive=True,
                    bgcolor="grey",
                    bordercolor="black",
                    borderwidth=1,
                    font=dict(color="black", size=13)
                )
            ],
            title=dict(
                text=f"Price History of {coin_name} ({symbol.upper()})",
                x=0.5,
                font=dict(size=22, color="white")
            ),
            xaxis=dict(
                title="Date",
                showgrid=True,
                gridcolor='gray',
                tickangle=-45,
                showline=True,
                linewidth=1,
                linecolor='white',
                color='white'
            ),
            yaxis=dict(
                title="Price (USD)",
                showgrid=True,
                gridcolor='gray',
                tickformat="$,.2f",
                showline=True,
                linewidth=1,
                linecolor='white',
                color='white'
            ),
            template="plotly_dark",
            font=dict(family="Arial", size=12, color="white"),
            margin=dict(l=70, r=40, t=100, b=70)
        )

        # Logo in top-left
        if logo_url:
            fig.add_layout_image(
                dict(
                    source=logo_url,
                    xref="paper", yref="paper",
                    x=0, y=1,
                    sizex=0.08, sizey=0.08,
                    xanchor="left", yanchor="top",
                    layer="above"
                )
            )

        fig.show()
        return "Success! The plot with robust candlesticks has been displayed."

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching data: {e}")

@mcp.tool()
def get_top_gainers_losers(
    vs_currency="usd",
    top_n=5,
    category="both",
    per_page=250,
    page=1,
    price_change_period="24h"
):
    """
    Fetch top gainers and/or losers in the crypto market.

    Args:
        vs_currency (str): Currency to compare prices against (default "usd").
        top_n (int): Number of top gainers/losers to return (default 5).
        category (str): "gainers", "losers", or "both" (default "both").
        per_page (int): Number of coins to fetch per page from CoinGecko (default 250).
        page (int): Page number to fetch (default 1).
        price_change_period (str): Period for price change: "1h", "24h", "7d" (default "24h").

    Returns:
        dict: Contains requested data based on category.
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": page,
        "price_change_percentage": price_change_period
    }

    data = requests.get(url, params=params).json()

    # Ensure top_n doesn't exceed the fetched data length
    top_n = min(top_n, len(data))

    # Sort by chosen price change period
    key_name = f"price_change_percentage_{price_change_period}"
    sorted_data = sorted(data, key=lambda x: x.get(key_name, 0), reverse=True)

    gainers = sorted_data[:top_n]
    losers = sorted_data[-top_n:]

    def format_list(coin_list):
        return [
            {
                "name": c["name"],
                "symbol": c["symbol"],
                "price": c["current_price"],
                "change": round(c.get(key_name, 0), 2)
            }
            for c in coin_list
        ]

    if category == "gainers":
        return {"gainers": format_list(gainers)}
    elif category == "losers":
        return {"losers": format_list(losers[::-1])}  # biggest negative change first
    else:
        return {
            "gainers": format_list(gainers),
            "losers": format_list(losers[::-1])
        }

load_coin_list()
mcp.run(transport="stdio")