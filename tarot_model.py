import json
import random
from typing import List, Type
from tarot_group_data import *


class TarotModel:
    """
    A model for managing tarot card data.
    """

    def __init__(
        self,
        tarot_data_path: str = "tarot_data.json",
        tarot_img_path: str = "tarot_img",
    ):
        self.tarot_data_path = tarot_data_path
        self.tarot_img_path = tarot_img_path
        self.tarot_data = self._load_tarot_data()

    def _load_tarot_data(self) -> None:
        """
        Load tarot card data from a JSON file.
        """
        with open(self.tarot_data_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return [TarotCard(**card) for card in data]

    def _choose_tarot_card(self, count: int) -> List[TarotResult]:
        """
        Select a specified number of tarot cards randomly from the available data.
        """
        # Check if count is within the valid range
        if count < 1 or count > len(self.tarot_data):
            raise ValueError(
                "Count must be between 1 and the number of available cards."
            )

        # Randomly select cards and determine if they are reversed
        selected_cards = random.sample(self.tarot_data, count)
        results = []
        for card in selected_cards:
            is_reversed = random.choice([True, False])
            results.append(
                TarotResult(
                    card=card,
                    is_reversed=is_reversed,
                    index=self.tarot_data.index(card) + 1,
                )
            )

        return results

    def choose_tarot_group(self, question: str) -> BaseTarotGroup:
        """
        Select a group of tarot cards to answer a question.

        :param question: The question to analyze.
        :return: An instance of a tarot group class with selected tarot results.
        """
        # choose a group
        group = self._select_tarot_group(question)()
        group.set_tarot_results(self._choose_tarot_card(group.card_count))

        return group

    def _select_tarot_group(self, question: str) -> Type[BaseTarotGroup]:
        """
        Select the most suitable tarot group based on the question.
        If the question contains the name of a tarot group, return that group.
        Otherwise, return the one with the highest matching score.
        If no group matches, return a random group.

        :param question: The question to analyze.
        :return: The selected tarot group class.
        """

        # First let's check if the question contains the name of any tarot group
        for group_class in tarot_groups:
            if group_class().group_name in question:
                return group_class

        # OK, let's calculate the match score for each group
        scores = {}
        for group_class in tarot_groups:
            scores[group_class] = group_class.match_score(question)

        max_score = max(scores.values())
        return random.choice([k for k, v in scores.items() if v == max_score])
