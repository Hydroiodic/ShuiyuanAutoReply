import json
import random
from typing import List
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

    def random_choose_tarot_group(self) -> BaseTarotGroup:
        """
        Randomly select a group of tarot cards.
        """
        # TODO: choose a group
        group = TimeTarotGroup()
        group.set_tarot_results(self._choose_tarot_card(group.card_count))

        return group
