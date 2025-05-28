import requests
import time
from graphics import send_text  # Assumes you render via image


# Shared function to fetch price data
def get_stock_info(ticker):
    url = f"https://api.nasdaq.com/api/quote/basic?&symbol={ticker}%7cstocks"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code <= 0:
            print(f"[HTTP Error] {ticker}: {response.status_code}")
            return None

        data = response.json()
        records = data.get("data", {}).get("records", [])
        if not records:
            print(f"[No Records] {ticker}")
            return None

        record = records[0]
        return {
            "ticker": ticker,
            "lastSale": record.get("lastSale", "$????"),
            "pctChange": record.get("pctChange", ""),
            "deltaIndicator": record.get("deltaIndicator", ""),
        }

    except Exception as e:
        print(f"[Exception] {ticker}: {e}")
        return None


# Single display for a given stock
def fetch_stock_price(ticker="NVDA"):
    stock = get_stock_info(ticker)
    if not stock:
        return

    yellow = (255, 221, 0)  # Bloomberg yellow
    white = (255, 255, 255)
    green = (0, 255, 0)
    red = (255, 0, 0)

    color = green if stock["deltaIndicator"] == "up" else red

    segments = [
        (stock["ticker"] + " ", yellow),
        (stock["pctChange"], color),
    ]
    send_text(segments)


# Cycle through a list of tickers
def cycle_through_stocks(stocks=[], delay=0.5, update_delay=30):
    if not stocks:
        print("No tickers provided.")
        return

    while True:
        # Fetch latest stock data
        stock_infos = []
        for ticker in stocks:
            info = get_stock_info(ticker)
            if info:
                stock_infos.append(info)

        # Display each stock in a loop
        start_time = time.time()
        while time.time() - start_time < update_delay:
            for stock in stock_infos:
                yellow = (255, 221, 0)
                white = (255, 255, 255)
                green = (0, 255, 0)
                red = (255, 0, 0)

                color = green if stock["deltaIndicator"] == "up" else red

                segments = [
                    (stock["ticker"] + " ", yellow),
                    (stock["pctChange"], color),
                ]

                send_text(segments)
                time.sleep(delay)


# Example usage
if __name__ == "__main__":
    # Single stock example
    # fetch_stock_price()

    # Or cycle through a list of stocks
    cycle_through_stocks(["AAPL", "TSLA", "NVDA"], delay=3, update_delay=30)
