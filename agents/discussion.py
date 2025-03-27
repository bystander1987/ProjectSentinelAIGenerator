import logging
from typing import List, Dict, Any, Optional, Union
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_community.vectorstores import FAISS

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
            model="gemini-2.0-flash-lite",  # 要求通りにgemini-2.0-flash-liteを使用
            google_api_key=api_key,
            temperature=0.7,
            max_tokens=300,  # 出力制限を緩和
            max_retries=2,   # リトライ回数を増加
            timeout=15,      # タイムアウトを長めに設定
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

def create_role_prompt(role: str, topic: str, context: Optional[str] = None) -> str:
    """
    Create a system prompt for a specific role in the discussion.
    
    Args:
        role (str): The role description
        topic (str): The discussion topic
        context (Optional[str]): Optional reference document context
        
    Returns:
        str: Formatted prompt for the role
    """
    base_prompt = f"""
    あなたは「{role}」として振る舞ってください。
    「{topic}」についてのディスカッションに参加しています。
    
    あなたの役割に合った意見を述べ、質問し、他の参加者に応答してください。
    回答は簡潔（2〜3文）かつ洞察に富んだものにしてください。
    どのような状況でも役柄から外れないでください。
    
    回答は簡潔かつ洞察に富んだものにしてください。長すぎる回答は避けてください。
    
    重要: 
    - 感謝やお礼などの議論の論点と関係のない内容は避け、常に議論の本質に集中してください。
    - 「ありがとうございます」「同意します」などの社交辞令や儀礼的表現は使わず、直接的に議論の内容を述べてください。
    - 他の参加者の意見に反応する場合は、その内容に対する具体的な見解や質問、または追加情報を提供してください。
    """
    
    # 参考文書がある場合は追加
    if context:
        context_prompt = f"""
    次の参考文書を考慮に入れて回答してください。この文書に記載されている情報を活用して、適切な発言をしてください。
    
    参考文書:
    {context}
    """
        return base_prompt + context_prompt
    
    return base_prompt

def agent_response(
    llm, 
    role: str, 
    topic: str, 
    discussion_history: List[Dict[str, str]],
    vector_store: Optional[FAISS] = None
) -> str:
    """
    Generate a response from an agent with a specific role.
    
    Args:
        llm: LLM instance
        role (str): The role of the agent
        topic (str): The discussion topic
        discussion_history (List[Dict[str, str]]): Previous discussion turns
        vector_store (Optional[FAISS]): Optional vector store for RAG
        
    Returns:
        str: The agent's response
    """
    # RAGから関連コンテキストを取得（存在する場合）
    context = None
    if vector_store:
        try:
            # 直近の会話と役割から検索クエリを作成
            recent_history_text = ""
            if discussion_history:
                for message in discussion_history[-3:]:  # 直近3つのメッセージを使用
                    recent_history_text += f"{message['content']} "
            
            search_query = f"{topic} {role} {recent_history_text}"
            # 関連ドキュメントを検索
            from agents.document_processor import search_documents, create_context_from_documents
            relevant_docs = search_documents(vector_store, search_query, top_k=3)
            if relevant_docs:
                context = create_context_from_documents(relevant_docs, max_tokens=1000)
                logger.info(f"Retrieved relevant context for {role}")
        except Exception as e:
            logger.warning(f"Failed to retrieve context from vector store: {str(e)}")
    
    # コンテキスト付きのプロンプトを作成
    system_prompt = create_role_prompt(role, topic, context)
    
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
    重要:
    - 回答は簡潔かつ分かりやすくしてください。
    - 冒頭や末尾での感謝やお礼などの表現は不要です。
    - 「～に同意します」「ありがとう」などの社交辞令は避け、すぐに自分の視点や意見を述べてください。
    - 議論の本質と直接関係のある内容のみを発言してください。
    """
    
    try:
        # メモリ使用量を削減するためのタイムアウト設定
        logger.info(f"Generating response for role: {role}")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        # 文字数制限（非常に長い場合のみ適用）
        content = response.content
        # より長い文字数を許容
        if len(content) > 500:
            content = content[:497] + "..."
            
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

def summarize_discussion(
    api_key: str,
    discussion_data: List[Dict[str, str]],
    topic: str,
    language: str = "ja"
) -> Dict[str, str]:
    """
    議論の内容を要約する

    Args:
        api_key (str): Google Gemini API key
        discussion_data (List[Dict[str, str]]): 議論データ
        topic (str): 議論のテーマ
        language (str): 出力言語 (デフォルト: "ja")
        
    Returns:
        Dict[str, str]: 要約結果
    """
    try:
        logger.info(f"Summarizing discussion on topic: {topic}")
        llm = get_gemini_model(api_key, language)
        
        # 議論の内容を文字列にフォーマット
        discussion_text = f"ディスカッションテーマ: {topic}\n\n"
        for turn in discussion_data:
            discussion_text += f"{turn['role']}: {turn['content']}\n\n"
        
        # 要約用プロンプト
        system_prompt = f"""
        あなたは議論の内容を整理し、要約する専門家です。
        以下のディスカッションの内容を読み、次の項目に分けて要約してください:
        
        1. 議論の主なポイント
        2. 各役割の視点や立場
        3. 合意された点
        4. 対立点
        5. 結論または次のステップ
        
        回答はMarkdown形式で整理して提供してください。
        """
        
        prompt = f"""
        以下のディスカッションを要約してください:
        
        {discussion_text}
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        return {
            "success": True,
            "summary": response.content,
            "markdown_content": response.content
        }
        
    except Exception as e:
        logger.error(f"Error summarizing discussion: {str(e)}")
        error_message = str(e)
        
        if "quota" in error_message.lower() or "429" in error_message:
            raise Exception("APIのリクエスト制限に達しました。しばらく待ってから再試行してください。")
        else:
            raise Exception(f"議論の要約に失敗しました: {error_message}")

