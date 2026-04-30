import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add the parent directory to the system path for module resolution
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from example.models.mention_google_model import MentionGeminiModel

from shuiyuan_auto_reply.shuiyuan.objects import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """
    To store user and token information for each session in memory.
    """

    user: User
    token: str


# Session dict in memory with structure { session_id: SessionData }
active_sessions: Dict[str, SessionData] = {}
bot_instance: Optional[MentionGeminiModel] = None


# Pydantic models for request and response validation
class ChatRequest(BaseModel):
    session_id: str
    token: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str


class ClearRequest(BaseModel):
    session_id: str
    token: str


class ClearResponse(BaseModel):
    status: str
    message: str


# Lifespan function to handle startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance
    logger.info("正在加载环境变量...")
    load_dotenv()

    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("❌ 错误: 未检测到 GOOGLE_API_KEY，请检查 .env 文件。")
        raise RuntimeError("Missing GOOGLE_API_KEY")

    logger.info("🔄 正在初始化模型 (连接 Neo4j 和 Gemini)...")
    try:
        bot_instance = MentionGeminiModel()
        logger.info("✅ 机器人初始化成功！")
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        raise RuntimeError(f"Bot initialization failed: {e}")

    yield

    logger.info("👋 正在关闭应用，清理资源...")
    bot_instance = None


# Initialize FastAPI app with lifespan and CORS middleware
app = FastAPI(title="小南瓜 (Gemini) 对话后端", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Receive a chat message from the frontend,
    perform session registration and token authentication,
    then call the bot instance to get a reply and return it to the frontend.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    if bot_instance is None:
        raise HTTPException(status_code=500, detail="机器人未正确初始化")

    session_id = request.session_id
    provided_token = request.token

    # 1. Session registration and token authentication
    if session_id not in active_sessions:
        # Accessing for the first time, register new session and bind token
        logger.info(f"🆕 注册新会话并绑定 Token: {session_id}")
        new_user = User(id=session_id, username="NULL", name=None)
        active_sessions[session_id] = SessionData(user=new_user, token=provided_token)
        current_session = active_sessions[session_id]
    else:
        # Session already exists, verify the provided token
        current_session = active_sessions[session_id]
        if current_session.token != provided_token:
            logger.warning(f"⚠️ 拦截到非法访问！会话 {session_id} 的 Token 校验失败。")
            # Token mismatch, possible unauthorized access attempt, reject the request
            raise HTTPException(
                status_code=403,
                detail="身份验证失败：Token 错误或已过期。",
            )

    # At this point, the session is authenticated successfully,
    # and we can safely access the user information
    user = current_session.user

    try:
        # 2. Call the bot instance to get a reply based on the user's message and session info
        reply = await bot_instance.get_pumpkin_response(request.message, user)
        return ChatResponse(session_id=session_id, reply=reply)
    except Exception as e:
        logger.error(f"处理消息时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")


@app.post("/api/clear", response_model=ClearResponse)
async def clear_endpoint(request: ClearRequest):
    """
    Clear the session and its history based on the provided session_id and token.
    """
    if bot_instance is None:
        raise HTTPException(status_code=500, detail="机器人未正确初始化")

    session_id = request.session_id
    provided_token = request.token

    # If session_id is not in active_sessions,
    # it means it's already cleared or never existed, so we can return success directly
    if session_id not in active_sessions:
        return ClearResponse(status="success", message="会话已处于清理状态")

    # 1. Authentication check: Ensure the provided token matches the one stored for this session_id
    current_session = active_sessions[session_id]
    if current_session.token != provided_token:
        logger.warning(f"⚠️ 拦截到非法清理请求！会话 {session_id} 的 Token 校验失败。")
        raise HTTPException(
            status_code=403,
            detail="身份验证失败：Token 错误，无法清理他人历史。",
        )

    # 2. Remove the session from active_sessions to clear authentication info
    active_sessions.pop(session_id, None)
    logger.info(f"🗑️ 已移除会话 {session_id} 的鉴权信息")

    # 3. Call the bot instance's method to clear the underlying model history for this session
    try:
        bot_instance.clear_session_history(session_id)
        logger.info(f"🗑️ 已清除会话 {session_id} 的底层模型历史")
        return ClearResponse(status="success", message="已成功清除会话和历史记录")
    except Exception as e:
        logger.error(f"清除底层模型历史时发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"清理模型历史失败: {str(e)}")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "active_sessions_count": len(active_sessions)}


if __name__ == "__main__":
    uvicorn.run("backend:app", host="0.0.0.0", port=11451, reload=True)
