import time
import aiohttp
import asyncio
import logging
import traceback
from PIL import Image
from typing import Optional, List
from shuiyuan.shuiyuan_model import ShuiyuanModel
from shuiyuan.topic_model import BaseTopicModel
from ashare.ashare_model import AShareModel
from ashare.objects import StockData

_auto_reply_tag = "<!-- 来自南瓜的自动回复 -->"


class StockTopicModel(BaseTopicModel):
    """
    A class to represent a topic model.
    """

    def __init__(self, model: ShuiyuanModel, topic_id: int):
        """
        Initialize the TopicModel with a ShuiyuanModel instance.

        :param model: An instance of ShuiyuanModel.
        :param topic_id: The ID of the topic to be managed.
        """
        super().__init__(model, topic_id)
        self.ashare_model = AShareModel()

    async def _download_upload_and_get_image_url(self, code: str) -> Optional[str]:
        """
        Upload an stock image and return its URL.
        NOTE: we do not check if gid is valid or not.

        :param code: The ID of the stock image to be uploaded.
        :return: The URL of the uploaded image.
        """
        # Download the image from the URL
        stock_min_url = f"http://image.sinajs.cn/newchart/min/n/{code}.gif"
        tmp_gif = f"stock_images/{code}.gif"
        tmp_jpg = f"stock_images/{code}.jpg"
        async with aiohttp.ClientSession() as session:
            async with session.get(stock_min_url) as resp:
                # Check if the response is OK
                if resp.status != 200:
                    logging.warning(f"Network error for {code}, status={resp.status}")
                    return None
                # Read the response data and save it to a temporary file
                data = await resp.read()
                if not data:
                    logging.warning(f"Stock image data for {code} is empty.")
                    return None
                with open(tmp_gif, "wb") as f:
                    f.write(data)

        # Convert the GIF to JPG
        img = Image.open(tmp_gif)
        rgb = img.convert("RGB")
        rgb.save(tmp_jpg, "JPEG")

        # Upload the image and return the URL of the uploaded image
        return (await self.model.upload_image(tmp_jpg)).short_url

    @staticmethod
    def _colorize_string(text: str, color: str) -> str:
        """
        Colorize a string with the given color.

        :param text: The text to be colorized.
        :param color: The color to be used.
        :return: A string with the color applied.
        """
        return f"[color={color}]{text}[/color]"

    @staticmethod
    def _format_stock_data(data: List[StockData]) -> str:
        """
        Format the StockData into a string.

        :param data: An list of StockData (length should be 2).
        :return: A formatted string containing the data details.
        """
        # Check if the data is valid
        if not isinstance(data, list) or len(data) != 2:
            raise ValueError("Data must be a list of two StockData objects.")

        # Format the stock volume into a readable string
        formatted_volume = f"{int(float(data[0].volume)):,}".replace(",", " ")

        def _get_data_color(v: float) -> str:
            return "green" if v < float(data[1].close) else "red"

        now_color, open_color, high_color, low_color = (
            _get_data_color(float(data[0].close)),
            _get_data_color(float(data[0].open)),
            _get_data_color(float(data[0].high)),
            _get_data_color(float(data[0].low)),
        )

        return (
            f"当前价格：{StockTopicModel._colorize_string(data[0].close, now_color)}\n"
            f"涨幅：{StockTopicModel._colorize_string(
                f'{(data[0].close / data[1].close - 1) * 100:.2f}%', now_color
            )}\n"
            f"开盘价：{StockTopicModel._colorize_string(data[0].open, open_color)}\n"
            f"最高价：{StockTopicModel._colorize_string(data[0].high, high_color)}\n"
            f"最低价：{StockTopicModel._colorize_string(data[0].low, low_color)}\n"
            f"成交量：{formatted_volume}\n"
        )

    async def _stock_condition(self, raw: str) -> Optional[str]:
        """
        Check if the raw content of a post contains the string "A股".

        :param raw: The raw content of the post.
        :return: A string to reply with if the condition is met, otherwise None.
        """
        # Check the format of the post
        raw = raw.replace(" ", "").replace("\n", "").lower()
        if "【A股】".lower() not in raw:
            return None

        # Check the correctness of the stock code
        stock_code = raw.replace("【A股】".lower(), "").strip()[:8]
        if (
            len(stock_code) != 8
            or (not stock_code.startswith("sh") and not stock_code.startswith("sz"))
            or not stock_code[2:].isdigit()
        ):
            return (
                "股票代码格式错误，请使用“【A股】+股票代码”的格式，例如：【A股】sz000001。\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )

        # First, let's get the min chart image for the stock
        try:
            image_url = await self._download_upload_and_get_image_url(stock_code)
        except Exception as e:
            logging.error(
                f"Failed to download or upload stock image for {stock_code}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return (
                "抱歉，南瓜Bot遇到了一个错误，暂时无法获取股票数据，请稍后再试。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )

        # If the image URL is None, which means the stock code is invalid
        # or the image could not be downloaded, we should return an error message
        if image_url is None:
            return (
                "未找到该股票或无法获取到分时图，请检查股票代码是否正确。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )

        # Let's arrange the text to reply
        image_text = f"[details=分时图]\n![分时图]({image_url})\n[/details]\n"

        try:
            # Get the stock data from the AShareModel (Sina or Tencent API)
            stock_data = await self.ashare_model.get_stock_data(stock_code)
            return (
                f"{StockTopicModel._format_stock_data(stock_data)}\n"
                f"{image_text}\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}\n"
                f"---\n[right]来自南瓜Bot自动获取数据[/right]\n"
            )
        except Exception as e:
            logging.error(
                f"Failed to get stock data for {stock_code}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            return (
                "南瓜Bot无法获取到股票数据，仅展示分时图。\n\n"
                f"{image_text}\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}\n"
                f"---\n[right]来自南瓜Bot自动获取数据[/right]\n"
            )

    async def _new_post_routine(self, post_id: int) -> None:
        """
        A routine to handle new posts in the topic.
        NOTE: no exception should be raised in this method.

        :param post_id: The ID of the new post.
        :return: None
        """

        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # First let's try to get the post details
            post_details = await self.model.get_post_details(post_id)

            # If the member "raw" is not present, we should skip it
            if post_details.raw is None:
                logging.warning(f"Post {post_id} does not have raw content, skipping.")
                return

            # If the post is an auto-reply, we should skip it
            if _auto_reply_tag in post_details.raw:
                return

            # OK, check the content of the post
            # If the post contains "A股", we will reply with the stock data
            text = await self._stock_condition(post_details.raw)
        except Exception as e:
            # If we failed to get the post details or any other error occurred
            logging.error(
                f"Failed to get post details for {post_id}, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            # We should reply to the post with an error message
            text = (
                "抱歉，南瓜Bot遇到了一个错误，暂时无法处理您的请求，请稍后再试。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"{_auto_reply_tag}"
            )
        finally:
            if text is not None:
                await self.model.reply_to_post(
                    text,
                    self.topic_id,
                    post_details.post_number,
                )

    async def _daily_routine(self) -> None:
        """
        A routine to handle a daily task.
        NOTE: no exception should be raised in this method.

        :return: None
        """
        # This is the text to reply to the post
        text: Optional[str] = None

        try:
            # Get the two index stock data here
            shanghai_index, shenzhen_index = await asyncio.gather(
                self.ashare_model.get_shanghai_index(),
                self.ashare_model.get_shenzhen_index(),
            )

            # Let's arrange the text to reply
            text = (
                f"**当前时间**(GMT+8)：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n\n"
                "**上证指数**\n"
                f"{StockTopicModel._format_stock_data(shanghai_index)}\n"
                "**深证成指**\n"
                f"{StockTopicModel._format_stock_data(shenzhen_index)}\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
                f"---\n[right]来自南瓜Bot自动获取数据[/right]\n"
            )
        except Exception as e:
            # If we failed to get the stock data or any other error occurred
            logging.error(
                f"Failed to get stock data, "
                f"traceback is as follows:\n{traceback.format_exc()}"
            )
            # We should reply to the post with an error message
            text = (
                "抱歉，南瓜bot遇到了一个错误，暂时无法获取到大盘数据，请稍后再试。\n\n"
                f"<!-- {self._generate_random_string(20)} -->\n"
            )
        finally:
            if text is not None:
                await self.model.reply_to_post(text, self.topic_id)
