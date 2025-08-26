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
    with a professional line chart on a dark background.

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
        # Fetch coin details for logo and full name
        details = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}", timeout=5).json()
        logo_url = details.get('image', {}).get('large')
        coin_name = details.get('name', symbol.upper())

        # Fetch historical price data
        chart_data = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
            params={"vs_currency": "usd", "days": days}, timeout=10
        ).json()

        prices = chart_data.get('prices', [])
        if not prices:
            return f"No price data found for {symbol} for last {days} days."

        timestamps = [datetime.fromtimestamp(p[0]/1000) for p in prices]
        price_values = [p[1] for p in prices]

        # Find min and max points
        min_price = min(price_values)
        max_price = max(price_values)
        min_index = price_values.index(min_price)
        max_index = price_values.index(max_price)

        # Create line plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=price_values,
            mode='lines+markers',
            line=dict(color="#00cc96", width=1),
            marker=dict(size=2),
            name="Price",
            hovertemplate="%{x|%b %d, %Y}<br>Price: $%{y:,.2f}<extra></extra>"
        ))

        # Highlight min and max points
        fig.add_trace(go.Scatter(
            x=[timestamps[min_index], timestamps[max_index]],
            y=[min_price, max_price],
            mode='markers+text',
            marker=dict(color="red", size=5, symbol="circle"),
            text=[f"Min: ${min_price:,.2f}", f"Max: ${max_price:,.2f}"],
            textposition="top center",
            showlegend=False
        ))

        # Layout improvements with dark theme
        fig.update_layout(
            title=dict(
                text=f"Price History of {symbol.upper()}",
                x=0.5,
                xanchor='center',
                yanchor='top',
                font=dict(family="Arial", size=22, color="white")
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

        # Add logo in top-left
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
        return "Success! The plot has been displayed."

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Error fetching data: {e}")

if __name__ == "__main__":
    # Load the coin list into memory before starting the server
    load_coin_list()
    mcp.run(transport="stdio")
