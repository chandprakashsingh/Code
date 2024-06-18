from custom_exceptions import NoPositionsError, InvalidTokens, InvalidSolanaAddress
import requests
from decimal import Decimal
from typing import List, Dict, NamedTuple, Union
from config import Config
from solders.pubkey import Pubkey


# Named tuple for PriceInfo
class PriceInfo(NamedTuple):
    price: Decimal
    liquidity: Decimal


# Placeholder for the TokenOverview type
TokenOverview = Dict[str, Union[float, str]]


# Utility function to validate Solana address
def is_solana_address(input_string: str) -> bool:
    try:
        Pubkey.from_string(input_string)
        return True
    except:
        return False


class BirdEyeClient:
    """
    Handler class to assist with all calls to BirdEye API
    """

    @property
    def _headers(self):
        return {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": Config.BIRDEYE_API_KEY
        }

    def _make_api_call(self, method: str, query_url: str, *args, **kwargs) -> requests.Response:
        if method.upper() == "GET":
            query_method = requests.get
        elif method.upper() == "POST":
            query_method = requests.post
        else:
            raise ValueError(f'Unrecognized method "{method}" passed for query - {query_url}')

        resp = query_method(query_url, *args, headers=self._headers, **kwargs)
        return resp

    def fetch_prices(self, token_addresses: List[str]) -> Dict[str, PriceInfo]:
        """
        For a list of tokens fetches their prices via multi-price API ensuring each token has a price

        Args:
            token_addresses (List[str]): A list of tokens for which to fetch prices

        Returns:
            Dict[str, PriceInfo]: Mapping of token to a named tuple PriceInfo with price and liquidity

        Raises:
            NoPositionsError: Raise if no tokens are provided
            InvalidToken: Raised if the API call was unsuccessful
        """
        if not token_addresses:
            raise NoPositionsError("No tokens provided")

        addresses = ",".join(token_addresses)
        url = f"{Config.BASE_URL}/defi/multi_price?list_address={addresses}"

        response = self._make_api_call("GET", url)

        if response.status_code != 200:
            raise InvalidTokens("API call was unsuccessful")

        data = response.json()

        prices = {}
        for token in token_addresses:
            token_data = data['data'].get(token)
            if token_data:
                prices[token] = PriceInfo(
                    price=Decimal(token_data['value']),
                    liquidity=Decimal(token_data['priceChange24h'])
                )
            else:
                prices[token] = PriceInfo(
                    price=Decimal('0'),
                    liquidity=Decimal('0')
                )
        print(prices)
    def fetch_token_overview(self, address: str) -> TokenOverview:
        """
        For a token fetches their overview
        via multi-price API ensuring each token has a price

        Args:
            address (str): A token address for which to fetch overview

        Returns:
            TokenOverview: Overview with a lot of token information

        Raises:
            InvalidSolanaAddress: Raise if invalid Solana address is passed
            InvalidToken: Raised if the API call was unsuccessful
        """

        if not is_solana_address(address):
            raise InvalidSolanaAddress(f"Invalid Solana address: {address}")


        url = f'https://public-api.birdeye.so/defi/token_overview?address={address}'
        response = self._make_api_call("GET", url)

        if response.status_code == 401:
            raise InvalidTokens({"CODE": 401, "message": "Token is not Authorized"})
        if response.status_code != 200:
            raise InvalidTokens("API call was unsuccessful")

        data = response.json()
        token = data.get('data')
        return TokenOverview(
            price=Decimal(token.get('price', 0)),
            symbol=token.get('symbol', ''),
            decimals=int(token.get('decimals', 0)),
            lastTradeUnixTime=int(token.get('lastTradeUnixTime', 0)),
            liquidity=Decimal(token.get('liquidity', 0)),
            supply=Decimal(token.get('supply', 0))
        )


if __name__ == "__main__":
    client = BirdEyeClient()

    # Test fetch_prices
    token_addresses = [
        "WskzsKqEW3ZsmrhPAevfVZb6PuuLzWov9mJWZsfDePC",
        "2uvch6aviS6xE3yhWjVZnFrDw7skUtf6ubc7xYJEPpwj",
        "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "2LxZrcJJhzcAju1FBHuGvw929EVkX7R7Q8yA2cdp8q7b"
    ]

    try:
        prices = client.fetch_prices(token_addresses)
        print("Prices:", prices)
    except Exception as e:
        print("Error fetching prices:", e)

    for token_address in token_addresses:

        try:
            overview = client.fetch_token_overview(token_address)
            print("Token Overview:", overview)
        except Exception as e:
            print("Error fetching token overview:", e)
