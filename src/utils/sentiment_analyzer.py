"""
Sentiment analyzer for financial news and text.
"""

import json
import time
from typing import Dict, Any, Optional

from src.config import config
from src.utils import get_logger

logger = get_logger("sentiment_analyzer")

def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze sentiment of provided text using OpenAI or fallback methods.
    
    Args:
        text: Financial news text to analyze
        
    Returns:
        Dictionary with sentiment analysis results, including:
        - sentiment: "bullish", "bearish", or "neutral"
        - score: 0-100 score (higher = more bullish)
        - explanation: Brief explanation of sentiment reasoning
    """
    # Check if OpenAI is configured
    if config.openai.api_key:
        result = _analyze_with_openai(text)
        if result:
            return result
            
    # Fallback to keyword-based analysis if OpenAI fails
    return _keyword_based_sentiment(text)

def _analyze_with_openai(text: str) -> Optional[Dict[str, Any]]:
    """
    Analyze sentiment using OpenAI's API
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with sentiment results or None if error
    """
    try:
        import openai
        
        # Configure the client
        openai.api_key = config.openai.api_key
        
        # Truncate text if too long
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        # Create prompt
        prompt = f"""
        You are a financial sentiment analyzer. Analyze the following financial news:
        
        "{text}"
        
        Respond with a JSON object containing:
        1. sentiment: either "bullish", "bearish", or "neutral"
        2. score: 0-100 scale where 0 is extremely bearish, 50 is neutral, 100 is extremely bullish
        3. explanation: Brief explanation (max 50 words) for your rating
        
        Your response must be valid JSON with ONLY these three keys.
        """
        
        # Make API call with appropriate model
        response = openai.chat.completions.create(
            model=config.openai.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200
        )
        
        # Extract and parse the response
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON portion if there are additional explanations
        if response_text.startswith("```json"):
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            json_text = response_text.split("```")[1].strip()
        else:
            json_text = response_text
            
        # Clean up any non-JSON content
        json_text = json_text.replace("```", "").strip()
        
        # Parse the JSON
        sentiment_data = json.loads(json_text)
        
        # Ensure we have the required fields
        required_fields = ["sentiment", "score", "explanation"]
        for field in required_fields:
            if field not in sentiment_data:
                logger.error(f"Missing required field in OpenAI response: {field}")
                return None
                
        # Validate and normalize
        sentiment = sentiment_data.get("sentiment", "neutral").lower()
        if sentiment not in ["bullish", "bearish", "neutral"]:
            sentiment = "neutral"
            
        score = float(sentiment_data.get("score", 50))
        score = max(0, min(100, score))  # Ensure score is between 0-100
        
        explanation = sentiment_data.get("explanation", "No explanation provided").strip()
        
        logger.info(f"OpenAI sentiment analysis: {sentiment}, score: {score}")
        
        return {
            "sentiment": sentiment,
            "score": score,
            "explanation": explanation,
            "method": "openai"
        }
    
    except Exception as e:
        logger.error(f"Error analyzing sentiment with OpenAI: {str(e)}")
        return None

def _keyword_based_sentiment(text: str) -> Dict[str, Any]:
    """
    Fallback sentiment analyzer using keyword matching.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with sentiment analysis results
    """
    # Convert to lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # List of positive and negative keywords
    positive_keywords = [
        "gain", "bull", "rally", "surge", "rise", "grow", "positive", "up", "higher",
        "beat", "exceed", "outperform", "profit", "success", "strong", "opportunity",
        "innovation", "breakthrough", "partnership", "leadership", "expansion", "recovery",
        "dividend", "launch", "record high", "approved", "buy", "upgrade", "recommendation"
    ]
    
    negative_keywords = [
        "loss", "bear", "drop", "fall", "decline", "decrease", "negative", "down", "lower",
        "miss", "below", "underperform", "investigation", "lawsuit", "fine", "penalty",
        "weak", "failure", "crisis", "recession", "layoff", "downsize", "debt", "bankruptcy",
        "recall", "scandal", "concern", "risk", "warning", "downgrade", "sell", "caution"
    ]
    
    # Count occurrences of positive and negative keywords
    positive_count = sum(text_lower.count(word) for word in positive_keywords)
    negative_count = sum(text_lower.count(word) for word in negative_keywords)
    
    # Calculate score (0-100 scale)
    total_count = positive_count + negative_count
    if total_count == 0:
        score = 50  # Neutral if no keywords found
    else:
        score = (positive_count / total_count) * 100
    
    # Determine sentiment
    if score > 60:
        sentiment = "bullish"
        explanation = f"Detected {positive_count} positive keywords vs {negative_count} negative keywords."
    elif score < 40:
        sentiment = "bearish"
        explanation = f"Detected {negative_count} negative keywords vs {positive_count} positive keywords."
    else:
        sentiment = "neutral"
        explanation = f"Found a balanced mix of {positive_count} positive and {negative_count} negative keywords."
    
    logger.info(f"Keyword sentiment analysis: {sentiment}, score: {score:.1f}")
    
    return {
        "sentiment": sentiment,
        "score": score,
        "explanation": explanation,
        "method": "keyword"
    }

# Add Ollama-based sentiment analysis if available
def _analyze_with_ollama(text: str) -> Optional[Dict[str, Any]]:
    """
    Analyze sentiment using local Ollama model
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary with sentiment results or None if error
    """
    try:
        import requests
        
        # Check if Ollama configuration is available
        if not config.ollama.host or not config.ollama.model:
            logger.warning("Ollama configuration not available")
            return None
            
        # Truncate text if too long
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        # Create prompt
        prompt = f"""
        You are a financial sentiment analyzer. Analyze the following financial news:
        
        "{text}"
        
        Respond with a JSON object containing:
        1. sentiment: either "bullish", "bearish", or "neutral"
        2. score: 0-100 scale where 0 is extremely bearish, 50 is neutral, 100 is extremely bullish
        3. explanation: Brief explanation (max 50 words) for your rating
        
        Your response must be valid JSON with ONLY these three keys.
        """
        
        # Make API call to Ollama
        response = requests.post(
            f"{config.ollama.host}/api/generate",
            json={
                "model": config.ollama.model,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama API error: {response.status_code}, {response.text}")
            return None
            
        response_data = response.json()
        response_text = response_data.get("response", "").strip()
        
        # Extract JSON portion
        if response_text.startswith("```json"):
            json_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            json_text = response_text.split("```")[1].strip()
        else:
            json_text = response_text
            
        # Clean up any non-JSON content
        json_text = json_text.replace("```", "").strip()
        
        try:
            # Parse the JSON
            sentiment_data = json.loads(json_text)
            
            # Ensure we have the required fields
            required_fields = ["sentiment", "score", "explanation"]
            for field in required_fields:
                if field not in sentiment_data:
                    logger.error(f"Missing required field in Ollama response: {field}")
                    return None
                    
            # Validate and normalize
            sentiment = sentiment_data.get("sentiment", "neutral").lower()
            if sentiment not in ["bullish", "bearish", "neutral"]:
                sentiment = "neutral"
                
            score = float(sentiment_data.get("score", 50))
            score = max(0, min(100, score))  # Ensure score is between 0-100
            
            explanation = sentiment_data.get("explanation", "No explanation provided").strip()
            
            logger.info(f"Ollama sentiment analysis: {sentiment}, score: {score}")
            
            return {
                "sentiment": sentiment,
                "score": score,
                "explanation": explanation,
                "method": "ollama"
            }
        
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from Ollama response: {response_text}")
            return None
    
    except Exception as e:
        logger.error(f"Error analyzing sentiment with Ollama: {str(e)}")
        return None 