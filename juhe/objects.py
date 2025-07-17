from dataclasses import dataclass


@dataclass
class StockData:
    """
    A data class representing stock data.
    """

    gid: str
    increPer: str
    increase: str
    name: str
    todayStartPri: str
    yestodEndPri: str
    nowPri: str
    todayMax: str
    todayMin: str
    competitivePri: str
    reservePri: str
    traNumber: str
    traAmount: str
    buyOne: str
    buyOnePri: str
    buyTwo: str
    buyTwoPri: str
    buyThree: str
    buyThreePri: str
    buyFour: str
    buyFourPri: str
    buyFive: str
    buyFivePri: str
    sellOne: str
    sellOnePri: str
    sellTwo: str
    sellTwoPri: str
    sellThree: str
    sellThreePri: str
    sellFour: str
    sellFourPri: str
    sellFive: str
    sellFivePri: str
    date: str
    time: str


@dataclass
class DaPanData:
    """
    A data class representing DaPan data.
    """

    dot: str
    name: str
    nowPic: str
    rate: str
    traAmount: str
    traNumber: str


@dataclass
class GoPicture:
    """
    A data class representing the URLs for different stock charts.
    """

    minurl: str
    dayurl: str
    weekurl: str
    monthurl: str


@dataclass
class StockModel:
    """
    A model representing stock data.
    """

    data: StockData
    dapandata: DaPanData
    gopicture: GoPicture


@dataclass
class IndexModel:
    """
    A model representing index data.
    """

    dealNum: str
    dealPri: str
    highPri: str
    increPer: str
    increase: str
    lowpri: str
    name: str
    nowpri: str
    openPri: str
    time: str
    yesPri: str
