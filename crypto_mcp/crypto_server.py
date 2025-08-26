from fastmcp import FastMCP
from typing import Optional
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


if __name__ == "__main__":
    # Load the coin list into memory before starting the server
    load_coin_list()
    mcp.run(transport="stdio")
