# streamlit_app/app.py
"""
AI Research Assistant - Advanced Frontend
Author: Kundana Pooskur
M4: API & Frontend Development
Features: Beautiful dark theme UI with complete functionality
"""

import streamlit as st
import requests
import time
import json
import html
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, Optional, List
import asyncio
import websocket
import threading

# ============ PAGE CONFIGURATION ============
st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'About': "AI Research Assistant - M4 Frontend by Kundana Pooskur"
    }
)

# ============ CUSTOM CSS FOR DARK THEME UI ============
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    /* Global Dark Theme */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Dark background for main app */
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: #e0e0e0;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Container */
    .main {
        padding-top: 0rem;
        max-width: 100%;
        background: transparent;
    }
    
    /* Hero Section - Pure Purple Theme */
    .hero-container {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 20px 40px rgba(124, 58, 237, 0.3);
        border: 1px solid rgba(124, 58, 237, 0.2);
    }
    
    .hero-title {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-align: center;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .hero-subtitle {
        color: rgba(255,255,255,0.95);
        font-size: 1.1rem;
        text-align: center;
        font-weight: 300;
    }
    
    /* Dark Cards */
    .metric-card {
        background: linear-gradient(135deg, #2a2d3a 0%, #212534 100%);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        border: 1px solid rgba(139, 92, 246, 0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 24px rgba(139, 92, 246, 0.3);
        border: 1px solid rgba(139, 92, 246, 0.4);
    }
    
    /* Status Badge */
    .status-badge {
        display: inline-block;
        padding: 0.35rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-pending { 
        background: linear-gradient(135deg, #f59e0b, #f97316);
        color: white;
        box-shadow: 0 4px 8px rgba(245, 158, 11, 0.3);
    }
    
    .status-processing { 
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        box-shadow: 0 4px 8px rgba(99, 102, 241, 0.3);
    }
    
    .status-completed { 
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
    }
    
    .status-failed { 
        background: linear-gradient(135deg, #ef4444, #dc2626);
        color: white;
        box-shadow: 0 4px 8px rgba(239, 68, 68, 0.3);
    }
    
    /* Pure Purple Theme Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 10px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(147, 51, 234, 0.5);
        background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%);
    }
    
    /* Dark Text Input */
    .stTextArea > div > div > textarea {
        background: #2a2d3a;
        color: #e0e0e0;
        border-radius: 10px;
        border: 2px solid #3f4354;
        padding: 1rem;
        font-size: 1rem;
        transition: border-color 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #8b5cf6;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
    }
    
    /* Pure Purple Progress Bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #7c3aed, #a855f7);
        border-radius: 10px;
    }
    
    /* Dark Tabs - Pure Purple Selected */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 2px solid #3f4354;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: auto;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 10px 10px 0 0;
        padding: 1rem 1.5rem;
        font-weight: 600;
        color: #9ca3af;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%);
        color: white;
    }
    
    /* Animation */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    /* Dark Theme Report Display - Pure Purple */
    .report-wrapper {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
        border: 1px solid rgba(124, 58, 237, 0.2);
    }
    
    .report-container-styled {
        background: linear-gradient(135deg, #2a2d3a 0%, #212534 100%);
        padding: 2.5rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(124, 58, 237, 0.3);
        margin: 0;
    }
    
    .report-title-styled {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    
    .report-content-styled {
        line-height: 1.8;
        color: #e0e0e0;
        font-size: 1.05rem;
        white-space: pre-wrap;
        font-family: 'Inter', sans-serif;
    }
    
    .report-content-styled h1, .report-content-styled h2, .report-content-styled h3 {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .report-divider {
        height: 3px;
        background: linear-gradient(90deg, #7c3aed, #a855f7);
        border: none;
        border-radius: 3px;
        margin: 1.5rem 0;
    }
    
    /* Purple Download Buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 10px;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.3);
    }
    
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(147, 51, 234, 0.4);
    }
    
    /* Dark Theme for all Streamlit elements */
    .stSelectbox > div > div {
        background: #2a2d3a;
        color: #e0e0e0;
        border: 1px solid #3f4354;
    }
    
    .stExpander {
        background: #2a2d3a;
        border: 1px solid #3f4354;
        border-radius: 10px;
    }
    
    .stMetric {
        background: linear-gradient(135deg, #2a2d3a 0%, #212534 100%);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(139, 92, 246, 0.2);
    }
    
    /* Custom scrollbar - Pure Purple */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1a1a2e;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #7c3aed, #a855f7);
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #8b5cf6, #a855f7);
    }
</style>
""", unsafe_allow_html=True)

# ============ SESSION STATE INITIALIZATION ============
if 'tasks' not in st.session_state:
    st.session_state.tasks = {}
if 'current_task' not in st.session_state:
    st.session_state.current_task = None
if 'completed_reports' not in st.session_state:
    st.session_state.completed_reports = {}
if 'session_id' not in st.session_state:
    st.session_state.session_id = None

# ============ API CLIENT CLASS ============
class APIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    def submit_research(self, query: str, depth: str = "standard") -> Dict:
        """Submit research query to API"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/research",
                json={"query": query, "depth": depth},
                timeout=10
            )
            if response.status_code in [200, 201]:  # Accept both 200 and 201
                return response.json()
            else:
                # Return error details for better debugging
                error_detail = {
                    "error": True,
                    "status_code": response.status_code,
                    "message": response.text,
                    "detail": response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                }
                return error_detail
        except requests.exceptions.ConnectionError as e:
            return {
                "error": True,
                "connection_error": True,
                "message": f"Cannot connect to API at {self.base_url}. Make sure the FastAPI server is running."
            }
        except requests.exceptions.Timeout as e:
            return {
                "error": True,
                "timeout": True,
                "message": "Request timed out. The API may be slow or unresponsive."
            }
        except Exception as e:
            return {
                "error": True,
                "exception": str(e),
                "message": f"Unexpected error: {str(e)}"
            }
    
    def get_status(self, task_id: str) -> Dict:
        """Get task status"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/status/{task_id}")
            return response.json() if response.status_code == 200 else None
        except:
            return None
    
    def get_report(self, task_id: str) -> Dict:
        """Get research report"""
        try:
            response = requests.get(f"{self.base_url}/api/v1/report/{task_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 409:
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "error": True,
                    "status_code": 409,
                    "message": error_detail.get("detail", {}).get("message", "Report not available"),
                    "detail": error_detail
                }
            else:
                error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "message": error_detail.get("detail", {}).get("message", f"HTTP {response.status_code}"),
                    "detail": error_detail
                }
        except requests.exceptions.ConnectionError:
            return {
                "error": True,
                "connection_error": True,
                "message": f"Cannot connect to API at {self.base_url}"
            }
        except requests.exceptions.Timeout:
            return {
                "error": True,
                "timeout": True,
                "message": "Request timed out"
            }
        except Exception as e:
            return {
                "error": True,
                "exception": str(e),
                "message": f"Error getting report: {str(e)}"
            }
    
    def submit_review(self, task_id: str, action: str, feedback: str = "") -> Dict:
        """Submit HITL review"""
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/review/{task_id}",
                json={"action": action, "task_id": task_id, "rejection_reason": feedback if action == "reject" else None}
            )
            return response.json() if response.status_code == 200 else None
        except:
            return None
    
    def get_all_tasks(self, status: Optional[str] = None) -> List[Dict]:
        """Get all tasks from database"""
        try:
            params = {"limit": 1000}  # Request a large limit to get all tasks
            if status:
                params["status"] = status
            response = requests.get(f"{self.base_url}/api/v1/tasks", params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                tasks = data.get("tasks", [])
                if len(tasks) == 0:
                    print(f"[API Client] Warning: API returned 200 but empty tasks list. Response: {data}")
                return tasks
            else:
                error_msg = f"Error getting tasks: {response.status_code} - {response.text[:200]}"
                print(f"[API Client] {error_msg}")
                return []
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: Cannot connect to {self.base_url}"
            print(f"[API Client] {error_msg}: {e}")
            return []
        except requests.exceptions.Timeout as e:
            error_msg = "Timeout error: API request took too long"
            print(f"[API Client] {error_msg}: {e}")
            return []
        except Exception as e:
            error_msg = f"Error in get_all_tasks: {e}"
            print(f"[API Client] {error_msg}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_analytics(self) -> Dict:
        """Get analytics dashboard data"""
        try:
            response = requests.get(f"{self.base_url}/api/v2/analytics/dashboard")
            return response.json() if response.status_code == 200 else None
        except:
            return None
    
    def get_suggestions(self, query: str) -> list:
        """Get search suggestions"""
        try:
            response = requests.get(f"{self.base_url}/api/v2/suggestions", params={"query": query})
            data = response.json()
            return data.get("suggestions", []) if response.status_code == 200 else []
        except:
            return []

# Initialize API client
api_client = APIClient()

# ============ API CONNECTION TEST ============
def test_api_connection():
    """Test if API is accessible"""
    try:
        response = requests.get(f"{api_client.base_url}/health", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        response = requests.get(f"{api_client.base_url}/api/v1/tasks?limit=1", timeout=5)
        if response.status_code == 200:
            return True, {"status": "healthy", "fallback": "tasks_endpoint"}
        return False, None
    except requests.exceptions.Timeout:
        return False, {"error": "timeout"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "connection_error"}
    except Exception as e:
        return False, {"error": str(e)}

# ============ HERO SECTION ============
st.markdown("""
<div class="hero-container">
    <h1 class="hero-title">🧬 AI Research Assistant</h1>
    <p class="hero-subtitle">Transform your questions into comprehensive research reports powered by advanced AI</p>
</div>
""", unsafe_allow_html=True)

# ============ MAIN TABS ============
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 New Research", "📊 Active Tasks", "📚 Reports", "✅ HITL Review", "📈 Analytics"])

# ============ TAB 1: NEW RESEARCH ============
with tab1:
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown("### Start Your Research Journey")
        st.markdown("---")
        
        # Query Input with Auto-suggestions
        query = st.text_area(
            "Research Question",
            placeholder="Example: What are the latest advances in quantum computing for cryptography?",
            height=120,
            key="research_query"
        )
        
        # Show suggestions if query is typed
        if query and len(query) > 3:
            suggestions = api_client.get_suggestions(query)
            if suggestions:
                st.markdown("**💡 Suggestions:**")
                for suggestion in suggestions[:3]:
                    st.text(f"→ {suggestion}")
        
        # Research Options
        col_a, col_b = st.columns(2)
        with col_a:
            depth = st.select_slider(
                "Research Depth",
                options=["quick", "standard", "comprehensive"],
                value="standard",
                help="Quick: 5-10 sources | Standard: 15-20 sources | Comprehensive: 25-30 sources"
            )
        
        with col_b:
            priority = st.selectbox(
                "Priority Level",
                ["Low", "Medium", "High", "Critical"],
                index=1,
                help="Higher priority tasks are processed first"
            )
        
        # API Connection Status
        api_connected, health_data = test_api_connection()
        if not api_connected:
            st.error("⚠️ **API is not running!** Please start the FastAPI server first.")
            st.code("cd ai-research-assistant\nuvicorn src.api.main:app --reload", language="bash")
            st.stop()
        
        # Submit Button
        if st.button("🚀 Start Research", type="primary", use_container_width=True):
            if query and len(query) > 10:
                with st.spinner("Submitting your research query..."):
                    result = api_client.submit_research(query, depth)
                    
                    if result and result.get("error"):
                        error_msg = result.get("message", "Unknown error")
                        if result.get("connection_error"):
                            st.error(f"❌ **Connection Error:** {error_msg}")
                            st.info("💡 **Troubleshooting:**\n1. Make sure the FastAPI server is running\n2. Check if it's running on `http://localhost:8000`\n3. Try running: `cd ai-research-assistant && uvicorn src.api.main:app --reload`")
                        elif result.get("timeout"):
                            st.error(f"❌ **Timeout Error:** {error_msg}")
                        else:
                            st.error(f"❌ **API Error:** {error_msg}")
                            if result.get("detail"):
                                with st.expander("Error Details"):
                                    st.json(result.get("detail"))
                            if result.get("status_code"):
                                st.caption(f"HTTP Status: {result.get('status_code')}")
                    elif result and result.get("task_id"):
                        task_id = result.get("task_id")
                        st.session_state.current_task = task_id
                        st.success(f"✅ Research task submitted! Task ID: `{task_id}`")
                        st.info("💡 Your task is now being processed. Check the 'Active Tasks' tab to see progress.")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Failed to submit research. No task ID was returned.")
                        if result:
                            with st.expander("Response Details (Debug)"):
                                st.json(result)
                        else:
                            st.error("No response from API. Check if the server is running.")
            else:
                st.warning("⚠️ Please enter a research question with at least 10 characters.")

# ============ TAB 2: ACTIVE TASKS ============
with tab2:
    st.markdown("### 📊 Task Monitor")
    st.markdown("---")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh (every 3 seconds)", value=True)
    
    # Show all tasks toggle
    show_all = st.checkbox("Show all tasks (including completed)", value=False)
    
    # Debug toggle
    debug_mode = st.checkbox("🔧 Debug Mode", value=False)
    
    # Get all tasks from database
    try:
        all_tasks = api_client.get_all_tasks()
        
        # Debug information
        if debug_mode:
            with st.expander("🔧 Debug Information", expanded=True):
                st.json({
                    "total_tasks": len(all_tasks),
                    "api_url": f"{api_client.base_url}/api/v1/tasks",
                    "tasks": all_tasks[:5] if all_tasks else [],
                    "status_breakdown": {
                        status: len([t for t in all_tasks if t.get("status") == status])
                        for status in set([t.get("status", "unknown") for t in all_tasks])
                    }
                })
        
        if not all_tasks:
            st.info("No tasks found in database. Start a new research query in the 'New Research' tab.")
            if st.button("🔄 Refresh"):
                st.rerun()
        else:
            all_tasks = sorted(all_tasks, key=lambda x: x.get("created_at", ""), reverse=True)
            
            st.caption(f"Total tasks in database: {len(all_tasks)}")
            
            if show_all:
                display_tasks = all_tasks
                st.info(f"Showing all {len(display_tasks)} tasks")
            else:
                display_tasks = [t for t in all_tasks if t.get("status", "").lower() not in ["completed", "approved"]]
                if len(display_tasks) < len(all_tasks):
                    completed_count = len([t for t in all_tasks if t.get("status", "").lower() in ["completed", "approved"]])
                    st.info(f"Showing {len(display_tasks)} active/failed tasks ({completed_count} completed - see Reports tab)")
            
            if display_tasks:
                for task in display_tasks:
                    task_id = task.get("task_id")
                    query = task.get("query", "Unknown query")
                    status = task.get("status", "unknown")
                    progress = task.get("progress", 0) or 0
                    current_agent = task.get("current_agent")
                    created_at = task.get("created_at", "Unknown")
                    error_message = task.get("error_message")
                    
                    status_data = api_client.get_status(task_id)
                    if status_data:
                        status_value = status_data.get("status")
                        if hasattr(status_value, 'value'):
                            status = status_value.value
                        elif isinstance(status_value, str):
                            status = status_value
                        else:
                            status = str(status_value)
                        
                        progress = status_data.get("progress", progress) or 0
                        current_agent = status_data.get("current_agent", current_agent)
                        
                        status_msg = status_data.get("message", "")
                        if status.lower() == "failed":
                            if status_msg and "Task failed:" in status_msg:
                                error_message = status_msg.replace("Task failed: ", "")
                            elif status_msg:
                                error_message = status_msg
                        elif status_msg and "error" in status_msg.lower():
                            error_message = status_msg
                    
                    with st.container():
                        if status.lower() == "failed":
                            st.error(f"❌ **Task Failed** - {error_message or 'Unknown error'}")
                        
                        col1, col2, col3 = st.columns([3, 2, 1])
                        
                        with col1:
                            st.markdown(f"**Query:** {query[:100]}{'...' if len(query) > 100 else ''}")
                            st.markdown(f"**Task ID:** `{task_id}`")
                            st.caption(f"Created: {created_at}")
                            if current_agent:
                                st.markdown(f"**Current Agent:** {current_agent}")
                            if error_message and status.lower() != "failed":
                                st.caption(f"⚠️ Error: {error_message[:100]}")
                        
                        with col2:
                            if status.lower() != "failed":
                                st.progress(progress / 100)
                                st.markdown(f"Progress: {progress}%")
                            else:
                                st.progress(0)
                                st.markdown("Progress: Failed")
                        
                        with col3:
                            status_class = status.lower().replace("_", "-")
                            st.markdown(f"<span class='status-badge status-{status_class}'>{status}</span>", 
                                      unsafe_allow_html=True)
                        
                        if status.lower() == "failed":
                            with st.expander("🔍 View Error Details & Troubleshooting", expanded=False):
                                if error_message:
                                    st.markdown("**Error Message:**")
                                    st.code(error_message, language="text")
                                else:
                                    st.warning("No error message available. Check API logs.")
                                
                                st.markdown("---")
                                st.markdown("**Common Issues & Solutions:**")
                                st.markdown("""
                                1. **Missing Dependencies**: Run `pip install -r requirements.txt` in the project directory
                                2. **Missing API Keys**: Check if OpenAI API key and Pinecone credentials are set in environment variables
                                3. **Service Connectivity**: Verify internet connection and that external services (OpenAI, Pinecone) are accessible
                                4. **Resource Limits**: Check if you've exceeded API rate limits or quotas
                                5. **Configuration**: Verify `.env` file has all required variables
                                6. **Database**: Ensure the database file exists and is writable
                                """)
                                st.caption("💡 Check the FastAPI server logs for detailed error information.")
                        
                        st.markdown("---")
            
                if auto_refresh:
                    time.sleep(3)
                    st.rerun()
            else:
                st.info("No active tasks. All tasks are completed, approved, or failed.")
                st.caption("Toggle 'Show all tasks' to see completed tasks.")
    except Exception as e:
        st.error(f"❌ Error loading tasks: {str(e)}")
        with st.expander("Debug Information"):
            st.exception(e)
        if st.button("🔄 Retry"):
            st.rerun()

# ============ TAB 3: REPORTS (FIXED) ============
with tab3:
    st.markdown("### 📚 Research Reports")
    st.markdown("---")
    
    try:
        with st.spinner("Loading reports from database..."):
            all_tasks = api_client.get_all_tasks()
        
        if not all_tasks:
            st.warning("⚠️ No tasks found. The API returned an empty list.")
            st.caption("Try submitting a new query or check if the API is running.")
            st.stop()
        
        # Filter for tasks with reports
        tasks_with_reports = []
        for t in all_tasks:
            status = str(t.get("status", "")).lower().strip()
            if status in ["pending_review", "completed", "approved"]:
                tasks_with_reports.append(t)
        
        if len(tasks_with_reports) > 0:
            # Show metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Reports", len(tasks_with_reports))
            with col2:
                pending_count = len([t for t in tasks_with_reports if "pending" in str(t.get("status", "")).lower()])
                st.metric("Pending Review", pending_count)
            with col3:
                completed_count = len([t for t in tasks_with_reports if "completed" in str(t.get("status", "")).lower() or "approved" in str(t.get("status", "")).lower()])
                st.metric("Completed", completed_count)
            
            # Create selector
            task_options = {}
            for task in tasks_with_reports:
                task_id = task.get("task_id")
                query = task.get("query", "Unknown")[:50]
                status = task.get("status", "unknown")
                status_emoji = "⏳" if "pending" in str(status).lower() else "✅"
                display_text = f"{status_emoji} {query} - {task_id[:8]}..."
                task_options[display_text] = task_id
            
            selected_display = st.selectbox(
                "Select a Report to View",
                options=list(task_options.keys()),
                help="Select a report to view. Reports with ⏳ are pending review, ✅ are completed."
            )
            
            selected_id = task_options[selected_display]
            
            # Load and display report
            if selected_id:
                with st.spinner("Loading report..."):
                    report_data = api_client.get_report(selected_id)
                
                if report_data and report_data.get("error"):
                    error_msg = report_data.get("message", "Unknown error")
                    st.error(f"❌ **Error loading report:** {error_msg}")
                elif report_data and report_data.get("report"):
                    # Get the report text
                    report_text = report_data.get('report', 'No report content available')
                    
                    # Display the report WITHOUT HTML wrapper - just use markdown
                    st.markdown("### 🧬 Research Report")
                    
                    # Display report in a nice container with dark theme
                    with st.container():
                        # Use markdown to display the report content
                        st.markdown(report_text)
                    
                    # Metadata section
                    st.markdown("---")
                    st.markdown("### 📊 Report Metrics")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        confidence = report_data.get('confidence_score', 0.0)
                        st.metric("Confidence Score", f"{confidence:.2%}")
                    
                    with col2:
                        sources_count = len(report_data.get('sources', []))
                        st.metric("Sources", sources_count)
                    
                    with col3:
                        status = report_data.get('status', 'unknown')
                        st.metric("Status", status)
                    
                    # Export options
                    st.markdown("---")
                    st.markdown("### 📥 Export Options")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.download_button(
                            "📝 Download Markdown",
                            data=report_text,
                            file_name=f"report_{selected_id[:8]}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )
                    
                    with col2:
                        st.download_button(
                            "📊 Download JSON",
                            data=json.dumps(report_data, indent=2),
                            file_name=f"report_{selected_id[:8]}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                else:
                    st.warning(f"⚠️ Report not yet available for task {selected_id[:8]}. It may still be processing.")
        else:
            st.info("No reports available yet. Reports will appear here once your research tasks are complete or pending review.")
    except Exception as e:
        st.error(f"❌ Error loading reports: {str(e)}")
        with st.expander("🔍 Full Error Details", expanded=True):
            st.exception(e)

# ============ TAB 4: HITL REVIEW ============
with tab4:
    st.markdown("### ✅ Human-in-the-Loop Review")
    st.markdown("---")
    
    pending_review_tasks = api_client.get_all_tasks(status="pending_review")
    
    if pending_review_tasks:
        task_options = {}
        for task in pending_review_tasks:
            task_id = task.get("task_id")
            query = task.get("query", "Unknown")[:50]
            task_options[f"{query} - {task_id[:8]}..."] = task_id
        
        selected_display = st.selectbox(
            "Select Report for Review",
            options=list(task_options.keys())
        )
        
        selected_review_id = task_options[selected_display]
        
        if selected_review_id:
            report_data = api_client.get_report(selected_review_id)
            
            if report_data and not report_data.get("error"):
                report_text = report_data.get('report', 'No content available')
                confidence = report_data.get('confidence_score', 0.0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Confidence Score", f"{confidence:.2%}")
                with col2:
                    st.metric("Sources", len(report_data.get('sources', [])))
                
                with st.expander("📄 View Full Report", expanded=True):
                    st.markdown(report_text)
                
                st.markdown("### Review Decision")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("✅ Approve", type="primary", use_container_width=True):
                        with st.spinner("Approving report..."):
                            result = api_client.submit_review(selected_review_id, "approve")
                        if result:
                            st.success("✅ Report approved!")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Failed to submit review.")
                
                with col2:
                    st.info("💡 Edit functionality coming soon.")
                
                with col3:
                    feedback = st.text_area(
                        "Rejection Reason",
                        placeholder="Enter reason for rejection...",
                        key="reject_feedback"
                    )
                    if st.button("❌ Reject", use_container_width=True):
                        if feedback and len(feedback.strip()) > 0:
                            with st.spinner("Rejecting report..."):
                                result = api_client.submit_review(selected_review_id, "reject", feedback)
                            if result:
                                st.warning("Report rejected.")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Failed to submit rejection.")
                        else:
                            st.error("Please provide a rejection reason.")
    else:
        st.info("No reports currently pending review.")

# ============ TAB 5: ANALYTICS DASHBOARD ============
with tab5:
    st.markdown("### 📈 Analytics Dashboard")
    st.markdown("---")
    
    analytics = api_client.get_analytics()
    
    if analytics:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #7c3aed; margin: 0;">Total Queries</h3>
                <h1 style="color: #e0e0e0; margin: 0;">{}</h1>
                <p style="color: #9ca3af; margin: 0;">All time</p>
            </div>
            """.format(analytics.get('summary', {}).get('total_queries', 0)), 
            unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #9333ea; margin: 0;">Today's Queries</h3>
                <h1 style="color: #e0e0e0; margin: 0;">{}</h1>
                <p style="color: #9ca3af; margin: 0;">Last 24 hours</p>
            </div>
            """.format(analytics.get('summary', {}).get('queries_today', 0)), 
            unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #10b981; margin: 0;">Success Rate</h3>
                <h1 style="color: #e0e0e0; margin: 0;">{}%</h1>
                <p style="color: #9ca3af; margin: 0;">Completion rate</p>
            </div>
            """.format(int(analytics.get('performance', {}).get('success_rate', 0) * 100)), 
            unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #f59e0b; margin: 0;">Avg Time</h3>
                <h1 style="color: #e0e0e0; margin: 0;">{}</h1>
                <p style="color: #9ca3af; margin: 0;">Per query</p>
            </div>
            """.format(analytics.get('performance', {}).get('average_completion_time', 'N/A')), 
            unsafe_allow_html=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'popular_topics' in analytics:
                topics_df = pd.DataFrame(analytics['popular_topics'])
                fig = px.bar(topics_df, x='count', y='topic', orientation='h',
                            title='Popular Research Topics',
                            color='count',
                            color_continuous_scale='Viridis')
                fig.update_layout(
                    height=400, 
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e0e0e0')
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if 'daily_usage' in analytics and analytics['daily_usage']:
                usage_df = pd.DataFrame(analytics['daily_usage'])
                if not usage_df.empty and 'date' in usage_df.columns:
                    fig = px.line(usage_df, x='date', y='queries',
                                 title='Daily Query Trend',
                                 markers=True)
                    fig.update_traces(line_color='#7c3aed', line_width=3)
                    fig.update_layout(
                        height=400,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e0e0e0')
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No daily usage data available yet")
            else:
                st.info("Daily usage tracking will be available as you use the system")
    else:
        st.info("Analytics data is currently unavailable.")

# ============ FOOTER ============
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #9ca3af; padding: 2rem 0;">
    <p>AI Research Assistant v2.0 - Dark Theme Edition</p>
    <p>DAMG 7245</p>
</div>
""", unsafe_allow_html=True)

# ============ SIDEBAR ============
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    try:
        response = requests.get(f"{api_client.base_url}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Connected")
            health_data = response.json()
            st.caption(f"Version: {health_data.get('version', 'N/A')}")
        else:
            st.error(f"❌ API Error ({response.status_code})")
    except requests.exceptions.ConnectionError:
        st.error("❌ API Offline")
        st.caption("Start API: uvicorn src.api.main:app --reload")
    except Exception as e:
        st.error(f"❌ API Error: {str(e)[:50]}")
    
    st.markdown("---")
    
    st.markdown("### Session Info")
    try:
        all_tasks = api_client.get_all_tasks()
        active_count = len([t for t in all_tasks if t.get("status") not in ["completed", "approved", "failed"]])
        completed_count = len([t for t in all_tasks if t.get("status") in ["completed", "approved"]])
        st.text(f"Active Tasks: {active_count}")
        st.text(f"Completed Reports: {completed_count}")
        st.text(f"Total Tasks: {len(all_tasks)}")
    except:
        st.text("Unable to load task statistics")