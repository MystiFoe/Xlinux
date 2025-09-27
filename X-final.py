import os
import time
import random
import asyncio
import platform
import re

import openai
from playwright.async_api import async_playwright
import json

# ---------------------- 🔐 CONFIG ----------------------

import os
# ✅ Load secrets from environment variables
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
X_USERNAME = os.getenv("X_USERNAME")
X_PASSWORD = os.getenv("X_PASSWORD")

# ✅ User data directory for persistent session
USER_DATA_DIR = os.path.expanduser("~/x_automation/user_data")

# ✅ Load configuration from config.json
def load_config():
    """Load configuration from config.json"""
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading config: {e}")

    # Default configuration
    return {
        "keywords": ["AI", "India"],
        "scroll_count": 5,
        "post_replies": True,
        "min_scroll_delay": 3,
        "max_scroll_delay": 8,
        "min_action_delay": 0.5,
        "max_action_delay": 2.5,
        "debug_mode": True,
        "max_reply_attempts": 3,
        "reply_prompt": """As an experienced industry leader, reply to "{tweet_text}" in under *260 characters*. Match their tone, be respectful, add insight from experience, never mention yourself, avoid clichés/slang, and invite meaningful dialogue."""
    }

# Load configuration
config = load_config()

# ✅ Apply configuration values
KEYWORDS = config["keywords"]
SCROLL_COUNT = config["scroll_count"]
POST_REPLIES = config["post_replies"]
MIN_SCROLL_DELAY = config["min_scroll_delay"]
MAX_SCROLL_DELAY = config["max_scroll_delay"]
MIN_ACTION_DELAY = config["min_action_delay"]
MAX_ACTION_DELAY = config["max_action_delay"]
DEBUG_MODE = config["debug_mode"]
MAX_REPLY_ATTEMPTS = config["max_reply_attempts"]
REPLY_PROMPT_TEMPLATE = config["reply_prompt"]

# ✅ Fixed timeouts
HOME_PAGE_LOAD_TIMEOUT = 60  # Timeout for home page loading
REPLY_SUBMISSION_TIMEOUT = 30
DIALOG_DETECTION_TIMEOUT = 10
# -------------------------------------------------------

# ---------------------- 🧠 OPENAI GENERATION ----------------------
async def generate_valuable_reply(tweet_text):
    """Generate a valuable, tone-matched reply using OpenAI's API"""
    prompt = REPLY_PROMPT_TEMPLATE.format(tweet_text=tweet_text)
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip()
        
        # Clean up quotes in the reply to avoid formatting issues
        reply = reply.replace('"', '').replace('"', '').replace(''', "'").replace(''', "'")
        
        return reply
    except Exception as e:
        print(f"⚠️ Error generating reply: {e}")
        return "This is interesting! Tell me more about your perspective."

# ---------------------- 🧍 HUMAN-LIKE BEHAVIOR ----------------------
async def random_delay(min_seconds=MIN_ACTION_DELAY, max_seconds=MAX_ACTION_DELAY):
    """Wait for a random amount of time to simulate human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
    return delay

async def human_like_typing(page, selector, text):
    """Type text like a human with variable speed and occasional pauses"""
    try:
        # First clear the field
        await page.click(selector)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        
        # Then type the text character by character
        for char in text:
            await page.keyboard.type(char, delay=random.uniform(15, 100))
            # Occasionally pause while typing
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.1, 0.3))
        
        return True
    except Exception as e:
        print(f"⚠️ Error during typing: {e}")
        return False

# ---------------------- 🔍 DEBUG HELPERS ----------------------
async def save_screenshot(page, filename):
    """Save a screenshot for debugging"""
    if not DEBUG_MODE:
        return
    
    try:
        screenshots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshots_dir, filename)
        await page.screenshot(path=screenshot_path, full_page=False)
        print(f"📸 Screenshot saved: {screenshot_path}")
    except Exception as e:
        print(f"⚠️ Screenshot error: {e}")

async def is_verified(tweet):
    """Simple check for verified badge using the exact selector"""
    try:
        # Use the data-testid from your HTML
        verified = await tweet.query_selector('svg[data-testid="icon-verified"]')
        return verified is not None
    except Exception:
        return False

# ---------------------- 🔑 LOGIN FUNCTIONALITY ----------------------
async def check_login_status(page):
    """Check if we're already logged in"""
    print("🔍 Checking login status...")
    
    # Check if we're on the home page
    current_url = page.url
    if "twitter.com/home" in current_url or "x.com/home" in current_url:
        try:
            # Look for elements that would only be present when logged in
            await page.wait_for_selector('div[aria-label="Home timeline"], div[aria-label="Timeline: Home"]', 
                                        timeout=5000)
            print("✅ Already logged in!")
            return True
        except Exception:
            print("⚠️ On home page but timeline not found. May need to log in.")
    
    print("⚠️ Not logged in.")
    return False

