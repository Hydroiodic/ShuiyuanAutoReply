import os
import aiohttp
from dacite import from_dict
from typing import Literal, Optional
from .objects import *

if not os.getenv("JUHE_API_KEY"):
    raise ValueError("Please set the JUHE_API_KEY environment variable.")


class JuheModel:
    """
    A model for managing Juhe API interactions.
    """

    def __init__(self):
        self.api_url = "http://web.juhe.cn/finance/stock/hs"
        self.api_key = os.getenv("JUHE_API_KEY")

    async def _send_request(
        self,
        gid: Optional[str] = None,
        type: Optional[Literal[0, 1]] = None,
    ) -> dict:
        """
        Sends a request to the Juhe API to fetch stock data.

        :param gid: The stock ID (optional).
        :param type: The type of data to fetch (optional).
        :return: The JSON response from the API.
        """
        # At least one of gid or type must be provided
        if gid is None and type is None:
            raise ValueError("At least one of 'gid' or 'type' must be provided.")

        # Prepare the parameters for the API request
        params = {"key": self.api_key}
        if type is not None:
            params["type"] = type
        else:
            params["gid"] = gid

        # Send the request to the Juhe API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.api_url,
                params=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch data: {response.status}")
                return from_dict(
                    data_class=(IndexModel if type is not None else StockModel),
                    data=(await response.json())["result"],
                )

    async def get_shanghai_index(self) -> IndexModel:
        """
        Fetches the Shanghai index data from the Juhe API.

        :return: An IndexModel instance containing the index data.
        """
        return await self._send_request(type=0)

    async def get_shenzhen_index(self) -> IndexModel:
        """
        Fetches the Shenzhen index data from the Juhe API.

        :return: An IndexModel instance containing the index data.
        """
        return await self._send_request(type=1)

    async def get_stock_data(self, gid: str) -> StockModel:
        """
        Fetches stock data for a specific stock ID from the Juhe API.

        :param gid: The stock ID.
        :return: A StockModel instance containing the stock data.
        """
        return await self._send_request(gid=gid)
