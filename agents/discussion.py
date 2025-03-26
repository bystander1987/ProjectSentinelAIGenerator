import logging
from typing import List, Dict, Any
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

def get_gemini_model(api_key: str):
    """
    Initialize and return a Gemini model instance.
    
    Args:
        api_key (str): Google Gemini API key
        
    Returns:
        ChatGoogleGenerativeAI: Initialized model
    """
    return ChatGoogleGenerativeAI(
        model="gemini-pro",
        google_api_key=api_key,
        temperature=0.7
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
    You are roleplaying as {role}. 
    You are participating in a discussion about: {topic}.
    
    Express opinions, ask questions, and respond to other participants in a way that is authentic to your role.
    Keep your responses concise (2-3 sentences) but insightful.
    Do not break character under any circumstances.
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
    num_turns: int = 3
) -> List[Dict[str, str]]:
    """
    Generate a multi-turn discussion between agents with different roles.
    
    Args:
        api_key (str): Google Gemini API key
        topic (str): The discussion topic
        roles (List[str]): List of roles for the agents
        num_turns (int): Number of conversation turns
        
    Returns:
        List[Dict[str, str]]: Generated discussion data
    """
    try:
        llm = get_gemini_model(api_key)
        discussion = []
        
        # Generate the initial prompt for each role to kick off the discussion
        for role in roles:
            response = agent_response(llm, role, topic, discussion)
            discussion.append({
                "role": role,
                "content": response
            })
        
        # Generate subsequent turns
        for _ in range(num_turns - 1):
            for role in roles:
                response = agent_response(llm, role, topic, discussion)
                discussion.append({
                    "role": role,
                    "content": response
                })
        
        return discussion
    
    except Exception as e:
        logger.error(f"Error in generate_discussion: {str(e)}")
        raise Exception(f"Failed to generate discussion: {str(e)}")