async def login_to_x(page, username, password):
    """Log in to X with provided credentials"""
    print("🔑 Attempting to log in to X...")
    
    try:
        # Navigate to X login page
        await page.goto("https://twitter.com/i/flow/login", wait_until="domcontentloaded")
        
        # Wait for the page to load and username field to be visible
        await page.wait_for_selector('input[autocomplete="username"]', timeout=10000)
        
        # Enter username with human-like typing
        await human_like_typing(page, 'input[autocomplete="username"]', username)
        await random_delay()
        
        # Click the Next button
        await page.click('div[role="button"] div:has-text("Next")')
        await random_delay(2, 3)
        
        # Check if we need to enter additional verification
        try:
            unusual_activity = await page.query_selector('div:has-text("We need to confirm you\'re not a robot")')
            if unusual_activity:
                print("⚠️ X is asking for verification. Please complete this manually.")
                print("The script will wait for you to complete verification and reach the home page.")
                await page.wait_for_selector('div[aria-label="Home timeline"], div[aria-label="Timeline: Home"]', 
                                           timeout=120000)  # 2 minute timeout for manual verification
                return True
        except Exception:
            # No verification needed, continue with normal login
            pass
        
        # Wait for password field
        await page.wait_for_selector('input[type="password"]', timeout=10000)
        
        # Enter password with human-like typing
        await human_like_typing(page, 'input[type="password"]', password)
        await random_delay()
        
        # Click the Log in button
        await page.click('div[role="button"] div:has-text("Log in")')
        
        # Wait for the home timeline to load
        await page.wait_for_selector('div[aria-label="Home timeline"], div[aria-label="Timeline: Home"]', 
                                   timeout=30000)
        
        print("✅ Successfully logged in to X!")
        return True
        
    except Exception as e:
        print(f"⚠️ Login failed: {e}")
        return False

# ---------------------- 🌐 HOME PAGE LOADING CHECK ----------------------
async def wait_for_home_page_loaded(page, timeout=HOME_PAGE_LOAD_TIMEOUT):
    """Wait for the X home page to be fully loaded with tweets visible"""
    print("⏳ Waiting for X home page to be fully loaded...")
    
    try:
        # Wait for the home timeline container
        await page.wait_for_selector('div[aria-label="Home timeline"], div[aria-label="Timeline: Home"]', 
                                   timeout=timeout * 1000)
        
        # Wait for tweets to be visible
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
        
        # Wait for at least 3 tweets to be loaded to ensure the page is properly populated
        for attempt in range(10):  # Try up to 10 times
            tweets = await page.query_selector_all('article[data-testid="tweet"]')
            if len(tweets) >= 3:
                print(f"✅ Home page fully loaded with {len(tweets)} tweets visible!")
                return True
            
            print(f"⏳ Only {len(tweets)} tweets loaded, waiting for more...")
            await asyncio.sleep(2)  # Wait a bit more for tweets to load
        
        # If we get here, we have some tweets but maybe not as many as expected
        print("⚠️ Home page loaded but with fewer tweets than expected. Continuing anyway...")
        return True
        
    except Exception as e:
        print(f"⚠️ Error while waiting for home page: {e}")
        return False

