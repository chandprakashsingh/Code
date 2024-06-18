"""
Client for DexScreener APIs
"""

from decimal import Decimal
from typing import Any

import requests

from clients.common import PriceInfo, TokenOverview
from custom_exceptions import InvalidSolanaAddress, InvalidTokens, NoPositionsError
from utils.helpers import is_solana_address
from constants import SOL_MINT


class DexScreenerClient:
    """
    Handler class to assist with all calls to DexScreener API
    """

    @staticmethod
    def _validate_token_address(token_address: str):
        """
        Validates the token address to be a valid Solana address.

        Args:
            token_address (str): Token address to validate.

        Returns:
            None: If the token address is valid.

        Raises:
            NoPositionsError: If the token address is empty.
            InvalidSolanaAddress: If the token address is not a valid Solana address.
        """
        try:
            if not token_address:
                raise NoPositionsError()

            if not is_solana_address(token_address):
                raise InvalidSolanaAddress(token_address)
  
        except Exception as e:
            raise InvalidSolanaAddress(token_address)


    def _validate_token_addresses(self, token_addresses: list[str]):
        """
        Validates token addresses to be a valid solana address

        Args:
            token_addresses (list[str]): Token addresses to validate

        Returns:
            None: If token addresses are valid

        Raises:
            NoPositionsError: If token addresses are empty
            InvalidSolanaAddress: If any token address is not a valid solana address
        """
        if not token_addresses:
            raise NoPositionsError("Token addresses list is empty")

        for address in token_addresses:
            self._validate_token_address(address)

    @staticmethod
    def _validate_response(resp: requests.Response):
        """
        Validates response from API to be 200

        Args:
            resp (requests.Response): Response from API

        Returns:
            None: If response is 200

        Raises:
            InvalidTokens: If response is not 200
        """
        if resp.status_code != 200:
            raise InvalidTokens()

    def _call_api(self, token_address: str) -> dict[str, Any]:
        """
        Calls DexScreener API for a single token

        Args:
            token_address (str): Token address for which to fetch data

        Returns:
            dict[str, Any]: JSON response from API

        Raises:
            InvalidTokens: If response is not 200
            NoPositionsError: If token address is empty
            InvalidSolanaAddress: If token address is not a valid solana address
        """
        self._validate_token_address(token_address)
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        response = requests.get(url)

        self._validate_response(response)

        return response.json()

    def _call_api_bulk(self, token_addresses: list[str]) -> dict[str, Any]:
        """
        Calls DexScreener API for multiple tokens

        Args:
            token_addresses (list[str]): Token addresses for which to fetch data

        Returns:
            dict[str, Any]: JSON response from API

        Raises:
            InvalidTokens: If response is not 200
            NoPositionsError: If token addresses are empty
            InvalidSolanaAddress: If any token address is not a valid solana address
        """
        if not token_addresses:
            raise NoPositionsError("Token addresses list is empty")

        responses = {}
        for address in token_addresses:
            try:
                self._validate_token_address(address)
                url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
                response = requests.get(url)
                self._validate_response(response)
                responses[address] = response.json()
            except (InvalidSolanaAddress, InvalidTokens) as e:
                # Log or handle specific errors as needed
                responses[address] = {"error": str(e)}

        return responses

    def fetch_prices_dex(self, token_addresses: list[str]) -> dict[str, PriceInfo[Decimal, Decimal]]:
        """
        For a list of tokens fetches their prices
        via multi API ensuring each token has a price

        Args:
            token_addresses (list[str]): A list of tokens for which to fetch prices

        Returns:
           dict[str, dict[Decimal, PriceInfo[str, Decimal]]: Mapping of token to a named tuple PriceInfo with price and liquidity in Decimal

        """

        self._validate_token_addresses(token_addresses)
        responses = self._call_api_bulk(token_addresses)
        prices = {}

        for address, token_data in responses.items():
            try:
                # Assuming token_data contains price and liquidity information
                if 'pairs' in token_data:
                    prices[address] = {}
                    for pair in token_data['pairs']:
                        try:
                            price = Decimal(pair.get('priceUsd', 0.0))
                            liquidity = Decimal(pair.get('liquidity', {}).get('usd', 0.0))
                            dex_id = pair.get('dexId')
                            prices[address][dex_id] = {}
                            symbol = pair.get('baseToken', {}).get('symbol')
                            prices[address][dex_id][symbol] = PriceInfo(value=price, liquidity=liquidity)
                        except (ValueError, TypeError):
                            if dex_id:
                                del prices[address][dex_id]

            except (ValueError, TypeError):
                # Handle if price or liquidity cannot be converted to Decimal
                if address in prices:
                    del prices[address]

        return prices


    def fetch_token_overview(self, address: str) -> TokenOverview:
        """
        For a token fetches their overview
        via Dex API ensuring each token has a price

        Args:
        address (str): A token address for which to fetch overview

        Returns:
        TokenOverview: Overview with a lot of token information I don't understand
        """
        self._validate_token_address(address)
        responses = self._call_api(address)
        token_overview = {}
        pairs = responses.get('pairs')

        if pairs:
            token_overview[address] = {}
            for pair in pairs:
                try:
                    price = Decimal(pair.get('priceUsd', 0.0))
                    symbol = pair.get('baseToken', {}).get('symbol')
                    liquidity = Decimal(pair.get('liquidity', {}).get('usd', 0.0))
                    decimals = "N/A"
                    lastTradeUnixTime = "N/A"
                    supply = "N/A"
                    dex_id = pair.get('dexId')
                    token_overview[address][dex_id] = {}
                    token_overview[address][dex_id][symbol] = TokenOverview(price=price, symbol=symbol, liquidity=liquidity,
                                                                            decimals=decimals, lastTradeUnixTime=lastTradeUnixTime,
                                                                            supply=supply)
                except (ValueError, TypeError):
                    if dex_id:
                        del token_overview[address][dex_id]
        else:
            return "Pairs Not Found"

        return token_overview

    @staticmethod
    def find_largest_pool_with_sol(token_pairs, address):
        max_entry = {}
        max_liquidity_usd = -1

        for entry in token_pairs:
            # Check if the baseToken address matches the specified address
            if entry.get("baseToken", {}).get("address") == address and entry["quoteToken"]["address"] == SOL_MINT:
                liquidity_usd = float(entry.get("liquidity", {}).get("usd", 0))
                if liquidity_usd > max_liquidity_usd:
                    max_liquidity_usd = liquidity_usd
                    max_entry = entry
        return max_entry


if __name__ == "__main__":
    token_addresses = [
        "WskzsKqEW3ZsmrhPAevfVZb6PuuLzWov9mJWZsfDePC",
        "2uvch6aviS6xE3yhWjVZnFrDw7skUtf6ubc7xYJEPpwj",
        "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "2LxZrcJJhzcAju1FBHuGvw929EVkX7R7Q8yA2cdp8q7b"
    ]
    client = DexScreenerClient()
    try:
        prices = client.fetch_prices_dex(token_addresses)
        print("Prices:", prices)
    except Exception as e:
        print("Error fetching prices:", e)

    for token_address in token_addresses:
        try:
            overview = client.fetch_token_overview(token_address)
            print("Token Overview:", overview)
        except Exception as e:
            print("Error fetching token overview:", e)