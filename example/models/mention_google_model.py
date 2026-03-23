from typing import Dict, List, Optional
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)
from .mention_chat_model import MentionChatModel
from src.shuiyuan.objects import User
from src.shuiyuan.shuiyuan_model import ShuiyuanModel


class MentionGeminiModel(MentionChatModel):
    """
    A model for managing Google Gemini data with Manual History Management.
    """

    def __init__(self, model: ShuiyuanModel):
        # Initialize the base class first to set up retriever and other components
        super().__init__(model)

        # Then initialize the Gemini model with specific parameters
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.1-pro-preview",
            temperature=0.8,
            safety_settings={
                # HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                # HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            },
            convert_system_message_to_human=False,
            client_args={"proxy": "socks5://127.0.0.1:7890"},
            # max_output_tokens=4096,
            # thinking_budget=2048,
        )

    def _parse_gemini_output(self, raw_output: List[Dict | str]) -> str:
        res = ""
        for item in raw_output:
            if isinstance(item, dict) and "text" in item:
                res += item["text"]
            if hasattr(item, "text"):
                res += item.text
            if isinstance(item, str):
                res += item
        return res.strip()

    async def get_pumpkin_response(
        self, topic_id: int, conversation: str, user: User
    ) -> Optional[str]:
        # Initialize agent for the first time
        if not self.agent_executor:
            await self.initialize_agent()

        docs = await self.retriever.ainvoke(conversation)
        context_text = "\n".join([doc.page_content for doc in docs])

        history_obj = self.get_session_history(topic_id)
        current_history_messages = history_obj.messages

        recent_msgs = await self.get_recent_msgs_context(topic_id)

        agent_input = {
            "topic_id": topic_id,
            "username": user.username,
            "name": user.name or "",
            "question": conversation,
            "context": context_text,
            "chat_history": current_history_messages,
            "recent_msgs": recent_msgs,
        }

        # Here we assume that agent_executor must not be None
        response = await self.agent_executor.ainvoke(agent_input)
        raw_output = response.get("output")
        final_clean_text = self._parse_gemini_output(raw_output)

        # Append history for the session
        history_obj.add_user_message(conversation)
        history_obj.add_ai_message(final_clean_text)

        return final_clean_text