# ---------------------- 🔍 IMPROVED ELEMENT FINDING ----------------------
async def find_reply_button(tweet, page):
    """Find the reply button using multiple strategies"""
    if DEBUG_MODE:
        print("🔍 Looking for reply button...")
    
    # Strategy 1: Try data-testid attribute (original approach)
    try:
        reply_button = await tweet.query_selector('div[data-testid="reply"]')
        if reply_button:
            if DEBUG_MODE:
                print("✅ Found reply button using data-testid")
            return reply_button
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Strategy 1 failed: {e}")
    
    # Strategy 2: Try aria-label attribute
    try:
        reply_button = await tweet.query_selector('div[aria-label="Reply"], div[aria-label="reply"], div[aria-label="Comment"], div[aria-label="comment"]')
        if reply_button:
            if DEBUG_MODE:
                print("✅ Found reply button using aria-label")
            return reply_button
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Strategy 2 failed: {e}")
    
    # Strategy 3: Look for SVG elements that might be the reply icon
    try:
        # First, find all SVG elements in the tweet
        svg_elements = await tweet.query_selector_all('svg')
        
        if DEBUG_MODE:
            print(f"🔍 Found {len(svg_elements)} SVG elements in tweet")
        
        # Look for SVGs inside a button or clickable div
        for svg in svg_elements:
            # Check if this SVG is inside a button or clickable element
            parent = await svg.evaluate("""function(node) {
                return node.closest("[role=button]");
            }""")
            
            if parent:
                # Take a screenshot for debugging
                if DEBUG_MODE:
                    await save_screenshot(page, "potential_reply_buttons.png")
                
                # Get the parent element in a way we can interact with it
                parent_element = await tweet.evaluate("""function(tweet, svgElement) {
                    const svg = svgElement;
                    const button = svg.closest("[role=button]");
                    
                    // Check if this looks like a reply button
                    const buttonRect = button.getBoundingClientRect();
                    const tweetRect = tweet.getBoundingClientRect();
                    
                    // Reply buttons are typically at the bottom of the tweet
                    const isNearBottom = (buttonRect.top > tweetRect.top + tweetRect.height * 0.7);
                    
                    // Reply is typically the leftmost button
                    const isLeftSide = (buttonRect.left < tweetRect.left + tweetRect.width * 0.3);
                    
                    if (isNearBottom && isLeftSide) {
                        // Mark this element for identification
                        button.setAttribute("data-found-reply-button", "true");
                        return true;
                    }
                    return false;
                }""", svg)
                
                if parent_element:
                    # Now get the element we marked
                    reply_button = await tweet.query_selector('[data-found-reply-button="true"]')
                    if reply_button:
                        if DEBUG_MODE:
                            print("✅ Found reply button using SVG position heuristic")
                        return reply_button
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Strategy 3 failed: {e}")
    
    # Strategy 4: Try to find the first interactive element in the tweet footer
    try:
        # The footer is typically the last section of the tweet
        footer = await tweet.evaluate("""function(tweet) {
            // Get all direct children of the tweet
            const children = Array.from(tweet.children);
            // The footer is typically the last child or second-to-last child
            return children.length >= 2 ? children[children.length - 1] : null;
        }""")
        
        if footer:
            # Find all interactive elements in the footer
            footer_element = await tweet.query_selector(':scope > :last-child')
            if footer_element:
                buttons = await footer_element.query_selector_all('[role="button"]')
                if buttons and len(buttons) > 0:
                    # The reply button is typically the first button in the footer
                    if DEBUG_MODE:
                        print(f"✅ Found potential reply button as first button in footer (of {len(buttons)} buttons)")
                    return buttons[0]
    except Exception as e:
        if DEBUG_MODE:
            print(f"⚠️ Strategy 4 failed: {e}")
    
    # If we get here, we couldn't find the reply button
    if DEBUG_MODE:
        print("❌ Could not find reply button with any strategy")
        await save_screenshot(page, "reply_button_not_found.png")
    
    return None

# ---------------------- 🔄 MODAL HANDLING ----------------------
async def wait_for_reply_dialog(page, timeout=DIALOG_DETECTION_TIMEOUT):
    """Wait for the reply dialog to appear using multiple detection methods"""
    print("⏳ Waiting for reply dialog to appear...")
    
    # Use a timeout approach instead of relying on wait_for_selector
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Method 1: Check for dialog role
            dialog = await page.query_selector('div[role="dialog"]')
            if dialog:
                print("✅ Found reply dialog using role=dialog")
                await save_screenshot(page, "dialog_detected_role.png")
                return True
            
            # Method 2: Check for specific aria labels
            post_reply = await page.query_selector('div[aria-label="Post reply"]')
            if post_reply:
                print("✅ Found reply dialog using aria-label=Post reply")
                await save_screenshot(page, "dialog_detected_aria.png")
                return True
            
            # Method 3: Look for tweet textarea
            textarea = await page.query_selector('div[data-testid="tweetTextarea_0"], div[role="textbox"]')
            if textarea:
                print("✅ Found reply dialog using textarea detection")
                await save_screenshot(page, "dialog_detected_textarea.png")
                return True
            
            # Method 4: Check for reply button in the dialog
            reply_button = await page.query_selector('div[data-testid="tweetButton"]')
            if reply_button:
                print("✅ Found reply dialog using tweet button detection")
                await save_screenshot(page, "dialog_detected_button.png")
                return True
            
            # Wait a bit before checking again
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ Error during dialog detection: {e}")
            await asyncio.sleep(0.5)
    
    print("❌ Reply dialog not detected after timeout")
    await save_screenshot(page, "dialog_detection_failed.png")
    return False

