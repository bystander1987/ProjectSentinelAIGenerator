import logging
from typing import List, Dict, Any
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

def get_gemini_model(api_key: str, language: str = "ja"):
    """
    Initialize and return a Gemini model instance.
    
    Args:
        api_key (str): Google Gemini API key
        language (str): Output language (default: "ja")
        
    Returns:
        ChatGoogleGenerativeAI: Initialized model
    """
    try:
        logger.info(f"Initializing Gemini model with language: {language}")
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # より軽量なモデルに変更
            google_api_key=api_key,
            temperature=0.7,
            max_tokens=100,  # さらにトークン数を制限
            max_retries=1,   # リトライ回数を最小に
            timeout=10,      # タイムアウトを短く設定
            generation_config={"language": language}
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to initialize Gemini model: {error_msg}")
        
        # 詳細なエラーメッセージを生成
        if "quota" in error_msg.lower() or "429" in error_msg:
            raise Exception("APIのリクエスト制限に達しました。時間を置いて再度お試しください。")
        elif "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            raise Exception("APIキー認証エラー：APIキーが無効または期限切れです。")
        elif "key" in error_msg.lower():
            raise Exception("APIキーエラー：有効なAPIキーを設定してください。")
        else:
            raise Exception(f"Geminiモデルの初期化エラー: {error_msg}")

def create_role_prompt(role: str, topic: str) -> str:
    """
    Create a system prompt for a specific role in the discussion.
    
    Args:
        role (str): The role description
        topic (str): The discussion topic
        
    Returns:
        str: Formatted prompt for the role
    """
    return f"""
    あなたは「{role}」として振る舞ってください。
    「{topic}」についてのディスカッションに参加しています。
    
    あなたの役割に合った意見を述べ、質問し、他の参加者に応答してください。
    回答は簡潔（2〜3文）かつ洞察に富んだものにしてください。
    どのような状況でも役柄から外れないでください。
    
    重要: メモリの使用量を減らすため、回答は最大100文字以内に収めてください。
    """

def agent_response(
    llm, 
    role: str, 
    topic: str, 
    discussion_history: List[Dict[str, str]]
) -> str:
    """
    Generate a response from an agent with a specific role.
    
    Args:
        llm: LLM instance
        role (str): The role of the agent
        topic (str): The discussion topic
        discussion_history (List[Dict[str, str]]): Previous discussion turns
        
    Returns:
        str: The agent's response
    """
    system_prompt = create_role_prompt(role, topic)
    
    # メモリ使用量削減のため、直近の会話履歴のみ含める
    recent_history = []
    if discussion_history:
        # 直近5つの発言だけを使用
        history_length = len(discussion_history)
        start_idx = max(0, history_length - 5)
        recent_history = discussion_history[start_idx:]
    
    # 会話履歴のフォーマット
    history_text = ""
    for turn in recent_history:
        history_text += f"{turn['role']}: {turn['content']}\n"
    
    # エージェント用のプロンプトを準備
    prompt = f"""
    ディスカッションのテーマ: {topic}
    
    これまでの議論:
    {history_text}
    
    「{role}」として、このディスカッションに次の発言をしてください。
    重要: 回答は非常に短く、100文字以内に収めてください。
    """
    
    try:
        # メモリ使用量を削減するためのタイムアウト設定
        logger.info(f"Generating response for role: {role}")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        # 文字数制限を強制
        content = response.content
        if len(content) > 150:
            content = content[:147] + "..."
            
        return content
        
    except Exception as e:
        logger.error(f"Error getting response from LLM: {str(e)}")
        error_msg = str(e)
        
        # エラータイプに基づいて対応
        if "quota" in error_msg.lower() or "429" in error_msg:
            return f"[APIのリクエスト制限により、{role}の発言を生成できませんでした]"
        elif "timeout" in error_msg.lower():
            return f"[タイムアウトのため、{role}の発言を生成できませんでした]"
        else:
            return f"[エラー: {role}の発言を生成できませんでした]"

def generate_discussion(
    api_key: str,
    topic: str,
    roles: List[str],
    num_turns: int = 3,
    language: str = "ja"
) -> List[Dict[str, str]]:
    """
    Generate a multi-turn discussion between agents with different roles.
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): The discussion topic
        roles (List[str]): List of roles for the agents
        num_turns (int): Number of conversation turns
        language (str): Output language code (default: "ja")
        
    Returns:
        List[Dict[str, str]]: Generated discussion data
    """
    try:
        # 全体的なメモリ使用量を減らすため、小さな機能のかたまりに分割
        logger.info(f"Starting discussion generation: {topic}, Roles: {roles}, Turns: {num_turns}")
        llm = get_gemini_model(api_key, language)
        discussion = []
        total_roles = len(roles)
        total_iterations = total_roles * num_turns
        
        # 1つずつ生成してメモリを管理
        # 各役割の最初の応答を生成
        logger.info("Generating initial responses")
        for i, role in enumerate(roles):
            logger.info(f"Generating response for {role} ({i+1}/{total_roles})")
            response = agent_response(llm, role, topic, discussion)
            discussion.append({
                "role": role,
                "content": response
            })
        
        # 後続のターンを生成
        if num_turns > 1:
            logger.info(f"Generating {num_turns-1} additional turns")
            for turn in range(1, num_turns):
                for i, role in enumerate(roles):
                    current_iteration = (turn * total_roles) + i + 1
                    logger.info(f"Turn {turn+1}, Role {role} ({current_iteration}/{total_iterations})")
                    
                    # レスポンスを生成
                    response = agent_response(llm, role, topic, discussion)
                    discussion.append({
                        "role": role,
                        "content": response
                    })
        
        return discussion
    
    except Exception as e:
        logger.error(f"Error in generate_discussion: {str(e)}")
        error_message = str(e)
        
        # より詳細なエラー診断
        if "quota" in error_message.lower() or "429" in error_message or "limit" in error_message.lower():
            logger.error("API rate limit or quota exceeded")
            raise Exception("APIのリクエスト制限に達しました。しばらく待ってから再試行してください。")
        elif "permission" in error_message.lower() or "access" in error_message.lower() or "auth" in error_message.lower():
            logger.error("API authentication or permission error")
            raise Exception("APIの認証エラー：APIキーの権限をご確認ください。")
        elif "memory" in error_message.lower() or "resource" in error_message.lower():
            logger.error("Memory or resource limitation error")
            raise Exception("リソース制限エラー：少ないロール数や少ないターン数でお試しください。")
        else:
            logger.error(f"Unknown error: {error_message}")
            raise Exception(f"ディスカッションの生成に失敗しました: {error_message}")
