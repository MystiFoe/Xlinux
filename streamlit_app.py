import streamlit as st
import subprocess
import time
import os
from datetime import datetime
import json
import signal
import psutil
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global variable to hold the subprocess
automation_process = None

# Global variables to control the automation
automation_running = False
automation_stats = {
    "start_time": None,
    "tweets_processed": 0,
    "replies_sent": 0,
    "status": "Stopped"
}

# Default configuration
default_config = {
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

def load_config():
    """Load configuration from config.json"""
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = default_config.copy()
                merged_config.update(config)
                return merged_config
    except Exception as e:
        st.error(f"Error loading config: {e}")
    return default_config.copy()

def save_config(config):
    """Save configuration to config.json"""
    try:
        with open("config.json", "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving config: {e}")
        return False

def save_stats():
    """Save automation statistics to file"""
    with open("automation_stats.json", "w") as f:
        json.dump(automation_stats, f, default=str)

def load_stats():
    """Load automation statistics from file"""
    global automation_stats
    try:
        if os.path.exists("automation_stats.json"):
            with open("automation_stats.json", "r") as f:
                automation_stats.update(json.load(f))
    except Exception:
        pass

def start_automation():
    """Start the automation as a subprocess"""
    global automation_process, automation_running
    if not automation_running and automation_process is None:
        try:
            # Start the automation script as a subprocess
            env = os.environ.copy()
            env['DISPLAY'] = ':99'
            automation_process = subprocess.Popen(
                ["python3", "X-final.py"],
                cwd=os.getcwd(),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            automation_running = True
            automation_stats["status"] = "Running"
            automation_stats["start_time"] = datetime.now()
            automation_stats["process_id"] = automation_process.pid  # Store PID
            save_stats()
            return True
        except Exception as e:
            automation_stats["status"] = f"Error: {str(e)}"
            save_stats()
            return False
    return False

def stop_automation():
    """Stop the automation subprocess (like Ctrl+C)"""
    global automation_process, automation_running

    # First try to stop the tracked process
    if automation_process is not None:
        try:
            # Send SIGINT (like Ctrl+C) for graceful shutdown
            automation_process.send_signal(signal.SIGINT)

            # Wait for process to terminate, with timeout
            try:
                automation_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                automation_process.kill()
                automation_process.wait()

            automation_process = None
            automation_running = False
            automation_stats["status"] = "Stopped"
            if "process_id" in automation_stats:
                del automation_stats["process_id"]
            save_stats()
            return True
        except Exception as e:
            print(f"Error stopping tracked process: {e}")

    # If no tracked process, try to find and stop by PID from stats
    if "process_id" in automation_stats:
        try:
            pid = automation_stats["process_id"]
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                process.send_signal(signal.SIGINT)  # Like Ctrl+C

                # Wait for process to terminate
                try:
                    process.wait(timeout=10)
                except psutil.TimeoutExpired:
                    process.kill()

                automation_running = False
                automation_stats["status"] = "Stopped"
                del automation_stats["process_id"]
                save_stats()
                return True
        except Exception as e:
            print(f"Error stopping by PID: {e}")

    return False

def find_automation_process():
    """Find running X-final.py process and return its PID"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['cmdline'] and len(proc.info['cmdline']) >= 2:
                    if 'python' in proc.info['name'].lower() and 'X-final.py' in ' '.join(proc.info['cmdline']):
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception:
        pass
    return None

def check_automation_status():
    """Check if the automation process is still running"""
    global automation_process, automation_running

    # First check if we have a tracked process
    if automation_process is not None:
        if automation_process.poll() is not None:
            # Process has finished
            automation_running = False
            automation_process = None
            if automation_stats["status"] == "Running":
                automation_stats["status"] = "Stopped"
                if "process_id" in automation_stats:
                    del automation_stats["process_id"]
            save_stats()
        else:
            # Process is still running
            automation_running = True
            return

    # If no tracked process, check if there's a saved PID that's still running
    if "process_id" in automation_stats:
        try:
            pid = automation_stats["process_id"]
            if psutil.pid_exists(pid):
                # Process is still running, but we lost track of it
                automation_running = True
                automation_stats["status"] = "Running"
                save_stats()
                return
            else:
                # Process no longer exists
                automation_running = False
                automation_stats["status"] = "Stopped"
                del automation_stats["process_id"]
                save_stats()
        except Exception:
            pass

    # If status shows "Running" but no PID tracked, try to find the process
    if automation_stats.get("status") == "Running" and "process_id" not in automation_stats:
        found_pid = find_automation_process()
        if found_pid:
            automation_stats["process_id"] = found_pid
            automation_running = True
            save_stats()
            return

    # No process exists
    automation_running = False

def main():
    st.set_page_config(
        page_title="X Automation Controller",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Check automation status and load statistics
    check_automation_status()
    load_stats()

    # Header
    st.markdown("""
    <div style='text-align: center; padding: 1rem 0; margin-bottom: 2rem;'>
        <h1 style='color: #1DA1F2; margin: 0;'>X Automation Controller</h1>
        <p style='color: #657786; margin: 0.5rem 0 0 0;'>Professional automation management interface</p>
    </div>
    """, unsafe_allow_html=True)

    # Main content in columns
    col1, col2 = st.columns([3, 2], gap="large")

    with col1:
        # Status and Control Section
        with st.container():
            st.markdown("### 🎮 Control Panel")

            # Status display with better styling
            status_color_map = {
                "Running": "#00C851",
                "Stopped": "#FF4444",
                "Stopping...": "#FF8800"
            }

            current_status = automation_stats.get("status", "Stopped")
            status_color = status_color_map.get(current_status.split(" ")[0], "#FF4444")

            st.markdown(f"""
            <div style='padding: 1rem; border-radius: 8px; background-color: #f8f9fa; border-left: 4px solid {status_color}; margin: 1rem 0;'>
                <h4 style='margin: 0; color: {status_color};'>Status: {current_status}</h4>
            </div>
            """, unsafe_allow_html=True)

            # Control button with better styling
            env_vars_set = all([os.getenv("X_USERNAME"), os.getenv("X_PASSWORD"), os.getenv("OPENAI_API_KEY")])

            st.markdown("<br>", unsafe_allow_html=True)

            if st.button("🚀 Start Automation",
                        type="primary",
                        disabled=automation_running or not env_vars_set,
                        use_container_width=True):
                if not env_vars_set:
                    st.error("❌ Environment variables are not configured properly")
                elif start_automation():
                    st.success("✅ Automation started successfully")
                    st.rerun()
                else:
                    st.error("❌ Failed to start automation")

        st.markdown("<br><br>", unsafe_allow_html=True)

        # Configuration section
        with st.container():
            st.markdown("### ⚙️ Configuration")

            # Load current config
            config = load_config()

            # Environment Variables Status (collapsible)
            with st.expander("🔐 Environment Variables", expanded=False):
                env_status = {
                    "X Username": "✅" if os.getenv("X_USERNAME") else "❌",
                    "X Password": "✅" if os.getenv("X_PASSWORD") else "❌",
                    "OpenAI API Key": "✅" if os.getenv("OPENAI_API_KEY") else "❌"
                }

                for key, status in env_status.items():
                    st.markdown(f"**{key}:** {status}")

            st.markdown("<br>", unsafe_allow_html=True)

            config_changed = False

            # Keywords Configuration
            st.markdown("#### 🎯 Target Keywords")
            keywords_input = st.text_area(
                "Keywords (one per line)",
                value="\n".join(config["keywords"]),
                height=120,
                help="Tweets containing these keywords will trigger replies",
                placeholder="AI\nBlockchain\nTechnology"
            )
            new_keywords = [k.strip() for k in keywords_input.split("\n") if k.strip()]
            if new_keywords != config["keywords"]:
                config["keywords"] = new_keywords
                config_changed = True

            st.markdown("#### 🤖 AI Response Template")
            new_prompt = st.text_area(
                "OpenAI prompt template",
                value=config["reply_prompt"],
                height=120,
                help="Use {tweet_text} as placeholder for the tweet content"
            )
            if new_prompt != config["reply_prompt"]:
                config["reply_prompt"] = new_prompt
                config_changed = True

            # Organized settings in tabs
            tab1, tab2, tab3 = st.tabs(["📊 Volume", "⏱️ Timing", "🎛️ Behavior"])

            with tab1:
                new_scroll_count = st.number_input(
                    "Number of scrolls",
                    min_value=1,
                    value=config["scroll_count"],
                    help="How many times to scroll through the timeline"
                )
                if new_scroll_count != config["scroll_count"]:
                    config["scroll_count"] = new_scroll_count
                    config_changed = True

                new_max_reply_attempts = st.number_input(
                    "Max reply attempts",
                    min_value=1,
                    value=config["max_reply_attempts"],
                    help="How many times to retry posting a reply"
                )
                if new_max_reply_attempts != config["max_reply_attempts"]:
                    config["max_reply_attempts"] = new_max_reply_attempts
                    config_changed = True

            with tab2:
                col_timing1, col_timing2 = st.columns(2)

                with col_timing1:
                    st.markdown("**Scroll Delays**")
                    new_min_scroll_delay = st.number_input(
                        "Min (seconds)",
                        min_value=0.5,
                        value=float(config["min_scroll_delay"]),
                        step=0.5,
                        key="min_scroll"
                    )
                    new_max_scroll_delay = st.number_input(
                        "Max (seconds)",
                        min_value=0.5,
                        value=float(config["max_scroll_delay"]),
                        step=0.5,
                        key="max_scroll"
                    )

                with col_timing2:
                    st.markdown("**Action Delays**")
                    new_min_action_delay = st.number_input(
                        "Min (seconds)",
                        min_value=0.1,
                        max_value=10.0,
                        value=float(config["min_action_delay"]),
                        step=0.1,
                        key="min_action"
                    )
                    new_max_action_delay = st.number_input(
                        "Max (seconds)",
                        min_value=0.1,
                        max_value=10.0,
                        value=float(config["max_action_delay"]),
                        step=0.1,
                        key="max_action"
                    )

                if new_min_scroll_delay != config["min_scroll_delay"]:
                    config["min_scroll_delay"] = new_min_scroll_delay
                    config_changed = True

                if new_max_scroll_delay != config["max_scroll_delay"]:
                    config["max_scroll_delay"] = new_max_scroll_delay
                    config_changed = True

                if new_min_action_delay != config["min_action_delay"]:
                    config["min_action_delay"] = new_min_action_delay
                    config_changed = True

                if new_max_action_delay != config["max_action_delay"]:
                    config["max_action_delay"] = new_max_action_delay
                    config_changed = True

            with tab3:
                col_behavior1, col_behavior2 = st.columns(2)

                with col_behavior1:
                    new_post_replies = st.toggle(
                        "Post replies",
                        value=config["post_replies"],
                        help="Turn off for test mode"
                    )

                with col_behavior2:
                    new_debug_mode = st.toggle(
                        "Debug mode",
                        value=config["debug_mode"],
                        help="Enable detailed logging"
                    )

                if new_post_replies != config["post_replies"]:
                    config["post_replies"] = new_post_replies
                    config_changed = True

                if new_debug_mode != config["debug_mode"]:
                    config["debug_mode"] = new_debug_mode
                    config_changed = True

            st.markdown("<br>", unsafe_allow_html=True)

            # Save buttons
            col_save1, col_save2 = st.columns(2)

            with col_save1:
                if config_changed:
                    if st.button("💾 Save Configuration",
                                type="primary",
                                use_container_width=True):
                        if save_config(config):
                            st.success("✅ Configuration saved!")
                            st.rerun()

            with col_save2:
                if st.button("🔄 Reset to Defaults",
                            use_container_width=True):
                    if save_config(default_config):
                        st.success("✅ Reset to defaults!")
                        st.rerun()

    with col2:
        # Statistics Section
        st.markdown("### 📊 Performance")

        # Stats display with cards
        if automation_stats["start_time"]:
            start_time = automation_stats["start_time"]
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time)
                except:
                    start_time = None

            if start_time and automation_running:
                runtime = datetime.now() - start_time
                hours, remainder = divmod(runtime.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                runtime_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            else:
                runtime_str = "Not running"

            st.markdown(f"""
            <div style='padding: 1rem; border-radius: 8px; background-color: #f0f7ff; border: 1px solid #e1ecf7; margin: 0.5rem 0;'>
                <h4 style='margin: 0; color: #1f77b4;'>⏱️ Runtime</h4>
                <p style='margin: 0.2rem 0 0 0; font-size: 1.2rem; font-weight: bold;'>{runtime_str}</p>
            </div>
            """, unsafe_allow_html=True)

        # Metrics in styled cards
        metrics = [
            ("📝", "Tweets Processed", automation_stats.get("tweets_processed", 0), "#e8f5e8"),
            ("📤", "Replies Sent", automation_stats.get("replies_sent", 0), "#fff0e6")
        ]

        for icon, label, value, bg_color in metrics:
            st.markdown(f"""
            <div style='padding: 1rem; border-radius: 8px; background-color: {bg_color}; border: 1px solid #e1e1e1; margin: 0.5rem 0;'>
                <h4 style='margin: 0; color: #333;'>{icon} {label}</h4>
                <p style='margin: 0.2rem 0 0 0; font-size: 1.8rem; font-weight: bold; color: #333;'>{value}</p>
            </div>
            """, unsafe_allow_html=True)

        # Current Configuration Summary
        st.markdown("### 🔧 Current Settings")

        current_config = load_config()

        config_summary = f"""
        **Keywords:** {', '.join(current_config['keywords'][:3])}{'...' if len(current_config['keywords']) > 3 else ''}

        **Scroll Count:** {current_config['scroll_count']}

        **Mode:** {'Production' if current_config['post_replies'] else 'Test Mode'}

        **Debug:** {'On' if current_config['debug_mode'] else 'Off'}
        """

        st.markdown(config_summary)

        # Expandable full config
        with st.expander("📋 Full Configuration"):
            st.json(current_config)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #657786; padding: 1rem;'>
        <small>X Automation Controller v2.0 | Use responsibly within platform terms</small>
    </div>
    """, unsafe_allow_html=True)

    # Auto-refresh every 3 seconds
    time.sleep(3)
    st.rerun()

if __name__ == "__main__":
    main()