async def check_for_open_modal(page):
    """Check if a reply modal is currently open using multiple detection methods"""
    try:
        # Method 1: Check for dialog role
        dialog = await page.query_selector('div[role="dialog"]')
        if dialog:
            return True
        
        # Method 2: Check for specific aria labels
        post_reply = await page.query_selector('div[aria-label="Post reply"]')
        if post_reply:
            return True
        
        # Method 3: Look for tweet textarea
        textarea = await page.query_selector('div[data-testid="tweetTextarea_0"], div[role="textbox"]')
        if textarea:
            # Make sure this textarea is in a dialog context, not just on the main page
            in_dialog = await page.evaluate("""function() {
                const textarea = document.querySelector('div[data-testid="tweetTextarea_0"], div[role="textbox"]');
                if (!textarea) return false;
                return !!textarea.closest('div[role="dialog"]');
            }""")
            if in_dialog:
                return True
        
        # Method 4: Check for reply button in the dialog
        reply_button = await page.query_selector('div[data-testid="tweetButton"]')
        if reply_button:
            # Make sure this button is in a dialog context
            in_dialog = await page.evaluate("""function() {
                const button = document.querySelector('div[data-testid="tweetButton"]');
                if (!button) return false;
                return !!button.closest('div[role="dialog"]');
            }""")
            if in_dialog:
                return True
    except Exception:
        pass
    
    return False

async def check_for_verification_dialog(page):
    """Check if a verification dialog is open (not a reply dialog)"""
    try:
        # Check if there's a dialog open
        dialog = await page.query_selector('div[role="dialog"]')
        if not dialog:
            return False
        
        # Check if it's a reply dialog
        is_reply_dialog = await check_for_open_modal(page)
        if is_reply_dialog:
            return False
        
        # If it's a dialog but not a reply dialog, it's likely a verification dialog
        # Take a screenshot for debugging
        if DEBUG_MODE:
            await save_screenshot(page, "verification_dialog_detected.png")
        
        return True
    except Exception:
        return False

async def handle_verification_dialog(page):
    """Handle verification dialogs by clicking the appropriate button"""
    try:
        if not await check_for_verification_dialog(page):
            return False
        
        print("🔍 Verification dialog detected, attempting to handle it...")
        
        # Try to find and click buttons with common verification text
        verification_button_texts = ["Got it", "OK", "Continue", "I understand", "Yes", "Confirm"]
        
        for text in verification_button_texts:
            try:
                # Try to find a button with this text
                button = await page.query_selector(f'div[role="button"]:has-text("{text}")')
                if button:
                    print(f"✅ Found verification dialog button with text: {text}")
                    await button.click()
                    await random_delay(1, 2)
                    
                    # Check if dialog closed
                    if not await check_for_verification_dialog(page):
                        print("✅ Successfully closed verification dialog")
                        return True
            except Exception:
                continue
        
        # If no specific button found, try to find any button in the dialog
        try:
            dialog = await page.query_selector('div[role="dialog"]')
            if dialog:
                buttons = await dialog.query_selector_all('div[role="button"]')
                if buttons and len(buttons) > 0:
                    # Try clicking the first button
                    await buttons[0].click()
                    await random_delay(1, 2)
                    
                    # Check if dialog closed
                    if not await check_for_verification_dialog(page):
                        print("✅ Successfully closed verification dialog with generic button")
                        return True
        except Exception:
            pass
        
        print("⚠️ Failed to handle verification dialog automatically")
        return False
    except Exception as e:
        print(f"⚠️ Error handling verification dialog: {e}")
        return False

async def close_modal_if_open(page):
    """Close any open modals"""
    try:
        # First check if it's a verification dialog
        if await check_for_verification_dialog(page):
            await handle_verification_dialog(page)
            return True
        
        # Then check if it's a reply modal
        if await check_for_open_modal(page):
            print("⚠️ Found open reply modal, closing it")
            await page.keyboard.press("Escape")
            await random_delay(1, 2)
            
            # Check if modal is still open
            if await check_for_open_modal(page):
                print("⚠️ Failed to close modal with Escape, attempting to reload page")
                await page.reload()
                await wait_for_home_page_loaded(page)
                await random_delay(3, 5)
                return True
            return True
    except Exception as e:
        print(f"⚠️ Error closing modal: {e}")
    
    return False

