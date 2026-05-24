import os
from importlib import resources


class Settings:

    @property
    def assets_directory(self) -> str:
        return str(resources.files("shuiyuan_auto_reply") / "assets")

    @property
    def auto_reply_tag(self) -> str:
        return "<!-- 来自南瓜的自动回复 -->"

    @property
    def embedding_dims(self) -> int:
        value = os.getenv("EMBEDDING_DIMS")
        if value is None:
            raise ValueError("Please set the EMBEDDING_DIMS environment variable.")
        return int(value)


settings = Settings()
