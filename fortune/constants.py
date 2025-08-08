import os
import skia
from typing import List
from dataclasses import dataclass


@dataclass
class ToDoData:
    to_do: str
    detail_true: str
    detail_false: str


to_do_list: List[ToDoData] = [
    ToDoData("刷B站", "承包一天笑点", "视频加载不出来"),
    ToDoData("和喜欢的人约会", "小鹿乱撞", "被放鸽子"),
    ToDoData("贴贴", "被夸可爱", "被嫌弃"),
    ToDoData("刷水源", "赶上爆帖直播", "被抬杠对线"),
    ToDoData("发鹊桥", "找到心仪对象", "鹊桥帖起爆"),
    ToDoData("开组会", "被老板夸赞", "“你做的什么东西”"),
    ToDoData("南体跑步", "身体倍棒", "体力不支"),
    ToDoData("去图书馆", "效率UpUp", "被占座"),
    ToDoData("写作业", "蒙的全对", "“这讲过吗？”"),
    ToDoData("打游戏", "“评分13.0”", "“评分3.0”"),
    ToDoData("摸鱼", "老板不在实验室", "“抓个正着”"),
    ToDoData("给crush发消息", "解锁热情回复", "已读不回"),
    ToDoData("熬夜", "灵感爆棚", "上火长痘"),
    ToDoData("翘课", "休息好最重要", "被老师点名"),
    ToDoData("购物", "“满200减20”", "发货Takes Forever"),
    ToDoData("食堂干饭", "阿姨手不抖了", "“猪太倔”"),
    ToDoData("健身", "被夸练得好", "累晕过去"),
    ToDoData("搞钱", "来财，来", "“别让这些数字因你而归零”"),
    ToDoData("吃麦麦", "偶遇帅哥", "麦旋风化了"),
]


too_lucky_not_to_do = ToDoData("诸事皆宜", "", "去做想做的事情吧")
too_unlucky_to_do = ToDoData("诸事不宜", "床上躺一天", "")

too_lucky = ["大吉"]
too_unlucky = ["大凶"]
lucky = ["小吉", "中吉"] + too_lucky
unlucky = ["凶", "小凶"] + too_unlucky
fortune_list = lucky + unlucky

# Importing Fonts
font_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")
noto_emoji = os.path.join(font_dir, "Noto_Color_Emoji", "NotoColorEmoji-Regular.ttf")
noto_regu = os.path.join(font_dir, "Noto_Sans_SC", "static", "NotoSansSC-Regular.ttf")
noto_bold = os.path.join(font_dir, "Noto_Sans_SC", "static", "NotoSansSC-Bold.ttf")

emoji_typeface = skia.Typeface.MakeFromFile(noto_emoji)
title_typeface = skia.Typeface.MakeFromFile(noto_bold)
fortune_typeface = skia.Typeface.MakeFromFile(noto_bold)
to_do_typeface = skia.Typeface.MakeFromFile(noto_regu)
to_do_typeface_bold = skia.Typeface.MakeFromFile(noto_bold)
detail_typeface = skia.Typeface.MakeFromFile(noto_regu)

emoji_size = 40
title_size = 40
fortune_size = 120
to_do_size = 32
detail_size = 24

emoji_font = skia.Font(emoji_typeface, emoji_size)
title_font = skia.Font(title_typeface, title_size)
fortune_font = skia.Font(fortune_typeface, fortune_size)
to_do_font = skia.Font(to_do_typeface, to_do_size)
to_do_font_bold = skia.Font(to_do_typeface_bold, to_do_size)
detail_font = skia.Font(detail_typeface, detail_size)

bg_size = (800, 550)

# Emoji regular expression
emoji_format = (
    "["
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map symbols
    "\U0001f1e0-\U0001f1ff"  # flags (iOS)
    "\U0001f700-\U0001f77f"  # alchemical symbols
    "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
    "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
    "\U0001f900-\U0001f9ff"  # Supplemental Symbols and Pictographs
    "\U0001fa00-\U0001fa6f"  # Chess Symbols
    "\U0001fa70-\U0001faff"  # Symbols and Pictographs Extended-A
    "\U00002600-\U000026ff"  # Miscellaneous Symbols
    "\U00002700-\U000027bf"  # Dingbats
    "\U0000fe00-\U0000fe0f"  # Variation Selectors
    "\U0001f170-\U0001f251"  # Enclosed Alphanumeric Supplement
    "]+"
)
