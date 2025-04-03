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

def get_action_items_model(api_key: str, language: str = "ja", model: str = "gemini-2.0-flash-lite", temperature: float = 0.2, max_output_tokens: int = 1024):
    """
    Google Geminiモデルインスタンスを初期化して返す
    
    Args:
        api_key (str): Google Gemini API キー
        language (str): 出力言語 (デフォルト: "ja")
        model (str): 使用するGeminiモデル名 (デフォルト: "gemini-2.0-flash-lite")
        temperature (float): 生成の温度パラメータ (0.0-1.0) (デフォルト: 0.2)
        max_output_tokens (int): 生成する最大トークン数 (デフォルト: 1024)
        
    Returns:
        ChatGoogleGenerativeAI: 初期化されたモデル
    """
    try:
        logger.info(f"アクションアイテム生成用モデルの初期化: {model}, 温度: {temperature}, 最大トークン: {max_output_tokens}")
        model = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
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
以下の議論を分析し、各参加者（役割）に対する具体的なアクションアイテムをまとめてください。

## 議論内容:
{discussion}

## 指示:
1. 各役割が取るべき具体的なアクションを特定してください。アクションは具体的かつ実行可能なものにしてください。
2. アクションには「高・中・低」の優先順位と目安となる期限（例: 1週間以内、1ヶ月以内）を必ず付けてください。
3. 各アクションは測定可能で明確な完了条件を含めてください。
4. 役割ごとに3〜5つの実践的なアクションアイテムを提案してください。
5. 最後に組織全体として取り組むべき次のステップを3つ提案してください。
6. すべてのアクションは社交辞令や感謝の言葉ではなく、具体的な行動指針のみを記述してください。

## 出力形式:
各役割ごとに以下の形式で出力してください。

# アクションアイテム一覧

## [役割名1]
1. **[具体的なアクション名]**: 詳細な説明と完了条件 (優先度: 高/中/低、期限: XX以内)
2. **[具体的なアクション名]**: 詳細な説明と完了条件 (優先度: 高/中/低、期限: XX以内)
...

## [役割名2]
...

## 組織全体の次のステップ
1. **[ステップ名]**: 具体的な実行内容と期待される成果
2. **[ステップ名]**: 具体的な実行内容と期待される成果
3. **[ステップ名]**: 具体的な実行内容と期待される成果
"""
    else:
        # 英語版プロンプト
        template = """
Analyze the following discussion and create specific, actionable items for each participant (role).

## Discussion:
{discussion}

## Instructions:
1. Identify specific, concrete actions that each role should take. Actions must be specific and implementable.
2. Assign each action a priority (High, Medium, Low) and an estimated timeframe (e.g., within 1 week, within 1 month).
3. Include measurable and clear completion criteria for each action.
4. Suggest 3-5 practical action items per role.
5. Finally, propose 3 next steps for the organization as a whole.
6. Focus on actionable directives only, avoiding pleasantries or expressions of gratitude.

## Output Format:
Please output in the following format for each role.

# Action Items List

## [Role Name 1]
1. **[Specific Action Name]**: Detailed explanation with completion criteria (Priority: High/Medium/Low, Deadline: within XX)
2. **[Specific Action Name]**: Detailed explanation with completion criteria (Priority: High/Medium/Low, Deadline: within XX)
...

## [Role Name 2]
...

## Organization-wide Next Steps
1. **[Step Name]**: Specific implementation details and expected outcomes
2. **[Step Name]**: Specific implementation details and expected outcomes
3. **[Step Name]**: Specific implementation details and expected outcomes
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
    language: str = "ja",
    model: str = "gemini-2.0-flash-lite",
    temperature: float = 0.2,
    max_output_tokens: int = 1024
) -> Dict[str, Any]:
    """
    議論データからアクションアイテムを生成する
    
    Args:
        api_key (str): Google Gemini API キー
        discussion_data (List[Dict[str, str]]): 議論データ
        language (str): 出力言語 (デフォルト: "ja")
        model (str): 使用するGeminiモデル名 (デフォルト: "gemini-2.0-flash-lite")
        temperature (float): 生成の温度パラメータ (0.0-1.0) (デフォルト: 0.2)
        max_output_tokens (int): 生成する最大トークン数 (デフォルト: 1024)
        
    Returns:
        Dict[str, Any]: 生成されたアクションアイテムデータ
    """
    try:
        logger.info(f"アクションアイテム生成処理を開始。モデル: {model}, 温度: {temperature}")
        model = get_action_items_model(api_key, language, model, temperature, max_output_tokens)
        
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