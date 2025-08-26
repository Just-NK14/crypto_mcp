# server.py
from fastmcp import FastMCP
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
        COIN_LIST_CACHE = {coin['symbol'].lower(): coin['id'] for coin in coins}
        print(f"Successfully loaded and cached {len(COIN_LIST_CACHE)} cryptocurrencies.")
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not load coin list. The tool may not work. Details: {e}")

@mcp.tool
def get_crypto_price(symbol: str) -> dict:
    """
    Fetches the real-time price data of any cryptocurrency by its symbol.

    Args:
        symbol: The cryptocurrency symbol (e.g., "BTC", "ETH", "ADA").
    
    Returns:
        The entire JSON response from the API as a dictionary.
        Example: {"bitcoin": {"usd": 65000.00}}
    
    Raises:
        ValueError: If the symbol is not found or the coin list isn't loaded.
        RuntimeError: If the API call fails.
    """
    if not COIN_LIST_CACHE:
        raise ValueError("The coin list is not available. The server may have failed to start correctly.")

    # Find the coin's API ID from our cache (case-insensitive)
    coin_id = COIN_LIST_CACHE.get(symbol.lower())
    if not coin_id:
        raise ValueError(f"Cryptocurrency with symbol '{symbol}' not found.")

    # Construct the API URL to get the price
    api_url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
    
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        
        # Parse the JSON response into a dictionary
        data = response.json()
        
        # Directly return the entire dictionary
        return data
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"An error occurred while fetching the price: {e}")

if __name__ == "__main__":
    # Load the coin list into memory before starting the server
    load_coin_list()
    mcp.run(transport="stdio")