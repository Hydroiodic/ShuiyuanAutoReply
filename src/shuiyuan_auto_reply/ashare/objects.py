import datetime
from dataclasses import dataclass


@dataclass
class StockData:
    """
    A data class representing stock data.
    """

    time: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: float
