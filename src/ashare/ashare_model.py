import json
import aiohttp
import datetime
import pandas as pd
from dacite import from_dict
from typing import List, Literal, Optional
from .objects import *


class AShareModel:
    """
    A model for managing Sina stock data.
    """

    def __init__(self):
        pass

    # Sina API for daily, weekly, monthly, and minute data
    @staticmethod
    async def _get_price_sina(
        code: str,
        end_date: Optional[str | datetime.date] = None,
        count: int = 10,
        frequency: Literal["1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"] = "60m",
    ) -> pd.DataFrame:
        # Convert frequency to Sina's expected format
        frequency = (
            frequency.replace("1d", "240m")
            .replace("1w", "1200m")
            .replace("1M", "7200m")
        )
        mcount = count
        ts = int(frequency[:-1]) if frequency[:-1].isdigit() else 1

        # Adjust count based on end_date for certain frequencies
        if (
            end_date is not None
            and end_date != ""
            and frequency in ["240m", "1200m", "7200m"]
        ):
            # Convert to datetime if not already
            end_date = (
                pd.to_datetime(end_date)
                if not isinstance(end_date, datetime.date)
                else end_date
            )
            # Determine the unit based on frequency
            unit = 4 if frequency == "1200m" else 29 if frequency == "7200m" else 1
            # Calculate the number of trading days between end_date and today
            count = count + (datetime.datetime.now() - end_date).days // unit

        # Concat the URL for Sina API
        sina_price_url = (
            "http://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
            f"/CN_MarketData.getKLineData?symbol={code}&scale={ts}&ma=5&datalen={count}"
        )

        # Let's try to fetch the data
        async with aiohttp.ClientSession() as session:
            # Let's parse the data we get from Sina
            dstr = json.loads(await (await session.get(sina_price_url)).content.read())
            df = pd.DataFrame(
                dstr, columns=["day", "open", "high", "low", "close", "volume"]
            )
            # Convert data types
            df[["open", "close", "high", "low", "volume"]] = df[
                ["open", "close", "high", "low", "volume"]
            ].astype("float")

            # Set the date as the index
            df.day = pd.to_datetime(df.day)
            df.set_index(["day"], inplace=True)
            df.sort_index(ascending=False, inplace=True)
            df.index.name = "time"

            # For daily, weekly, monthly data, return the last 'mcount' rows
            if (
                end_date is not None
                and end_date != ""
                and frequency in ["240m", "1200m", "7200m"]
            ):
                return df[df.index <= end_date][:mcount]

            # For minute-level data, return the data as is
            return df

    # Tencent API for minute-level data
    @staticmethod
    async def _get_price_min_tx(
        code: str,
        end_date: Optional[str | datetime.date] = None,
        count: int = 10,
        frequency: Literal["1m", "5m", "15m", "30m", "60m"] = "1m",
    ) -> pd.DataFrame:
        # Convert frequency to integer minutes
        ts = int(frequency[:-1]) if frequency[:-1].isdigit() else 1
        # Adjust end_date format if provided
        if end_date is not None and end_date != "":
            end_date = (
                end_date.strftime("%Y-%m-%d")
                if isinstance(end_date, datetime.date)
                else end_date.split(" ")[0]
            )

        # Concat the URL for Tencent API
        tencent_price_url = (
            "http://ifzq.gtimg.cn/appstock/app/kline/mkline"
            f"?param={code},m{ts},,{count}"
        )

        # Let's try to fetch the data
        async with aiohttp.ClientSession() as session:
            # Let's parse the data we get from Tencent
            st = json.loads(await (await session.get(tencent_price_url)).content.read())
            buf = st["data"][code]["m" + str(ts)]

            # Only these columns are needed
            df = pd.DataFrame(
                buf,
                columns=["time", "open", "close", "high", "low", "volume", "n1", "n2"],
            )

            # Convert data types
            df = df[["time", "open", "close", "high", "low", "volume"]]
            df.iloc[:, 1:] = df.iloc[:, 1:].astype("float")

            # Set the date as the index
            df.time = pd.to_datetime(df.time)
            df.set_index(["time"], inplace=True)
            df.sort_index(ascending=False, inplace=True)

            # Update the last close price to the real-time price
            df.loc[df.index[0], "close"] = float(st["data"][code]["qt"][code][3])
            return df

    # The all-in-one method to get stock prices
    @staticmethod
    async def _get_price(
        code: str,
        end_date: Optional[str | datetime.date] = None,
        count: int = 10,
        frequency: Literal["1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M"] = "1d",
    ) -> pd.DataFrame:
        # For compatibility with other interfaces, convert code to xcode
        xcode = code.replace(".XSHG", "").replace(".XSHE", "")
        if "XSHG" in code or "XSHE" in code:
            xcode = ("sh" if "XSHG" in code else "sz") + xcode
        else:
            xcode = code

        # For daily, weekly, and monthly data, use Sina API
        if frequency in ["1d", "1w", "1M"]:
            return await AShareModel._get_price_sina(
                xcode,
                end_date=end_date,
                count=count,
                frequency=frequency,
            )

        # For minute-level data, use Tencent API primarily, with Sina as a fallback
        if frequency in [
            "1m",
            "5m",
            "15m",
            "30m",
            "60m",
        ]:
            # Only tencent supports 1-minute data
            if frequency in "1m":
                return await AShareModel._get_price_min_tx(
                    xcode,
                    end_date=end_date,
                    count=count,
                    frequency=frequency,
                )

            # For other minute-level data, use Sina API
            return await AShareModel._get_price_sina(
                xcode,
                end_date=end_date,
                count=count,
                frequency=frequency,
            )

        # Raise an error if the frequency is not supported
        raise ValueError(
            "Unsupported frequency. Supported frequencies are: "
            "1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M."
        )

    @staticmethod
    def _convert_to_stockdata(df: pd.DataFrame) -> List[StockData]:
        """
        Converts a DataFrame to a list of StockData instances.

        :param df: The DataFrame to convert.
        :return: A list of StockData instances.
        """
        return [
            from_dict(StockData, data)
            for data in df.reset_index().to_dict(orient="records")
        ]

    @staticmethod
    async def get_shanghai_index() -> List[StockData]:
        """
        Fetches the Shanghai index data from the Sina API.

        :return: StockData for today and yesterday.
        """
        return await AShareModel.get_stock_data("sh000001")

    @staticmethod
    async def get_shenzhen_index() -> List[StockData]:
        """
        Fetches the Shenzhen index data from the Sina API.

        :return: StockData for today and yesterday.
        """
        return await AShareModel.get_stock_data("sz399001")

    @staticmethod
    async def get_stock_data(code: str) -> List[StockData]:
        """
        Fetches stock data for a specific stock ID from the Sina API.

        :param code: The stock ID.
        :return: StockData for the specified stock ID.
        """
        return AShareModel._convert_to_stockdata(
            await AShareModel._get_price(
                code=code,
                frequency="1d",
                count=2,
            )
        )