# ---------------------- 🚀 REPLY SUBMISSION TECHNIQUES ----------------------
async def submit_reply_with_keyboard(page):
    """Try to submit the reply using keyboard shortcuts"""
    try:
        # Check if on Mac
        if platform.system() == "Darwin":  # Mac OS
            await page.keyboard.press("Meta+Enter")
        else:
            await page.keyboard.press("Control+Enter")
        
        # Wait to see if the reply was posted
        await random_delay(3, 5)
        
        # Check if modal is still open
        if not await check_for_open_modal(page):
            print("✅ Reply submitted successfully with keyboard shortcut")
            return True
        else:
            print("⚠️ Keyboard shortcut didn't work, modal still open")
            return False
    except Exception as e:
        print(f"⚠️ Error using keyboard shortcut: {e}")
        return False

async def submit_reply_with_button_click(page):
    """Try to submit the reply by clicking the reply/post button"""
    post_selectors = [
        'div[data-testid="tweetButton"]',
        'div[role="button"]:has-text("Reply")',
        'div[role="button"]:has-text("Post")',
        'div[role="button"]:has-text("Tweet")',
        'div[data-testid="reply"]',
        'div[aria-label="Reply"]',
        'div[aria-label*="Reply"]',
        'button:has-text("Reply")',
        'button[aria-label="Reply"]',
        'div[role="button"][tabindex="0"]:right-of(div[role="textbox"])'
    ]
    
    for selector in post_selectors:
        try:
            # First check if the selector exists
            post_button = await page.query_selector(selector)
            if post_button:
                if DEBUG_MODE:
                    print(f"✅ Found post button with selector: {selector}")
                    await save_screenshot(page, "found_post_button.png")
                
                # Try multiple methods to click the button
                for attempt in range(MAX_REPLY_ATTEMPTS):
                    try:
                        if attempt == 0:
                            # First try: normal click
                            await post_button.click()
                        elif attempt == 1:
                            # Second try: force click
                            await post_button.click(force=True)
                        else:
                            # Third try: JavaScript click
                            await page.evaluate("""function(button) {
                                button.click();
                            }""", post_button)
                        
                        # Wait to see if modal closed
                        await random_delay(2, 3)
                        if not await check_for_open_modal(page):
                            print(f"✅ Reply submitted successfully with {selector} (attempt {attempt+1})")
                            return True
                        else:
                            print(f"⚠️ Click attempt {attempt+1} didn't close modal, trying again...")
                    except Exception as click_error:
                        print(f"⚠️ Click attempt {attempt+1} failed: {click_error}")
        except Exception:
            if DEBUG_MODE:
                print(f"⚠️ Post button selector failed: {selector}")
    
    return False

async def submit_reply_with_direct_dom_manipulation(page):
    """Try to submit the reply by directly manipulating the DOM"""
    try:
        # Use JavaScript to find and click the submit button
        result = await page.evaluate("""function() {
            // Try to find the submit button using various approaches
            let submitButton = null;
            
            // Approach 1: Look for buttons with specific text
            const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
            for (const button of buttons) {
                const text = button.textContent.toLowerCase();
                if (text.includes('reply') || text.includes('post') || text.includes('tweet')) {
                    submitButton = button;
                    break;
                }
            }
            
            // Approach 2: Look for buttons in the modal footer
            if (!submitButton) {
                const modal = document.querySelector('div[role="dialog"]');
                if (modal) {
                    const modalButtons = Array.from(modal.querySelectorAll('div[role="button"]'));
                    // The submit button is typically the last button in the modal
                    if (modalButtons.length > 0) {
                        submitButton = modalButtons[modalButtons.length - 1];
                    }
                }
            }
            
            // Approach 3: Look for buttons with specific attributes
            if (!submitButton) {
                submitButton = document.querySelector('div[data-testid="tweetButton"]');
            }
            
            // If we found a button, click it
            if (submitButton) {
                submitButton.click();
                return true;
            }
            
            return false;
        }""")
        
        if result:
            # Wait to see if modal closed
            await random_delay(2, 3)
            if not await check_for_open_modal(page):
                print("✅ Reply submitted successfully with direct DOM manipulation")
                return True
            else:
                print("⚠️ DOM manipulation click didn't close modal")
        
        return False
    except Exception as e:
        print(f"⚠️ Error with direct DOM manipulation: {e}")
        return False

