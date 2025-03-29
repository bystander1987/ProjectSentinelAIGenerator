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
            temperature=0.0,  # 最低値に設定して一貫性を向上させる
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
    - インプットや他の参加者の発言内容の具体的な箇所を指摘してください。例えば「XX氏の『〜〜』という指摘に関して」など、具体的な言葉を引用しながら議論を進めてください。
    - 自分の意見や主張の根拠となる参照情報がある場合は、その具体的な箇所に言及してください。
    - 感謝やお礼などの議論の論点と関係のない内容は避け、常に議論の本質に集中してください。
    - 「ありがとうございます」「同意します」などの社交辞令や儀礼的表現は使わず、直接的に議論の内容を述べてください。
    - 他の参加者の意見に反応する場合は、その内容に対する具体的な見解や質問、または追加情報を提供してください。
    - 抽象的な議論を避け、常に具体的な事例や引用を含めるようにしてください。
    """
    
    # 参考文書がある場合は追加
    if context:
        context_prompt = f"""
    次の参考文書を必ず考慮に入れて回答してください。この文書に記載されている情報を議論の中心に置き、具体的な内容に言及してください。
    
    発言には必ず参考文書から少なくとも1つ以上の具体的な情報を引用してください。「参考文書によれば〜」「文書の〜の部分に記載されているように〜」など、明示的に参考文書を引用してください。
    
    参考文書:
    {context}
    
    あなたの役割と参考文書の内容に基づいて、トピック「{topic}」について議論してください。参考文書の内容を中心に発言を組み立てるよう努めてください。
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
            # トピックと役割に特化した検索クエリを作成
            topic_keywords = topic.replace("　", " ").split()  # 日本語のスペースを処理
            role_keywords = role.split("（")[0] if "（" in role else role  # 役割の括弧前の部分を使用
            
            # 議論履歴から重要なキーワードを抽出
            recent_history_keywords = ""
            if discussion_history:
                # 直近のメッセージから重要なフレーズを抽出（最大5つ）
                recent_messages = discussion_history[-3:] if len(discussion_history) >= 3 else discussion_history
                for message in recent_messages:
                    content = message['content']
                    # 短い単語や一般的な単語を除外し、重要そうなフレーズを取得
                    important_phrases = [p for p in content.split("。") if len(p) > 8][:2]
                    recent_history_keywords += " ".join(important_phrases) + " "
            
            # 主要キーワードを強調し、より具体的な検索クエリを構築
            search_query = f"{topic} {role_keywords} {recent_history_keywords}"
            
            logger.info(f"RAG search query: {search_query[:100]}...")
            
            # 関連ドキュメントを検索（より多くの結果を取得してフィルタリング）
            from agents.document_processor import search_documents, create_context_from_documents
            relevant_docs = search_documents(vector_store, search_query, top_k=5)
            
            if relevant_docs:
                # 検索結果をより広範囲に取得してコンテキストを構築
                context = create_context_from_documents(relevant_docs, max_tokens=1500)
                logger.info(f"Retrieved relevant context for {role} - {len(context)} chars")
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
    system_instructions = []
    
    # システムからの指示があれば抽出
    for turn in recent_history:
        if turn['role'] == 'システム':
            system_instructions.append(turn['content'])
        history_text += f"{turn['role']}: {turn['content']}\n"
    
    # システム指示が存在する場合の特別な処理
    system_instruction_text = ""
    if system_instructions:
        # 最新のシステム指示を優先
        latest_instruction = system_instructions[-1]
        system_instruction_text = f"""
        最優先指示: 
        {latest_instruction}
        
        この指示内容は他のすべての考慮事項よりも優先されます。この指示に焦点を当てた発言をしてください。
        """
    
    # エージェント用のプロンプトを準備
    prompt = f"""
    ディスカッションのテーマ: {topic}
    
    {system_instruction_text}
    
    これまでの議論:
    {history_text}
    
    「{role}」として、このディスカッションに次の発言をしてください。
    重要:
    - 前の発言者の具体的な言葉を引用し、それに対して直接応答してください。
    - 「〇〇さんの『××』という点について」のように、具体的な箇所を指摘してください。
    - 抽象的な議論ではなく、具体的な事例や詳細に言及してください。
    - 回答は簡潔かつ分かりやすくしてください。
    - 冒頭や末尾での感謝やお礼などの表現は不要です。
    - 「～に同意します」「ありがとう」などの社交辞令は避け、すぐに自分の視点や意見を述べてください。
    - 議論の本質と直接関係のある内容のみを発言してください。
    - システム指示がある場合は、その内容を最優先事項として扱ってください。
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
    language: str = "ja",
    vector_store: Optional[FAISS] = None
) -> Dict[str, str]:
    """
    議論に対して指示や提案を提供する

    Args:
        api_key (str): Google Gemini API key
        discussion_data (List[Dict[str, str]]): 議論データ
        topic (str): 議論のテーマ
        instruction (str): ユーザーからの指示
        language (str): 出力言語 (デフォルト: "ja")
        vector_store (Optional[FAISS]): RAG用のベクトルストア
        
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
        
        # 文書から関連コンテキストを取得（存在する場合）
        document_context = ""
        if vector_store:
            try:
                from agents.document_processor import search_documents, create_context_from_documents
                
                # 指示と議論のトピックに基づいて検索
                search_query = f"{topic} {instruction}"
                document_chunks = search_documents(vector_store, search_query, top_k=5)
                if document_chunks:
                    document_context = create_context_from_documents(document_chunks, max_tokens=2000)
                    logger.info(f"Retrieved document context for guidance - {len(document_context)} chars")
            except Exception as e:
                logger.warning(f"Failed to retrieve document context for guidance: {str(e)}")
        
        # 指導用プロンプト - 重要度を最優先に設定
        system_prompt = f"""
        あなたは議論のファシリテーターです。
        ディスカッションの内容を分析し、ユーザーの指示に基づいて適切な提案やガイダンスを提供してください。
        回答はMarkdown形式で整理して提供してください。
        
        最重要指示：ユーザーからの指示を最優先事項として扱い、それに焦点を当てた応答を生成してください。
        他の考慮事項よりも、ユーザーの指示に基づいた内容が最も重要です。
        """
        
        prompt = f"""
        以下の指示は最優先事項として扱ってください。この指示内容が他のすべての考慮事項よりも重要です：
        
        最優先指示: {instruction}
        
        この指示に基づいて、以下のディスカッション内容を分析し、適切な提案やガイダンスを提供してください:
        
        ディスカッション内容:
        {discussion_text}
        """
        
        # 文書コンテキストがある場合は追加
        if document_context:
            prompt += f"""
        
        また、以下の参考文書の内容も考慮してください。この文書にある情報を活用して、より具体的なガイダンスを提供してください：
        
        参考文書:
        {document_context}
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
        
        # 文書ベクトルストアがあり、かつこれまでの議論に文書分析が含まれていない場合は、文書分析ステップを追加
        needs_document_analysis = vector_store is not None
        
        # 既存の議論に文書分析が含まれているか確認
        if needs_document_analysis:
            has_document_analysis = False
            for message in discussion_data:
                if message["role"] == "システム" and "文書の分析" in message["content"]:
                    has_document_analysis = True
                    break
            
            # 文書分析がまだない場合は追加
            if not has_document_analysis:
                logger.info("Adding document analysis step before continuing the discussion")
                
                # システムメッセージを追加
                continued_discussion.append({
                    "role": "システム",
                    "content": f"議論の継続のため、アップロードされた文書の分析を行います。各役割が文書内容を踏まえて議論を継続します。"
                })
                
                # 各役割が文書を分析
                for role in roles:
                    analysis = analyze_document_for_role(api_key, role, topic, language, vector_store)
                    if analysis:
                        continued_discussion.append({
                            "role": role,
                            "content": analysis
                        })
                
                # 分析後の議論継続を示すシステムメッセージ
                continued_discussion.append({
                    "role": "システム",
                    "content": f"文書分析が完了しました。この内容を踏まえて、テーマ「{topic}」についての議論を継続します。"
                })
        
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

def analyze_document_for_role(
    api_key: str,
    role: str,
    topic: str,
    language: str,
    vector_store: FAISS
) -> str:
    """
    文書を特定の役割の視点から分析する
    
    Args:
        api_key (str): Google Gemini API key
        role (str): 分析する役割
        topic (str): 議論のテーマ
        language (str): 出力言語
        vector_store (FAISS): 文書のベクトルストア
        
    Returns:
        str: 分析結果
    """
    try:
        llm = get_gemini_model(api_key, language)
        
        # 文書全体の内容を取得
        from agents.document_processor import search_documents, create_context_from_documents
        # トピックと役割に関連する内容を検索 (より多めに取得)
        document_chunks = search_documents(vector_store, f"{topic} {role}", top_k=10)
        document_context = create_context_from_documents(document_chunks, max_tokens=2000)
        
        if not document_context:
            return ""
        
        logger.info(f"Analyzing document for role: {role} - context length: {len(document_context)}")
        
        # 役割に特化した文書分析のプロンプト
        system_prompt = f"""
        あなたは「{role}」の視点から情報を分析する専門家です。
        以下の文書を{role}の視点から分析し、この役割にとって重要なポイントを抽出してください。
        
        特に「{topic}」というテーマに関連して、この役割が着目すべき情報に焦点を当ててください。
        """
        
        prompt = f"""
        以下の文書を「{role}」の視点から分析してください。
        
        文書:
        {document_context}
        
        この文書の中で、「{role}」という役割にとって重要な情報を抽出し、以下の形式でまとめてください:
        
        1. 重要なポイント: この文書の中で、{role}にとって最も重要なポイントをリストアップ
        2. 関連する数値/データ: {role}が議論で引用できる具体的な数値やデータ
        3. 懸念事項: {role}の立場から見たときに懸念される点
        4. 推奨事項: {role}としてこの情報に基づいて推奨できること
        
        回答は簡潔にまとめ、「{topic}」に関する議論で活用できる形にしてください。
        冒頭に「文書分析：」と記載してください。
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        logger.error(f"Error analyzing document for role {role}: {str(e)}")
        return f"文書の分析中にエラーが発生しました: {str(e)}"

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
        
        # 文書があれば、まず各ロールが文書を分析するステップを追加
        if vector_store:
            logger.info("Adding document analysis step for each role")
            # システムメッセージを追加
            discussion.append({
                "role": "システム",
                "content": f"アップロードされた文書の分析を行います。各役割が文書内容を理解した上で議論を開始します。"
            })
            
            # 各役割が文書を分析
            for role in roles:
                analysis = analyze_document_for_role(api_key, role, topic, language, vector_store)
                if analysis:
                    discussion.append({
                        "role": role,
                        "content": analysis
                    })
            
            # 分析後の議論開始を示すシステムメッセージ
            discussion.append({
                "role": "システム",
                "content": f"文書分析が完了しました。この内容を踏まえて、テーマ「{topic}」についての議論を開始します。"
            })
        
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
