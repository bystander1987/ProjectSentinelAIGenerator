import logging
from typing import List, Dict, Any
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

def get_gemini_model(api_key: str, language: str = "en"):
    """
    Initialize and return a Gemini model instance.
    
    Args:
        api_key (str): Google Gemini API key
        language (str): Output language (default: "en")
        
    Returns:
        ChatGoogleGenerativeAI: Initialized model
    """
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        google_api_key=api_key,
        temperature=0.7,
        max_tokens=300,  # トークン数を制限してメモリ使用量を削減
        generation_config={"language": language}
    )

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
    
    重要: メモリの使用量を減らすため、回答は最大200文字以内に収めてください。
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
    
    # Format the discussion history
    history_text = ""
    if discussion_history:
        for turn in discussion_history:
            history_text += f"{turn['role']}: {turn['content']}\n"
    
    # Prepare the prompt for the agent
    prompt = f"""
    The discussion topic is: {topic}
    
    Previous discussion:
    {history_text}
    
    As {role}, provide your next contribution to this discussion.
    """
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        logger.error(f"Error getting response from LLM: {str(e)}")
        return f"[Error generating response for {role}: {str(e)}]"

def generate_discussion(
    api_key: str,
    topic: str,
    roles: List[str],
    num_turns: int = 3,
    language: str = "en"
) -> List[Dict[str, str]]:
    """
    Generate a multi-turn discussion between agents with different roles.
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): The discussion topic
        roles (List[str]): List of roles for the agents
        num_turns (int): Number of conversation turns
        language (str): Output language code (default: "en")
        
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
