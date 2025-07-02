from abc import abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass
class TarotCard:
    name: str
    T: str
    F: str


@dataclass
class TarotResult:
    card: TarotCard
    is_reversed: bool
    index: int


class BaseTarotGroup:
    def __init__(self, group_name: str, group_description: str):
        self.group_name = group_name
        self.group_description = group_description
        self.tarot_results = []

    @abstractmethod
    def __str__(self) -> str:
        pass

    def set_tarot_results(self, tarot_results: List[TarotResult]):
        """
        Set the tarot results for the group.
        :param tarot_results: A list of tarot results to set.
        """
        self.tarot_results = tarot_results

    def base_info(self) -> str:
        """
        Return the base information of the tarot group.
        """
        return f"此次选择的牌阵为：{self.group_name}，{self.group_description}\n\n"

    def _get_card_name(self, result: TarotResult) -> str:
        """
        Get the name of the tarot card.

        :param result: The tarot result containing the card and its orientation.
        """
        return f"{'逆位' if result.is_reversed else '正位'}{result.card.name}"


class TimeTarotGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__("时间牌阵", "该牌阵由3张牌组成，分别代表过去、现在和未来")
        self.tarot_results = []
        self.card_count = 3

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n"

        text += "过去："
        text += f"{self._get_card_name(self.tarot_results[0])}\n"
        text += "现在："
        text += f"{self._get_card_name(self.tarot_results[1])}\n"
        text += "未来："
        text += f"{self._get_card_name(self.tarot_results[2])}\n"
        text += "\n"

        return text


class YesOrNoGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__("YesOrNo牌阵", "该牌阵由1张牌组成，代表问题的答案")
        self.tarot_results = []
        self.card_count = 1

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n"
        text += f"答案：{self._get_card_name(self.tarot_results[0])}\n"
        text += "\n"

        return text


tarot_groups = [TimeTarotGroup, YesOrNoGroup]
