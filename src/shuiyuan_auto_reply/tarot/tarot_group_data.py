import re
from abc import abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Type


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
    if key in _global_image_dict.keys():
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
            f"{result.img_url}\n"
            "[/details]"
        )

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {}

    @classmethod
    def match_score(cls, question: str) -> int:
        """
        Calculate the match score for the question based on keywords.

        :param question: The question to match against the keywords.
        :return: The match score, which is the count of keywords found in the question.
        """
        question_lower = question.lower()
        score = 0.0
        for keyword, weight in cls.get_keywords().items():
            if re.search(keyword, question_lower) is not None:
                score = max(score, weight)
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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "过去": 0.4,
            "现在": 0.4,
            "未来": 0.4,
            "时间": 0.4,
            "时候": 0.4,
            "发展": 0.4,
            "变化": 0.4,
            "历程": 0.4,
            "趋势": 0.4,
            "年": 0.2,
            "月": 0.2,
            "周": 0.2,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "是否": 1.0,
            "能否": 1.0,
            "是不是": 1.0,
            "要不要": 1.0,
            "会不会": 1.0,
            "能不能": 1.0,
            "对不对": 1.0,
            "吗|嘛": 0.5,
            r"应该.*(?:吗|嘛|不)": 1.0,
            r"可以.*(?:吗|嘛|不)": 1.0,
            r"是.*(?:吗|嘛|不)": 1.0,
            r"要.*(?:吗|嘛|不)": 1.0,
            r"会.*(?:吗|嘛|不)": 1.0,
            r"能.*(?:吗|嘛|不)": 1.0,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "为什么": 0.8,
            "为啥": 0.8,
            "原因": 0.8,
            "分析": 0.5,
            "状况": 0.5,
            "情况": 0.5,
            "背景": 0.3,
            "怎么": 0.8,
            "如何": 0.8,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "问题": 0.4,
            "困难": 0.8,
            "挑战": 0.8,
            "阻碍": 0.8,
            "麻烦": 0.8,
            "障碍": 0.8,
            "解决": 0.4,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "恋爱": 0.9,
            "感情": 0.9,
            "爱情": 0.9,
            "男友": 0.9,
            "女友": 0.9,
            "喜欢": 0.9,
            "暗恋": 0.9,
            "表白": 0.9,
            "恋人": 0.9,
            "他": 0.2,
            "她": 0.2,
            "鹊": 0.6,
            "533": 0.6,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "经历": 0.6,
            "处境": 0.6,
            "运势": 0.6,
            "自己": 0.6,
            "性格": 0.6,
            "内心": 0.6,
            "想法": 0.6,
            "心理": 0.6,
            "个性": 0.6,
            "特点": 0.6,
            "自我": 0.6,
            "什么": 0.8,
            r"我会.*": 1.0,
            r"我想.*": 1.0,
            r"我能.*": 1.0,
            r"我应该.*": 1.0,
            r"我可以.*": 1.0,
        }


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
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "恋爱": 0.9,
            "感情": 0.9,
            "爱情": 0.9,
            "男友": 0.9,
            "女友": 0.9,
            "喜欢": 0.9,
            "暗恋": 0.9,
            "表白": 0.9,
            "恋人": 0.9,
            "他": 0.2,
            "她": 0.2,
            "鹊": 0.6,
            "533": 0.6,
        }


class SingleCardGuidanceGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "单牌指引",
            "该牌阵由1张牌组成，适合快速确认当下最需要关注的核心信息。",
        )
        self.tarot_results = []
        self.card_count = 1

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"
        text += "核心指引：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路：单牌不做复杂推演，重点说明这张牌对当前问题最直接的提醒、"
            "可采取的行动，以及需要避免的误区。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "单牌": 1.0,
            "指引": 0.8,
            "建议": 0.7,
            "提醒": 0.7,
            "今天": 0.7,
            "今日": 0.7,
            "此刻": 0.6,
            "快速": 0.5,
            "抽一张": 1.0,
            "一张": 0.8,
        }


class ChoiceTarotGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "二择一",
            "该牌阵由5张牌组成，适合在两个选项之间做比较，"
            "分别代表选项A的发展、选项A的风险、选项B的发展、选项B的风险和内在取舍。",
        )
        self.tarot_results = []
        self.card_count = 5

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "选项A的发展：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "选项A的风险：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "选项B的发展：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "选项B的风险：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "内在取舍：\n"
        text += f"{self._get_card_text(self.tarot_results[4])}\n\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路：分别比较A、B两个路径的机会与风险，最后用第五张牌总结问卜者真正重视的价值。"
            "不要直接替问卜者做决定，而是给出判断依据。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "二择一": 1.0,
            "选择": 0.9,
            "选哪个": 1.0,
            "哪个": 0.8,
            "还是": 0.8,
            "或者": 0.8,
            "方案": 0.7,
            "比较": 0.7,
            "取舍": 0.8,
            "决定": 0.8,
            "纠结": 0.8,
        }


class FiveElementsGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "五元素",
            "该牌阵由5张牌组成，从火、水、风、土和中心能量五个角度分析问题的动力、情绪、思路、现实基础和核心平衡。",
        )
        self.tarot_results = []
        self.card_count = 5

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "火元素（行动与动力）：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "水元素（情绪与关系）：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "风元素（思路与沟通）：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "土元素（资源与现实）：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "中心能量（整体平衡）：\n"
        text += f"{self._get_card_text(self.tarot_results[4])}\n\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路：按行动、情绪、思路、现实资源和整体平衡五个维度分析，"
            "指出哪一类能量过强或不足，并给出调整建议。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "五元素": 1.0,
            "元素": 0.8,
            "平衡": 0.8,
            "整体": 0.6,
            "综合": 0.6,
            "状态": 0.5,
            "能量": 0.7,
            "资源": 0.5,
        }


class HorseshoeGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "马蹄牌阵",
            "该牌阵由7张牌组成，适合分析较复杂的处境，分别代表过去、现在、隐藏影响、阻碍、外部影响、建议和结果。",
        )
        self.tarot_results = []
        self.card_count = 7

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "过去影响：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "当前状态：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "隐藏影响：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "主要阻碍：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "外部影响：\n"
        text += f"{self._get_card_text(self.tarot_results[4])}\n"
        text += "建议行动：\n"
        text += f"{self._get_card_text(self.tarot_results[5])}\n"
        text += "可能结果：\n"
        text += f"{self._get_card_text(self.tarot_results[6])}\n\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路：先说明过去与现在如何形成当前局面，再区分隐藏因素、阻碍和外部影响，"
            "最后结合建议牌给出通向结果牌的行动路径。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "马蹄": 1.0,
            "复杂": 0.8,
            "局面": 0.7,
            "处境": 0.7,
            "隐藏": 0.8,
            "影响": 0.6,
            "外部": 0.6,
            "阻碍": 0.7,
            "长期": 0.5,
        }


class CelticCrossGroup(BaseTarotGroup):
    def __init__(self):
        super().__init__(
            "凯尔特十字",
            "该牌阵由10张牌组成，适合深入分析复杂或长期问题，覆盖现状、挑战、意识、潜意识、过去、未来、自我、环境、希望恐惧和结果。",
        )
        self.tarot_results = []
        self.card_count = 10

    def __str__(self) -> str:
        text = self.base_info()
        text += "抽牌结果如下：\n\n"

        text += "现状：\n"
        text += f"{self._get_card_text(self.tarot_results[0])}\n"
        text += "挑战：\n"
        text += f"{self._get_card_text(self.tarot_results[1])}\n"
        text += "显意识目标：\n"
        text += f"{self._get_card_text(self.tarot_results[2])}\n"
        text += "潜意识根基：\n"
        text += f"{self._get_card_text(self.tarot_results[3])}\n"
        text += "过去影响：\n"
        text += f"{self._get_card_text(self.tarot_results[4])}\n"
        text += "近期未来：\n"
        text += f"{self._get_card_text(self.tarot_results[5])}\n"
        text += "自我态度：\n"
        text += f"{self._get_card_text(self.tarot_results[6])}\n"
        text += "外部环境：\n"
        text += f"{self._get_card_text(self.tarot_results[7])}\n"
        text += "希望与恐惧：\n"
        text += f"{self._get_card_text(self.tarot_results[8])}\n"
        text += "最终结果：\n"
        text += f"{self._get_card_text(self.tarot_results[9])}\n\n"

        return text

    def query_prompt(self):
        text = str(self)
        text += (
            "解读思路：凯尔特十字需要先读中心两张牌的现状与挑战，再用意识/潜意识、过去/未来、"
            "自我/环境三组关系交叉验证，最后谨慎总结希望恐惧与结果。"
        )
        return text

    @classmethod
    def get_keywords(cls) -> Dict[str, float]:
        return {
            "凯尔特": 1.0,
            "十字": 0.8,
            "深入": 0.8,
            "详细": 0.8,
            "全面": 0.8,
            "长期": 0.7,
            "复杂": 0.8,
            "大事": 0.7,
            "人生": 0.5,
            "事业": 0.6,
            "未来规划": 0.7,
        }


tarot_groups: List[Type[BaseTarotGroup]] = [
    TimeTarotGroup,
    YesOrNoGroup,
    SacredTriangleGroup,
    DiamondExpansionGroup,
    LoverPyramidGroup,
    SelfExplorationGroup,
    GypsyCrossGroup,
    SingleCardGuidanceGroup,
    ChoiceTarotGroup,
    FiveElementsGroup,
    HorseshoeGroup,
    CelticCrossGroup,
]
