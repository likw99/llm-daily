#!/usr/bin/env python3
"""
LLM Daily Diagnostics Script

This script tests all components of LLM Daily to ensure they're working correctly.
Run this before deploying to GitHub Actions to verify everything is set up properly.
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the main modules
sys.path.append(str(Path(__file__).parent.parent))

from llm_daily.collectors.reddit_collector import RedditCollector
from llm_daily.generators.newsletter_generator import NewsletterGenerator
from llm_daily.publishers.buttondown_publisher import ButtondownPublisher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("llm_daily.diagnostics")

def check_environment_variables():
    """Check if all required environment variables are set"""
    logger.info("Checking environment variables...")
    
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        logger.error("Set ANTHROPIC_API_KEY, or OPENAI_API_KEY with LLMDAILY_PROVIDER=openai")
        return False

    required_vars = [
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET"
    ]
    
    optional_vars = [
        "BUTTONDOWN_API_KEY",
        "NEWSLETTER_STATUS"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    for var in optional_vars:
        if not os.environ.get(var):
            logger.warning(f"Optional environment variable not set: {var}")
    
    logger.info("Environment variables check passed!")
    return True

def test_reddit_collector(limit=2):
    """Test the Reddit collector"""
    logger.info("Testing Reddit collector...")
    
    try:
        collector = RedditCollector()
        start_time = time.time()
        formatted_data, raw_data = collector.run(time_period=24, limit=limit)
        duration = time.time() - start_time
        
        if not raw_data:
            logger.error("Reddit collector returned empty data")
            return False
        
        subreddit_count = len(raw_data)
        total_posts = sum(len(posts) for posts in raw_data.values())
        
        logger.info(f"Reddit collector successfully retrieved {total_posts} posts " 
                   f"from {subreddit_count} subreddits in {duration:.2f} seconds")
        
        if total_posts == 0:
            logger.warning("No posts were collected. This might be normal if the time period is too short.")
        
        return True
    except Exception as e:
        logger.error(f"Reddit collector test failed: {str(e)}", exc_info=True)
        return False

def test_newsletter_generator():
    """Test the newsletter generator with minimal input"""
    logger.info("Testing newsletter generator...")
    
    try:
        generator = NewsletterGenerator()
        start_time = time.time()
        
        # Generate a minimal "test" newsletter without Reddit data
        content = generator.generate_content()
        duration = time.time() - start_time
        
        if not content:
            logger.error("Newsletter generator returned empty content")
            return False
        
        content_length = len(content)
        word_count = len(content.split())
        
        logger.info(f"Newsletter generator produced {word_count} words ({content_length} chars) "
                   f"in {duration:.2f} seconds")
        
        # Write sample to a file
        output_dir = Path("data/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        sample_file = output_dir / f"test_newsletter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(sample_file, "w") as f:
            f.write(content)
        
        logger.info(f"Sample newsletter saved to {sample_file}")
        return True
    except Exception as e:
        logger.error(f"Newsletter generator test failed: {str(e)}", exc_info=True)
        return False

def test_buttondown_api():
    """Test Buttondown API connection (if configured)"""
    buttondown_api_key = os.environ.get("BUTTONDOWN_API_KEY")
    
    if not buttondown_api_key:
        logger.warning("Skipping Buttondown API test - No API key configured")
        return None
    
    logger.info("Testing Buttondown API connection...")
    
    try:
        ButtondownPublisher()  # raises if BUTTONDOWN_API_KEY is missing
        
        # Test API connection by attempting to get a draft email
        # This is a safe operation that won't publish anything
        
        url = "https://api.buttondown.email/v1/emails?status=draft&count=1"
        headers = {
            "Authorization": f"Token {buttondown_api_key}",
            "Content-Type": "application/json"
        }
        
        import requests
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            logger.info("Buttondown API connection successful!")
            return True
        else:
            logger.error(f"Buttondown API connection failed: {response.status_code}")
            logger.error(response.text)
            return False
    except Exception as e:
        logger.error(f"Buttondown API test failed: {str(e)}", exc_info=True)
        return False

def main():
    """Run all diagnostics"""
    logger.info("Starting LLM Daily diagnostics...")
    
    # Load environment variables
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)
    
    # Run tests
    env_check = check_environment_variables()
    reddit_check = test_reddit_collector()
    generator_check = test_newsletter_generator()
    buttondown_check = test_buttondown_api()
    
    # Print summary
    logger.info("\n=== DIAGNOSTICS SUMMARY ===")
    logger.info(f"Environment Variables: {'✅ PASS' if env_check else '❌ FAIL'}")
    logger.info(f"Reddit Collector: {'✅ PASS' if reddit_check else '❌ FAIL'}")
    logger.info(f"Newsletter Generator: {'✅ PASS' if generator_check else '❌ FAIL'}")
    
    if buttondown_check is None:
        logger.info("Buttondown API: ⚠️ SKIPPED (not configured)")
    else:
        logger.info(f"Buttondown API: {'✅ PASS' if buttondown_check else '❌ FAIL'}")
    
    # Final verdict
    required_checks = [env_check, reddit_check, generator_check]
    if all(required_checks):
        logger.info("\n✅ All required checks passed! The system is ready for deployment.")
        if buttondown_check is False:
            logger.warning("⚠️ Note: Buttondown publishing will not work until the API issue is fixed.")
        return 0
    else:
        logger.error("\n❌ Some checks failed. Please fix the issues before deploying.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