def provide_discussion_guidance(
    api_key: str,
    discussion_data: List[Dict[str, str]],
    topic: str,
    instruction: str,
    language: str = "ja"
) -> Dict[str, str]:
    """
    議論に対して指示や提案を提供する

    Args:
        api_key (str): Google Gemini API key
        discussion_data (List[Dict[str, str]]): 議論データ
        topic (str): 議論のテーマ
        instruction (str): ユーザーからの指示
        language (str): 出力言語 (デフォルト: "ja")
        
    Returns:
        Dict[str, str]: 指示結果
    """
    try:
        logger.info(f"Providing guidance for discussion on topic: {topic}")
        logger.info(f"Instruction: {instruction}")
        llm = get_gemini_model(api_key, language)
        
        # 議論の内容を文字列にフォーマット
        discussion_text = f"ディスカッションテーマ: {topic}\n\n"
        for turn in discussion_data:
            discussion_text += f"{turn['role']}: {turn['content']}\n\n"
        
        # 指導用プロンプト
        system_prompt = f"""
        あなたは議論のファシリテーターです。
        ディスカッションの内容を分析し、ユーザーの指示に基づいて適切な提案やガイダンスを提供してください。
        回答はMarkdown形式で整理して提供してください。
        """
        
        prompt = f"""
        以下のディスカッションに対して、次の指示に基づいて提案やガイダンスを提供してください:
        
        指示: {instruction}
        
        ディスカッション内容:
        {discussion_text}
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        
        return {
            "success": True,
            "guidance": response.content,
            "markdown_content": response.content
        }
        
    except Exception as e:
        logger.error(f"Error providing discussion guidance: {str(e)}")
        error_message = str(e)
        
        if "quota" in error_message.lower() or "429" in error_message:
            raise Exception("APIのリクエスト制限に達しました。しばらく待ってから再試行してください。")
        else:
            raise Exception(f"議論の指導提供に失敗しました: {error_message}")

def continue_discussion(
    api_key: str,
    discussion_data: List[Dict[str, str]],
    topic: str,
    roles: List[str],
    num_additional_turns: int = 1,
    language: str = "ja",
    vector_store: Optional[FAISS] = None
) -> List[Dict[str, str]]:
    """
    既存の議論を継続する

    Args:
        api_key (str): Google Gemini API key
        discussion_data (List[Dict[str, str]]): 既存の議論データ
        topic (str): 議論のテーマ
        roles (List[str]): 役割のリスト
        num_additional_turns (int): 追加するターン数
        language (str): 出力言語 (デフォルト: "ja")
        vector_store (Optional[FAISS]): RAG用のベクトルストア
        
    Returns:
        List[Dict[str, str]]: 継続された議論データ
    """
    try:
        logger.info(f"Continuing discussion on topic: {topic} for {num_additional_turns} more turns")
        llm = get_gemini_model(api_key, language)
        
        # 既存の議論をコピー
        continued_discussion = discussion_data.copy()
        total_roles = len(roles)
        
        # 追加ターンを生成
        for turn in range(num_additional_turns):
            for i, role in enumerate(roles):
                logger.info(f"Generating additional turn {turn+1}, Role {role}")
                
                # レスポンスを生成
                response = agent_response(llm, role, topic, continued_discussion, vector_store)
                continued_discussion.append({
                    "role": role,
                    "content": response
                })
        
        return continued_discussion
    
    except Exception as e:
        logger.error(f"Error continuing discussion: {str(e)}")
        error_message = str(e)
        
        if "quota" in error_message.lower() or "429" in error_message:
            raise Exception("APIのリクエスト制限に達しました。しばらく待ってから再試行してください。")
        else:
            raise Exception(f"議論の継続に失敗しました: {error_message}")

def generate_next_turn(
    api_key: str,
    topic: str,
    roles: List[str],
    current_discussion: List[Dict[str, str]],
    current_turn: int,
    current_role_index: int,
    language: str = "ja",
    vector_store: Optional[FAISS] = None
) -> Dict[str, Any]:
    """
    Generate the next message in a discussion turn by turn.
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): The discussion topic
        roles (List[str]): List of roles for the agents
        current_discussion (List[Dict[str, str]]): Current discussion history
        current_turn (int): Current turn number (0-indexed)
        current_role_index (int): Current role index in the roles list
        language (str): Output language code (default: "ja")
        vector_store (Optional[FAISS]): Optional vector store for RAG
        
    Returns:
        Dict[str, Any]: Response containing the new message and next turn/role information
    """
    try:
        total_roles = len(roles)
        llm = get_gemini_model(api_key, language)
        
        # 現在の役割を取得
        current_role = roles[current_role_index]
        logger.info(f"Generating response for Turn {current_turn+1}, Role {current_role} ({current_role_index+1}/{total_roles})")
        
        # レスポンスを生成
        response = agent_response(llm, current_role, topic, current_discussion, vector_store)
        new_message = {
            "role": current_role,
            "content": response
        }
        
        # 次の役割とターンの計算
        next_role_index = (current_role_index + 1) % total_roles
        next_turn = current_turn + 1 if next_role_index == 0 else current_turn
        
        return {
            "message": new_message,
            "next_turn": next_turn,
            "next_role_index": next_role_index,
            "is_complete": False
        }
    
    except Exception as e:
        logger.error(f"Error in generate_next_turn: {str(e)}")
        error_message = str(e)
        
        # エラー診断
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
            raise Exception(f"メッセージの生成に失敗しました: {error_message}")

def generate_discussion(
    api_key: str,
    topic: str,
    roles: List[str],
    num_turns: int = 3,
    language: str = "ja",
    vector_store: Optional[FAISS] = None
) -> List[Dict[str, str]]:
    """
    Generate a multi-turn discussion between agents with different roles.
    Note: This is maintained for backwards compatibility but is now implemented
    to generate all turns at once by calling generate_next_turn repeatedly.
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): The discussion topic
        roles (List[str]): List of roles for the agents
        num_turns (int): Number of conversation turns
        language (str): Output language code (default: "ja")
        vector_store (Optional[FAISS]): Optional vector store for RAG
        
    Returns:
        List[Dict[str, str]]: Generated discussion data
    """
    try:
        # 全体的なメモリ使用量を減らすため、小さな機能のかたまりに分割
        logger.info(f"Starting discussion generation: {topic}, Roles: {roles}, Turns: {num_turns}")
        if vector_store:
            logger.info("RAG enabled: Using uploaded document as reference")
        
        discussion = []
        total_roles = len(roles)
        total_iterations = total_roles * num_turns
        
        # ターンごとに生成
        current_turn = 0
        current_role_index = 0
        
        for i in range(total_iterations):
            # 次のメッセージを生成
            result = generate_next_turn(
                api_key=api_key,
                topic=topic,
                roles=roles,
                current_discussion=discussion,
                current_turn=current_turn,
                current_role_index=current_role_index,
                language=language,
                vector_store=vector_store
            )
            
            # 結果を追加
            discussion.append(result["message"])
            
            # 次の状態を更新
            current_turn = result["next_turn"]
            current_role_index = result["next_role_index"]
        
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