async def submit_reply_with_tab_navigation(page):
    """Try to submit the reply by using tab navigation to focus the submit button"""
    try:
        # First make sure we're in the text area
        text_area = await page.query_selector('div[role="textbox"]')
        if text_area:
            await text_area.focus()
            
            # Tab to the submit button (usually 1-3 tabs away)
            for i in range(5):  # Try up to 5 tabs
                await page.keyboard.press("Tab")
                await random_delay(0.5, 1)
                
                # Try pressing Enter after each tab to see if we've focused the submit button
                await page.keyboard.press("Enter")
                await random_delay(1, 2)
                
                # Check if modal closed
                if not await check_for_open_modal(page):
                    print(f"✅ Reply submitted successfully with tab navigation (tabs: {i+1})")
                    return True
            
            print("⚠️ Tab navigation didn't find the submit button")
        return False
    except Exception as e:
        print(f"⚠️ Error with tab navigation: {e}")
        return False

async def try_all_reply_submission_methods(page):
    """Try all available methods to submit a reply"""
    # Method 1: Keyboard shortcut
    if await submit_reply_with_keyboard(page):
        return True
    
    # Method 2: Button click
    if await submit_reply_with_button_click(page):
        return True
    
    # Method 3: Direct DOM manipulation
    if await submit_reply_with_direct_dom_manipulation(page):
        return True
    
    # Method 4: Tab navigation
    if await submit_reply_with_tab_navigation(page):
        return True
    
    print("❌ All reply submission methods failed")
    return False

# ---------------------- 🔄 CONTROL VARIABLES ----------------------
import signal
import sys

# Global control variables for external control
automation_should_stop = False
automation_stats_file = "automation_stats.json"

def signal_handler(signum, frame):
    """Handle stop signals"""
    global automation_should_stop
    print("\n🛑 Stop signal received. Gracefully shutting down...")
    automation_should_stop = True

# Register signal handler only if in main thread
try:
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
except ValueError:
    # Not in main thread, skip signal handler registration
    print("⚠️ Signal handlers not available in this thread context")

def update_stats(tweets_processed=0, replies_sent=0, status="Running"):
    """Update automation statistics"""
    try:
        stats = {
            "tweets_processed": tweets_processed,
            "replies_sent": replies_sent,
            "status": status,
            "last_update": time.time()
        }
        with open(automation_stats_file, "w") as f:
            json.dump(stats, f)
    except Exception as e:
        print(f"⚠️ Error updating stats: {e}")

def should_continue():
    """Check if automation should continue running"""
    return not automation_should_stop

