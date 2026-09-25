import asyncio
import os

import pytest

from shuiyuan_auto_reply.constants import settings
from shuiyuan_auto_reply.tarot.tarot_group_data import (
    LoverPyramidGroup,
    TarotCard,
    TarotResult,
    YesOrNoGroup,
    get_image_from_cache,
    save_image_to_cache,
    tarot_groups,
)
from shuiyuan_auto_reply.tarot.tarot_model import TarotModel


def _results(count):
    card = TarotCard(name="愚者", T="正位含义", F="逆位含义")
    return [TarotResult(card, i % 2 == 0, i + 1) for i in range(count)]


@pytest.mark.parametrize("group_class", tarot_groups)
def test_group_text_lists_every_position(group_class):
    group = group_class()
    group.set_tarot_results(_results(group.card_count))
    text = str(group)
    assert text.startswith(f"此次选择的牌阵为：{group.group_name}")
    for position in group.positions:
        assert f"{position}：\n" in text
    assert group.query_prompt() == f"{text}解读思路：{group.interpretation}"


def test_card_text_embeds_image():
    group = YesOrNoGroup()
    result = _results(1)[0]
    result.img_url = "![img](upload://a.jpg)"
    group.set_tarot_results([result])
    assert "[details=逆位愚者]\n![img](upload://a.jpg)\n[/details]" in str(group)


def test_match_score_uses_highest_keyword():
    assert YesOrNoGroup.match_score("我应该换工作吗") == 1.0
    assert LoverPyramidGroup.match_score("他喜欢我") == 0.9
    assert LoverPyramidGroup.match_score("hello") == 0.0


def test_image_cache_is_per_orientation():
    upright, reversed_ = _results(2)[1], _results(1)[0]
    save_image_to_cache(upright, "upright-url")
    assert get_image_from_cache(upright) == "upright-url"
    assert get_image_from_cache(reversed_) is None


@pytest.fixture
def tarot_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return TarotModel(
        tarot_data_path=os.path.join(settings.assets_directory, "tarot_data.json"),
        tarot_img_path=os.path.join(settings.assets_directory, "tarot_img"),
    )


def test_choose_tarot_card(tarot_model):
    results = tarot_model._choose_tarot_card(10)
    assert len({result.index for result in results}) == 10
    for result in results:
        assert tarot_model.tarot_data[result.index - 1] is result.card
    with pytest.raises(ValueError):
        tarot_model._choose_tarot_card(0)


def test_group_named_in_question_is_selected(tarot_model):
    group = asyncio.run(tarot_model.choose_tarot_group("用凯尔特十字看看我的人生"))
    assert group.group_name == "凯尔特十字"
    assert len(group.tarot_results) == 10
