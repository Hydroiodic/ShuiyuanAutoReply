import os
from typing import Optional
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_models.tongyi import ChatTongyi
from .mention_chat_model import MentionChatModel
from src.shuiyuan.objects import User
from src.shuiyuan.shuiyuan_model import ShuiyuanModel


class MentionTongyiModel(MentionChatModel):
    """
    A model for managing Tongyi Qianwen data.
    """

    def __init__(self, model: ShuiyuanModel):
        """
        Initialize the Tongyi Qianwen model.
        """
        # Initialize the base class first to set up retriever and other components
        super().__init__(model)

        # Define the ChatTongyi model
        self.llm = ChatTongyi(
            model_name="qwen3-max-2026-01-23",
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
            model_kwargs={
                "temperature": 1.5,
                "enable_thinking": True,
                "incremental_output": True,
            },
        )

    async def get_pumpkin_response(
        self, topic_id: int, conversation: str, user: User
    ) -> Optional[str]:
        """
        Let the model respond based on conversation and similar responses.
        """
        # Initialize MCP connection if not already done
        if not self.agent_executor:
            await self.initialize_agent()

        # Retrieve similar documents from Neo4j
        docs = await self.retriever.ainvoke(conversation)
        context_text = "\n".join([doc.page_content for doc in docs])

        # Retrieve recent posts in the same topic to provide more context
        recent_msgs = await self.get_recent_msgs_context(topic_id)

        # Arrange the input of LangChain
        agent_input = {
            "topic_id": topic_id,
            "username": user.username,
            "name": user.name or "",
            "question": conversation,
            "context": context_text,
            "recent_msgs": recent_msgs,
        }

        # Create RunnableWithMessageHistory
        agent_with_history = RunnableWithMessageHistory(
            self.agent_executor,
            self.get_session_history,
            input_messages_key="question",
            history_messages_key="chat_history",
        )

        response = await agent_with_history.ainvoke(
            agent_input,
            config={"configurable": {"session_id": topic_id}},
        )
        return response["output"]
