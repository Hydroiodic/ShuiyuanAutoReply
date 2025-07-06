import re
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional


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
    img_url: Optional[str] = None


_global_image_dict = {}


def get_image_from_cache(result: TarotResult) -> Optional[str]:
    """
    Get the image path from the global image cache based on the tarot result.

    :param result: The tarot result containing the card and its orientation.
    :return: The image url of the tarot card.
    """
    key = f"{result.card.name}_{'reversed' if result.is_reversed else 'upright'}"
    if key in _global_image_dict:
        return _global_image_dict[key]
    else:
        # If the image is not cached, return a placeholder or an empty string
        return None


def save_image_to_cache(result: TarotResult, image_url: str) -> None:
    """
    Save the image path to the global image cache based on the tarot result.

    :param result: The tarot result containing the card and its orientation.
    :param image_url: The image url of the tarot card.
    """
    key = f"{result.card.name}_{'reversed' if result.is_reversed else 'upright'}"
    _global_image_dict[key] = image_url


class BaseTarotGroup:
    def __init__(self, group_name: str, group_description: str):
        self.group_name = group_name
        self.group_description = group_description
        self.tarot_results = []

    @abstractmethod
    def __str__(self) -> str:
        pass

    @abstractmethod
    def query_prompt(self) -> str:
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

    def _get_card_text(self, result: TarotResult) -> str:
        """
        Get the representation text of the tarot card.

        :param result: The tarot result containing the card and its orientation.
        """
        if result.img_url is None:
            return self._get_card_name(result)

        # Image URL is not None, we should use "details" tag to embed the image
        return (
            f"[details={self._get_card_name(result)}]\n"
            f"![img]({result.img_url})\n"
            "[/details]"
        )

    @classmethod
    def get_keywords(cls) -> List[str]:
        return []

    @classmethod
    def match_score(cls, question: str) -> int:
        """
        Calculate the match score for the question based on keywords.

        :param question: The question to match against the keywords.
        :return: The match score, which is the count of keywords found in the question.
        """
        question_lower = question.lower()
        score = 0
        for keyword in cls.get_keywords():
            if re.search(keyword, question_lower) is not None:
                score += 1
        return score


class TimeTarotGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__("时间牌阵", "该牌阵由3张牌组成，分别代表过去、现在和未来。")
        self.tarot_results = []
        self.card_count = 3

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "过去：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "现在：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "未来：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "改变未来最好的时间在于过去，如果发现占卜的未来塔罗牌含义不理想，可以想想过去塔罗牌所表示的问题加以改正。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "过去",
            "现在",
            "未来",
            "时间",
            "时候",
            "发展",
            "变化",
            "历程",
            "趋势",
            "年",
            "月",
            "周",
        ]


class YesOrNoGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__("YesOrNo", "该牌阵由1张牌组成，代表问题的答案。")
        self.tarot_results = []
        self.card_count = 1

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"
        text += f"答案：\n{self._get_card_text(self.tarot_results[0])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "如果抽到的是正位塔罗牌，答案是肯定的；如果抽到的是逆位塔罗牌，答案是否定的。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "是否",
            "能否",
            "要不要",
            "会不会",
            "能不能",
            "了吗",
            r"应该.*吗",
            r"可以.*吗",
            r"要.*吗",
            r"会.*吗",
            r"能.*吗",
        ]


class SacredTriangleGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "圣三角",
            "该牌阵由3张牌组成，分别代表问题的原因、当前状况和结果。",
        )
        self.tarot_results = []
        self.card_count = 3

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "原因：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "当前状况：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "结果：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += "解读思路：三张牌解读时尽可能的形成逻辑链。"
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "为什么",
            "为啥",
            "原因",
            "分析",
            "状况",
            "情况",
            "背景",
            "怎么",
        ]


class DiamondExpansionGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "钻石展开法", "该牌阵由4张牌组成，分别代表现在、即将遇到的两个问题和结果。"
        )
        self.tarot_results = []
        self.card_count = 4

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "现在：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "问题1：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "问题2：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "结果：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "一般情况下二或三号塔罗牌正位表示做过头的事情，逆位表示哪些方面做的还不够好。"
            "这是占卜中泰极否来的思想。比如说，对某人好，但好过头反而造成坏结果，凡事都要适度。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "问题",
            "困难",
            "挑战",
            "阻碍",
            "麻烦",
            "障碍",
            "解决",
        ]


class LoverPyramidGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "恋人金字塔",
            "该牌阵由4张牌组成，适用于爱情主题，"
            "分别代表你的期望、恋人的期望、目前彼此的关系和未来彼此的关系。",
        )
        self.tarot_results = []
        self.card_count = 4

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "你的期望：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "恋人的期望：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "目前彼此的关系：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "未来彼此的关系：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "感情的发展由三号塔罗牌转变至四号塔罗牌，结合一号与二号塔罗牌，分析转变的原因，基本可以回答问卜者的感情问题。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "恋爱",
            "感情",
            "爱情",
            "男友",
            "女友",
            "喜欢",
            "暗恋",
            "表白",
            "恋人",
            "他",
            "她",
            "鹊",
            "533",
        ]


class SelfExplorationGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "自我探索",
            "该牌阵由4张牌组成，可以帮助你在某些处境中认清自己，"
            "分别代表你所处的状态、你的外在表现、你的内在想法和你的潜意识。",
        )
        self.tarot_results = []
        self.card_count = 4

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "你所处的状态：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "你的外在表现：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "你的内在想法：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "你的潜意识：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "一号塔罗牌表示的状态，比如焦虑，矛盾，迷惘，纠结，抑郁等等。"
            "二号塔罗牌是在说自己的外在表现与行为，比如动作，表情，行为。这反映了你要做的事。"
            "三号塔罗牌是在说你想在达到什么目的，或者期望事件发展到哪种程度。"
            "四号塔罗牌是在说你需要满足自己的哪些方面的原欲，比如说是知欲，食欲，性欲，物质欲等等。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "经历",
            "处境",
            "运势",
            "自己",
            "性格",
            "内心",
            "想法",
            "心理",
            "个性",
            "特点",
            "自我",
            r"我会.*吗",
            r"我想.*吗",
            r"我能.*吗",
            r"我应该.*吗",
            r"我可以.*吗",
        ]


class GypsyCrossGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "吉普赛十字",
            "该牌阵由5张牌组成，适用于爱情主题，"
            "分别代表对方的想法、你的想法、相处中存在的问题、二人目前的人文环境和二人关系发展的结果。",
        )
        self.tarot_results = []
        self.card_count = 5

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "对方的想法：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "你的想法：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "相处中存在的问题：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "二人目前的人文环境：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "二人关系发展的结果：\n"
        text += f"{self._get_card_text(self.tarot_results[4])}\n"
        text += "\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路："
            "一般情况下，三号塔罗牌如果是正位需要将正位塔罗牌所表示的含义减弱一些，如果是逆位，则是你需要你改正的问题。"
            "在二人相处中太在乎对方与太放任对方都是不可取的。"
            "四号塔罗牌所表示的是二人所处的大环境对爱情的发展是否有促进的作用，这里的大环境包括双方的家庭，双方的事业，时间与空间。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> List[str]:
        return [
            "恋爱",
            "感情",
            "爱情",
            "男友",
            "女友",
            "喜欢",
            "暗恋",
            "表白",
            "恋人",
            "他",
            "她",
            "鹊",
            "533",
        ]


tarot_groups = [
    TimeTarotGroup,
    YesOrNoGroup,
    SacredTriangleGroup,
    DiamondExpansionGroup,
    LoverPyramidGroup,
    SelfExplorationGroup,
    GypsyCrossGroup,
]
