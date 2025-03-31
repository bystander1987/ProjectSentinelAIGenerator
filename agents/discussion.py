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
    
    絶対遵守すべき最重要ルール:
    - アップロードされた文書に記載されている内容のみについて発言してください。文書に記載されていない情報や知識に基づいた発言は一切禁止です。
    - 文書に明示的に記載されていない限り、一般的な知識や外部情報を用いた発言を絶対に行わないでください。
    - 必ず文書から直接引用し、どの部分から得た情報かを明確にしてください。
    
    最優先指示:
    - アップロードされた文書の内容を唯一の情報源として扱ってください。
    - 文書に記載されている具体的な事実、数値、データ、見解を文章内で明示的に引用してください。
    - 文書に記載されていないことについては「文書には言及がありません」と明確に述べてください。
    
    重要: 
    - 他の参加者の発言内容の具体的な箇所を指摘し、具体的な言葉を引用しながら議論を進めてください。
    - 自分の意見や主張の根拠は必ずアップロードされた文書から直接引用してください。
    - 文書の内容と直接関係ない発言は絶対に避けてください。
    - 感謝やお礼などの議論の論点と関係のない内容は避け、常に文書の内容に集中してください。
    - 「ありがとうございます」「同意します」などの社交辞令や儀礼的表現は使わず、直接的に文書の内容を述べてください。
    - 抽象的な議論を避け、常に文書からの具体的な引用を含めてください。
    """
    
    # 参考文書がある場合は追加
    if context:
        context_prompt = f"""
    ##################################################
    # 重要: 議論の元となる文書全文
    ##################################################

    次の文書全文を最も重要な情報源、かつ唯一の情報源として厳密に扱ってください。
    この文書に記載されている情報は最優先事項であり、必ず議論の中心に置き、具体的な内容に言及してください。
    
    文書全文:
    ```
    {context}
    ```
    ##################################################

    絶対に遵守すべき最重要ルール:
    - この文書に記載されている内容のみについて発言してください。文書に記載されていない情報や知識に基づいた発言は一切禁止です。
    - 文書に明示的に記載されていない限り、一般的な知識や外部情報を用いた発言を絶対に行わないでください。
    - 必ず文書から直接引用し、どの部分から得た情報かを明示してください。
    - 文書に記載されていない内容について質問された場合は、「文書にはその情報がありません」と明確に述べてください。
    
    最優先指示: 
    1. あなたの役割と上記の文書全文の内容に基づいて、トピック「{topic}」について議論してください。文書に記載されていない情報は一切使用しないでください。
    2. 文書全文の内容を唯一の情報源として発言を組み立ててください。
    3. 文書に記載されていない内容を述べることは絶対に避け、文書に記載されている内容を直接引用してください。
    4. 発言には必ず「文書によると～」「文書に記載されている～」などと言及し、どの部分から情報を得たのかを明確にしてください。
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
    # 文書コンテキストがある場合、ディスカッションテーマに含める
    prompt_with_context = ""
    if context:
        prompt_with_context = f"""
    ディスカッションのテーマ: {topic}
    
    ##################################################
    # ディスカッションの元となる文書全文（唯一の情報源として必ず参照）:
    ##################################################
    
    ```
    {context}
    ```
    ##################################################
    
    {system_instruction_text}
    
    これまでの議論:
    {history_text}
    
    あなたは「{role}」です。最初に行われたコンサルタントによる文書分析と、あなた自身による文書分析を踏まえて、次の発言をしてください。
    あなたの役割固有の視点から、テーマについて文書に基づいた見解を述べてください。
    
    【絶対に従うべき最重要指示】
    以下のルールを必ず遵守してください：
    1. 文書内の情報「のみ」を使用し、外部知識や一般論は一切使用しないでください
    2. 必ず文書からの直接引用を「」で囲んで、最低3回以上含めてください
    3. 引用する際は、引用元の位置情報（セクション番号、段落位置など）を可能な限り付記してください
       例：「文書のセクション3によると、「〜〜〜」と記載されています」
    4. 自己紹介や立場表明は行わず、直接的に議論の内容に入ってください
    5. 事実に基づいた発言を心がけ、意見は文書の引用を根拠として述べてください
    6. 他の参加者の発言に言及する場合も、必ず文書からの引用を含めてください
    7. 数値データを引用する場合は、正確に数値を引用し、その出典を明示してください
    8. 文書に記載されていない情報については言及せず、文書内容のみに集中してください
    
    上記のルールは絶対に守り、文書の内容を正確に反映した発言を心がけてください。
    """
    else:
        prompt_with_context = f"""
    ディスカッションのテーマ: {topic}
    
    {system_instruction_text}
    
    これまでの議論:
    {history_text}
    
    「{role}」として、このディスカッションに次の発言をしてください。
    
    絶対に遵守すべき最重要ルール：
    - 自分の役割紹介や立場表明は行わないでください
    - 前の発言者への挨拶や「～に同意します」などの社交辞令は避けてください
    - 回答は簡潔かつ分かりやすくしてください
    """
    
    # 文書関連の指示は既にprompt_with_contextに含まれているため、追加の指示は不要
    
    prompt = prompt_with_context
    
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
                
                # システムメッセージを追加 - 文書の重要性を強調
                continued_discussion.append({
                    "role": "システム",
                    "content": f"【重要文書情報】議論の継続のため、アップロードされた文書の分析を行います。この文書は議論の主要な情報源です。各役割は文書内容を最優先参照して議論を継続してください。"
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
                    "content": f"文書分析が完了しました。この内容を踏まえて、テーマ「{topic}」についての議論を継続します。常に文書の内容を最も重要な情報源として優先してください。"
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
        document_chunks = search_documents(vector_store, f"{topic} {role}", top_k=12)
        document_context = create_context_from_documents(document_chunks, max_tokens=2500)
        
        if not document_context:
            return ""
        
        logger.info(f"Analyzing document for role: {role} - context length: {len(document_context)}")
        
        # 役割に特化した文書分析のプロンプト
        system_prompt = f"""
        あなたは「{role}」の立場からアップロードされた文書を詳細に分析する専門家です。
        
        【絶対に守るべき最重要指示】
        アップロードされた文書の内容を唯一の情報源として扱い、「{role}」の視点から詳細に分析してください。
        文書に明示的に記載されている情報のみを使用し、外部知識や一般論は一切使用してはなりません。
        
        分析するとき、以下の点を厳守してください：
        1. 文書から「」で囲んだ直接引用を各セクションに最低2つ以上、合計で最低8つ以上含める
        2. 文書内の数値データは正確に引用し、文書内のどのセクションから引用したかを明示する
        3. 抽象的な言及は避け、具体的な引用と根拠を示す（「文書のXXページには「〜〜」と記載されています」など）
        4. 引用の際は、引用元の位置情報（セクション番号、段落位置など）を可能な限り付記する
        5. 文書に記載されていない情報については「文書には記載がありません」と明記する
        
        この分析の目的は、「{role}」が議論において文書の内容を正確に参照し、具体的な引用をもとに発言できるよう準備することです。
        他の役割との違いを明確にし、{role}としての立場や視点を文書内容に基づいて明確に示してください。
        """
        
        prompt = f"""
        アップロードされた以下の文書を「{role}」の立場から徹底的に分析してください。
        この文書は議論の唯一の情報源であり、最優先で参照すべきものです。
        
        文書:
        {document_context}
        
        この文書の中で、「{role}」という役割にとって重要な情報を抽出し、以下の形式で詳細にまとめてください:
        
        ## 「{role}」の立場からの文書分析
        
        ### 1. 重要なポイント
        この文書の中で、{role}にとって最も重要なポイントを具体的な引用と共にリストアップしてください。
        各ポイントには、必ず文書からの直接引用を「」で囲んで含めてください。
        
        ### 2. 役割固有の関心事項
        {role}の立場から特に注目すべき文書内の事項や問題点について、文書からの具体的な引用と共に説明してください。
        
        ### 3. 関連する数値/データ
        {role}が議論で活用できる具体的な数値やデータを文書から抽出し、出典と共に提示してください。
        
        ### 4. 懸念事項
        {role}の立場から見たときに懸念される点を、文書内の記述に基づいて分析してください。
        
        ### 5. 推奨事項/主張すべき点
        {role}としてこの文書の情報に基づいて主張すべき内容や推奨できる事項を具体的に説明してください。
        
        ### 6. 議論での引用ポイント
        議論中に{role}として引用すべき文書内の重要な箇所を5つ以上リストアップし、各引用の文脈や意義を説明してください。
        
        分析は詳細かつ正確に行い、「{topic}」に関する議論で{role}が積極的に活用できる形にしてください。
        他の役割にはない、{role}ならではの視点や関心事を文書内容に基づいて具体的に示してください。
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

def generate_consultant_analysis(
    api_key: str,
    topic: str,
    roles: List[str],
    language: str = "ja",
    vector_store: Optional[FAISS] = None
) -> str:
    """
    アップロードされた文書とテーマに基づいて、コンサルタントの視点で論点を分析する
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): ディスカッションのテーマ
        roles (List[str]): 参加者の役割リスト
        language (str): 出力言語 (デフォルト: "ja")
        vector_store (Optional[FAISS]): 文書のベクトルストア
        
    Returns:
        str: コンサルタントによる論点分析
    """
    try:
        llm = get_gemini_model(api_key, language)
        
        # 文書からの情報抽出
        document_context = ""
        if vector_store:
            try:
                from agents.document_processor import search_documents, create_context_from_documents
                
                # まず文書全体の概要を把握するために広い範囲で検索
                logger.info("Retrieving document content for consultant analysis")
                
                # 一般的な概要検索（幅広く文書をカバー）
                search_query_general = "文書 全体 概要 目的 内容"
                document_chunks_general = search_documents(vector_store, search_query_general, top_k=10)
                
                # テーマに関連する文書部分を検索
                search_query_topic = f"{topic} 関連 重要"
                document_chunks_topic = search_documents(vector_store, search_query_topic, top_k=10)
                
                # 数値データや重要事実の検索
                search_query_data = "データ 数値 表 グラフ 重要 指標"
                document_chunks_data = search_documents(vector_store, search_query_data, top_k=10)
                
                # 課題や論点の検索
                search_query_issues = "課題 問題 論点 懸念 リスク"
                document_chunks_issues = search_documents(vector_store, search_query_issues, top_k=10)
                
                # すべてのチャンクを結合して重複を削除
                all_chunks = []
                for chunk_list in [document_chunks_general, document_chunks_topic, document_chunks_data, document_chunks_issues]:
                    if chunk_list:
                        all_chunks.extend(chunk_list)
                
                # 重複を削除（セットに変換して再度リストに戻す）
                unique_chunks = list(set(all_chunks))
                
                if unique_chunks:
                    document_context = create_context_from_documents(unique_chunks, max_tokens=4000)
                    logger.info(f"Retrieved comprehensive document context for consultant analysis - {len(document_context)} chars, {len(unique_chunks)} unique chunks")
                else:
                    logger.warning("No document chunks retrieved for consultant analysis")
                    # 文書全体のテキストを直接使用するフォールバック（今後追加予定）
            except Exception as e:
                logger.error(f"Failed to retrieve document context for consultant analysis: {str(e)}")
                # エラーの詳細をログに記録
                import traceback
                logger.error(traceback.format_exc())
                raise Exception(f"文書コンテキストの取得に失敗しました: {str(e)}")
        
        if not document_context:
            logger.error("Empty document context for consultant analysis")
            raise Exception("文書の内容を取得できませんでした。文書が正しくアップロードされているか確認してください。")
        
        roles_description = "\n".join([f"- {role}" for role in roles])
        
        # コンサルタント分析用のプロンプト - より詳細な指示を追加
        system_prompt = f"""
        あなたは高度な戦略コンサルタントとして、アップロードされた文書を詳細に分析し、その後テーマに基づいた議論の論点を設定する役割です。
        
        【最優先指示】
        1. アップロードされた文書の内容を唯一の情報源として扱い、文書全体を徹底的に分析してください。
        2. 文書に記載されている情報「のみ」を使用し、外部知識は一切使用してはいけません。
        3. 文書に記載がない内容については「文書には記載がありません」と明示してください。
        4. 一般的な知識や仮定に基づく分析は行わないでください。
        
        【分析方法の重要ポイント】
        1. 各セクションでは、文書から「」または『』で囲んだ直接引用を最低5つ以上含めること
        2. 引用する際は、可能な限り文書内のどの部分からの引用かを明示すること
        3. 文書の構造（章立て、セクション構成など）を詳細に分析すること
        4. 文書内のすべての数値データ、表、グラフ情報を正確に引用すること
        5. 文書の主題、目的、背景、結論を文書内の記述に基づいて明示すること
        
        最も重要なことは、文書内容を正確に伝え、議論の参加者全員が文書の全体像を完全に把握できるようにすることです。
        分析は網羅的かつ詳細で、文書からの直接引用が豊富に含まれていなければなりません。
        """
        
        prompt = f"""
        テーマ: {topic}
        
        参加者の役割:
        {roles_description}
        
        以下が分析対象の文書です:
        
        {document_context if document_context else "文書が提供されていません。"}
        
        上記の文書内容に基づいて、次の形式で詳細な分析結果を提供してください:
        
        ## 文書全体の分析
        
        1. 文書の基本情報 - 文書の種類、目的、対象読者など
        2. 文書の構造 - 章立て、セクション構成、主要な部分の概要
        3. 文書の概要 - 文書全体の内容を要約（内容に応じて5-10文程度）
        4. 重要な数値データ・事実 - 文書内の重要な数値、事実関係の引用
        
        ## テーマに関連する分析
        
        5. 主要な論点 - 文書から抽出した3-5個の主要な論点と、各論点の根拠となる文書からの具体的な引用
        6. 役割別の重要ポイント - 各役割がこのテーマについて注目すべき文書内の部分と具体的な引用
        7. 議論で扱うべき課題 - 文書内容から抽出した、議論すべき主要な課題や問題点
        8. 議論の進め方の提案 - 文書の内容に基づいた議論の進め方の提案
        
        各セクションでは、必ず文書から直接引用した部分を「」で囲んで明示し、その引用がどのセクションや段落から来ているかを可能な限り明記してください。
        文書に記載されていない情報は「文書には言及がありません」と明記してください。
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        logger.info(f"Generating consultant analysis for topic: {topic}")
        response = llm.invoke(messages)
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error generating consultant analysis: {str(e)}")
        raise Exception(f"コンサルタント分析の生成に失敗しました: {str(e)}")

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
        
        # 議論の流れを明確に示すシステムメッセージを追加
        discussion.append({
            "role": "システム",
            "content": f"# 文書ベース議論の開始\n\n【進行手順】\n1. アップロードされた文書の詳細な分析（コンサルタント視点）\n2. 各役割による文書分析（役割ごとの視点）\n3. テーマ「{topic}」に基づく議論\n\n【最重要指示】\nこの議論ではアップロードされた文書の内容を唯一の情報源として使用します。\n議論は文書に記載されている情報のみで行い、外部知識は一切使用しないでください。\n各発言では文書からの直接引用を含め、引用元を明示してください。"
        })
        
        # 文書があれば、まずコンサルタント視点での分析を追加
        if vector_store:
            logger.info("Adding consultant analysis as the first step")
            
            # コンサルタント分析の説明
            discussion.append({
                "role": "システム",
                "content": f"## 第1ステップ: コンサルタントによる文書全体分析\n\nコンサルタントが文書全体を詳細に分析し、主要な内容、構造、重要ポイントを整理します。この分析が議論全体の基礎となります。"
            })
            
            # コンサルタント分析を生成
            consultant_analysis = generate_consultant_analysis(
                api_key=api_key,
                topic=topic,
                roles=roles,
                language=language,
                vector_store=vector_store
            )
            
            # コンサルタント分析の追加
            discussion.append({
                "role": "コンサルタント",
                "content": consultant_analysis
            })
            
            # 各役割の分析の説明
            discussion.append({
                "role": "システム",
                "content": f"## 第2ステップ: 各役割による文書分析\n\n各役割の視点から文書を分析し、その役割特有の関心事項や重要ポイントを明確にします。この分析により、議論で各役割が注目すべき文書内の情報が明らかになります。"
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
                "content": f"## 第3ステップ: テーマに基づく議論開始\n\n以上の文書分析を踏まえて、テーマ「{topic}」についての議論を開始します。\n\n【議論のルール】\n1. 文書からの具体的な引用を含める\n2. 引用元を明示する\n3. 文書に書かれていない情報には言及しない\n4. 他の参加者の発言に対する意見も、文書を根拠として提示する\n\n各役割は自分の文書分析を踏まえ、文書内容に基づいた議論を展開してください。"
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
