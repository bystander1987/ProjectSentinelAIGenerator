"""
アクションアイテムモジュール - 議論からアクションアイテムを生成する機能
"""

import logging
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

# ログ設定
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def get_action_items_model(api_key: str, language: str = "ja"):
    """
    Google Geminiモデルインスタンスを初期化して返す
    
    Args:
        api_key (str): Google Gemini API キー
        language (str): 出力言語 (デフォルト: "ja")
        
    Returns:
        ChatGoogleGenerativeAI: 初期化されたモデル
    """
    try:
        model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            google_api_key=api_key,
            temperature=0.2,
            max_output_tokens=1024,
        )
        return model
    except Exception as e:
        logger.error(f"Failed to initialize Gemini model: {str(e)}")
        raise

def create_action_items_prompt(discussion_data: List[Dict[str, str]], language: str = "ja") -> str:
    """
    アクションアイテム生成のためのプロンプトを作成する
    
    Args:
        discussion_data (List[Dict[str, str]]): 議論データ
        language (str): 出力言語 (デフォルト: "ja")
        
    Returns:
        str: フォーマット済みプロンプト
    """
    # 言語に基づいたプロンプトテンプレート
    if language.lower() == "ja":
        template = """
以下の議論を分析し、各参加者（役割）に対するアクションアイテムをまとめてください。

## 議論内容:
{discussion}

## 指示:
1. 各役割が取るべき具体的なアクションを特定してください。
2. アクションには優先順位（高・中・低）をつけてください。
3. 各アクションの期限や完了条件を明確にしてください。
4. 役割ごとに最大5つのアクションアイテムを提案してください。
5. 最後に全体の次のステップを3つ提案してください。

## 出力形式:
各役割ごとに以下の形式で出力してください。

# アクションアイテム一覧

## [役割名1]
1. **アクション1**: 説明 (優先度: 高/中/低)
2. **アクション2**: 説明 (優先度: 高/中/低)
...

## [役割名2]
...

## 次のステップ
1. ...
2. ...
3. ...
"""
    else:
        # 英語版プロンプト
        template = """
Analyze the following discussion and summarize action items for each participant (role).

## Discussion:
{discussion}

## Instructions:
1. Identify specific actions that each role should take.
2. Assign priority (High, Medium, Low) to each action.
3. Clearly define deadlines or completion criteria for each action.
4. Suggest a maximum of 5 action items per role.
5. Finally, propose 3 next steps for the entire team.

## Output Format:
Please output in the following format for each role.

# Action Items List

## [Role Name 1]
1. **Action 1**: Description (Priority: High/Medium/Low)
2. **Action 2**: Description (Priority: High/Medium/Low)
...

## [Role Name 2]
...

## Next Steps
1. ...
2. ...
3. ...
"""

    # 議論内容をフォーマット
    discussion_text = ""
    for msg in discussion_data:
        discussion_text += f"{msg['role']}: {msg['content']}\n\n"
    
    prompt = PromptTemplate(
        template=template,
        input_variables=["discussion"]
    )
    
    return prompt.format(discussion=discussion_text)

def generate_action_items(
    api_key: str,
    discussion_data: List[Dict[str, str]],
    language: str = "ja"
) -> Dict[str, Any]:
    """
    議論データからアクションアイテムを生成する
    
    Args:
        api_key (str): Google Gemini API キー
        discussion_data (List[Dict[str, str]]): 議論データ
        language (str): 出力言語 (デフォルト: "ja")
        
    Returns:
        Dict[str, Any]: 生成されたアクションアイテムデータ
    """
    try:
        logger.info("Initializing model for action items generation")
        model = get_action_items_model(api_key, language)
        
        logger.info("Creating action items prompt")
        prompt = create_action_items_prompt(discussion_data, language)
        
        logger.info("Generating action items")
        response = model.invoke(prompt)
        
        result = {
            "success": True,
            "action_items": response.content
        }
        
    except Exception as e:
        logger.error(f"Error generating action items: {str(e)}")
        result = {
            "success": False,
            "error": str(e)
        }
    
    return result