# ---------------------- 🚀 MAIN FUNCTION ----------------------
async def main():
    """Main function to run the X automation"""
    global automation_should_stop

    # Set display environment for headless mode
    os.environ['DISPLAY'] = ':99'

    print("🤖 Starting X automation with Playwright and persistent session...")

    tweets_processed = 0
    replies_sent = 0
    
    async with async_playwright() as p:
        # Launch the browser with persistent context to maintain login session
        print(f"📂 Using persistent session from: {USER_DATA_DIR}")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,  # Always headless for server deployment
            slow_mo=50,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-extensions",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-features=VizDisplayCompositor",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding"
            ]
        )
        
        # Use the first page in the browser
        page = browser.pages[0]
        if len(browser.pages) == 0:
            page = await browser.new_page()
        
        # Set default navigation timeout
        page.set_default_timeout(30000)
        
        try:
            # Navigate to X home page
            print("🌐 Navigating to X home page...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded")
            
            # Check if we're already logged in
            is_logged_in = await check_login_status(page)
            
            # If not logged in and credentials are provided, log in
            if not is_logged_in and X_USERNAME != "your_username" and X_PASSWORD != "your_password":
                print("🔑 Using provided credentials to log in...")
                login_success = await login_to_x(page, X_USERNAME, X_PASSWORD)
                if not login_success:
                    print("⚠️ Login failed. Please check your credentials or log in manually.")
                    print("⏳ Waiting for manual login...")
            
            # If not logged in and no credentials, wait for manual login
            elif not is_logged_in:
                print("⚠️ No login credentials provided. Please log in manually.")
                print("⏳ The script will wait for you to log in...")
            
            # Wait for the home page to be fully loaded with tweets
            if not await wait_for_home_page_loaded(page):
                print("❌ Failed to load home page properly. Please check your connection and try again.")
                await browser.close()
                return
                
            # Additional wait to ensure everything is stable
            await random_delay(3, 5)
            
            # Check for any verification dialogs that might appear on startup
            await handle_verification_dialog(page)
            
            # Keep track of tweets we've already replied to
            replied_tweets = set()

            # Initialize stats
            update_stats(tweets_processed, replies_sent, "Running")

            # ---------------------- 🔁 MAIN LOOP ----------------------
            for scroll_index in range(SCROLL_COUNT):
                # Check if we should stop
                if not should_continue():
                    print("\n🛑 Stopping automation as requested...")
                    break

                print(f"\n🔁 Scroll #{scroll_index + 1}")

                # Check for and handle any verification dialogs
                await handle_verification_dialog(page)
                
                # Check for and close any open reply modals before proceeding
                await close_modal_if_open(page)
                
                # Get tweets
                tweets = await page.query_selector_all('article[data-testid="tweet"]')
                print(f"📊 Found {len(tweets)} tweets in current view")
                
                if DEBUG_MODE and len(tweets) > 0:
                    await save_screenshot(page, f"tweets_scroll_{scroll_index}.png")
                
                for tweet_index, tweet in enumerate(tweets):
                    # Check if we should stop before processing each tweet
                    if not should_continue():
                        print("\n🛑 Stopping automation as requested...")
                        break

                    try:
                        # Extract tweet text
                        tweet_text_element = await tweet.query_selector('div[data-testid="tweetText"]')
                        if not tweet_text_element:
                            if DEBUG_MODE:
                                print(f"⚠️ No tweet text found for tweet #{tweet_index}")
                            continue
                        
                        tweet_text = await tweet_text_element.inner_text()
                        tweet_text = tweet_text.strip()

                        # Update tweets processed count
                        tweets_processed += 1
                        update_stats(tweets_processed, replies_sent, "Running")

                        # Skip if empty or already replied
                        if not tweet_text or tweet_text in replied_tweets:
                            continue

                              # ---- START: Add this code block around line 650 ----
                        try:
                            # Attempt to find the author's handle element within the tweet.
                            author_element = await tweet.query_selector('div[data-testid="User-Name"] span > span:has-text("@")')
                            if not author_element:
                                # Fallback selector attempt (adjust based on actual X structure if the above fails)
                                # This looks for a link starting with '/' (like a profile link) containing a span with '@'
                                author_element = await tweet.query_selector('a[role="link"][href^="/"]:has(span:has-text("@"))')

                            if author_element:
                                author_handle = await author_element.inner_text()
                                author_handle = author_handle.strip() # Expected format: "@username"

                                # Compare the found handle with the bot's username (case-insensitive)
                                # It's safer to compare without the '@' symbol
                                if author_handle.lstrip('@').lower() == X_USERNAME.lower():
                                    if DEBUG_MODE:
                                        print(f"🚮 Skipping own tweet by {author_handle} (Tweet Index: {tweet_index})")
                                    continue # Skip the rest of the loop iteration for this tweet

                            # Optional: Handle cases where the author handle couldn't be found
                            # else:
                            #    if DEBUG_MODE:
                            #        print(f"⚠️ Could not find author handle for tweet #{tweet_index}. Proceeding with caution.")
                                # If you want to be extra safe, you could 'continue' here too,
                                # to avoid replying if the author isn't confirmed *not* to be the bot.
                                # continue

                        except Exception as author_ex:
                            if DEBUG_MODE:
                                print(f"⚠️ Error extracting author handle for tweet #{tweet_index}: {author_ex}")
                            # Optional: Decide if you want to skip ('continue') on error
                            # continue
                        # ---- END: Added code block ----
                        
                        # Check for keywords
                        if any(re.search(r'\b' + re.escape(keyword.lower()) + r'\b', tweet_text.lower()) for keyword in KEYWORDS):
                            print(f"\n🔥 Found keyword match:\n{tweet_text[:200]}")

                            # Add verification check right here
                            if not await is_verified(tweet):
                                print("❌ Not verified, skipping...")
                                continue

                            print("✅ Verified account - generating reply...")

                            # Generate reply
                            valuable_reply = await generate_valuable_reply(tweet_text)
                            print(f"💡 Reply: {valuable_reply}")
                            
                            if POST_REPLIES:
                                try:
                                    # Find reply button using our improved function
                                    await random_delay(1, 2)  # Add delay before looking for reply button
                                    
                                    if DEBUG_MODE:
                                        print(f"🔍 Analyzing tweet #{tweet_index} for reply button")
                                        await save_screenshot(page, f"tweet_{tweet_index}_before_reply.png")
                                    
                                    reply_button = await find_reply_button(tweet, page)
                                    
                                    if not reply_button:
                                        print("⚠️ Reply button not found, skipping...")
                                        continue
                                    
                                    # Scroll to make sure the button is visible
                                    await reply_button.scroll_into_view_if_needed()
                                    await random_delay()
                                    
                                    # Click the reply button
                                    try:
                                        await reply_button.click()
                                    except Exception as click_error:
                                        print(f"⚠️ Error clicking reply button: {click_error}")
                                        # Try JavaScript click as fallback
                                        try:
                                            await page.evaluate("""function(button) {
                                                button.click();
                                            }""", reply_button)
                                        except Exception:
                                            print("⚠️ JavaScript click also failed, skipping...")
                                            continue
                                    
                                    await random_delay(2, 3)
                                    
                                    # Check if reply dialog opened using our improved detection
                                    if DEBUG_MODE:
                                        await save_screenshot(page, f"after_reply_click_{tweet_index}.png")
                                    
                                    # Wait for the reply dialog to appear using our improved detection
                                    dialog_opened = await wait_for_reply_dialog(page)
                                    if not dialog_opened:
                                        print("⚠️ Reply dialog did not open, skipping...")
                                        continue
                                    
                                    # Enter reply with human-like typing
                                    reply_selectors = [
                                        'div[aria-label="Tweet text"]', 
                                        'div[data-testid="tweetTextarea_0"]',
                                        'div[role="textbox"][aria-label="Tweet text"]',
                                        'div[role="textbox"]'
                                    ]
                                    
                                    typing_success = False
                                    for selector in reply_selectors:
                                        try:
                                            if await page.query_selector(selector):
                                                if DEBUG_MODE:
                                                    print(f"✅ Found reply box with selector: {selector}")
                                                
                                                if await human_like_typing(page, selector, valuable_reply):
                                                    typing_success = True
                                                    break
                                        except Exception:
                                            if DEBUG_MODE:
                                                print(f"⚠️ Selector failed: {selector}")
                                    
                                    if not typing_success:
                                        print("⚠️ Reply box not found or typing failed, closing modal...")
                                        await close_modal_if_open(page)
                                        continue
                                    
                                    await random_delay(1, 2)
                                    
                                    # Try all available methods to submit the reply
                                    submission_start_time = time.time()
                                    submission_success = False
                                    
                                    while time.time() - submission_start_time < REPLY_SUBMISSION_TIMEOUT:
                                        if await try_all_reply_submission_methods(page):
                                            submission_success = True
                                            break
                                        
                                        # If we're still here, none of the methods worked
                                        # Wait a bit and try again
                                        await random_delay(2, 3)
                                    
                                    if submission_success:
                                        print("✅ Reply submitted successfully!")
                                        # Add to replied set
                                        replied_tweets.add(tweet_text)
                                        # Update replies sent count
                                        replies_sent += 1
                                        update_stats(tweets_processed, replies_sent, "Running")
                                        # Wait longer after posting to avoid rate limiting
                                        await random_delay(4, 7)
                                    else:
                                        print("❌ Failed to submit reply after multiple attempts")
                                        # Close the modal and continue
                                        await close_modal_if_open(page)
                                    
                                except Exception as e:
                                    print(f"⚠️ Error during reply process: {e}")
                                    # Try to close any open dialogs
                                    await close_modal_if_open(page)
                    
                    except Exception as e:
                        print(f"⚠️ Error processing tweet: {e}")
                        continue
                
                # Check for and close any open modals before scrolling
                await close_modal_if_open(page)
                
                # Scroll down with randomized behavior
                scroll_amount = random.randint(500, 1000)
                await page.evaluate("""function(scrollAmount) {
                    window.scrollBy(0, scrollAmount);
                }""", scroll_amount)
                
                # Check if we should stop before scrolling
                if not should_continue():
                    print("\n🛑 Stopping automation as requested...")
                    break

                # Use longer random delays between scrolls to avoid throttling
                scroll_delay = await random_delay(MIN_SCROLL_DELAY, MAX_SCROLL_DELAY)
                print(f"⏱️ Waiting {scroll_delay:.2f}s before next scroll")
        
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            if DEBUG_MODE:
                await save_screenshot(page, "fatal_error.png")
        
        finally:
            # ---------------------- ✅ DONE ----------------------
            final_status = "Stopped" if should_continue() else "Stopped by user"
            update_stats(tweets_processed, replies_sent, final_status)
            print(f"\n🎉 Finished scrolling & replying. {final_status}")
            print("📝 Session has been saved and will be reused next time.")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
