# streamlit_app/app.py
"""
AI Research Assistant - Advanced Frontend
Author: Kundana Pooskur
M4: API & Frontend Development
Features: Beautiful minimalist UI with complete functionality
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

# ============ CUSTOM CSS FOR BEAUTIFUL UI ============
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Container */
    .main {
        padding-top: 0rem;
        max-width: 100%;
    }
    
    /* Hero Section */
    .hero-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 3rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
    }
    
    .hero-title {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    .hero-subtitle {
        color: rgba(255,255,255,0.9);
        font-size: 1.1rem;
        text-align: center;
        font-weight: 300;
    }
    
    /* Cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        border: 1px solid rgba(0,0,0,0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 20px rgba(0,0,0,0.1);
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
        background: linear-gradient(135deg, #ffd93d, #ffb73d);
        color: white;
    }
    
    .status-processing { 
        background: linear-gradient(135deg, #6a11cb, #2575fc);
        color: white;
    }
    
    .status-completed { 
        background: linear-gradient(135deg, #56ab2f, #a8e063);
        color: white;
    }
    
    .status-failed { 
        background: linear-gradient(135deg, #ff5858, #f09819);
        color: white;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 10px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
    }
    
    /* Text Input */
    .stTextArea > div > div > textarea {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 1rem;
        font-size: 1rem;
        transition: border-color 0.3s ease;
    }
    
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Progress Bar */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 10px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 2px solid #e0e0e0;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: auto;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 10px 10px 0 0;
        padding: 1rem 1.5rem;
        font-weight: 600;
        color: #666;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    
    /* Report Display - Updated Styles */
    .report-wrapper {
        background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
    }
    .report-container-styled {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9ff 100%);
        padding: 2.5rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.1);
        border: 1px solid rgba(102, 126, 234, 0.1);
        margin: 0;
    }
    .report-title-styled {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .report-content-styled {
        line-height: 1.8;
        color: #2c3e50;
        font-size: 1.05rem;
        white-space: pre-wrap;
        font-family: 'Inter', sans-serif;
    }
    .report-content-styled h1, .report-content-styled h2, .report-content-styled h3 {
        color: #667eea;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .report-divider {
        height: 3px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border: none;
        border-radius: 3px;
        margin: 1.5rem 0;
    }
    
    /* Download Buttons */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 10px;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .stDownloadButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
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
                # Task might be pending review - the endpoint should allow this now
                # But if it still returns 409, there might be an issue
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
                # Log for debugging (only in Streamlit context)
                if len(tasks) == 0:
                    print(f"[API Client] Warning: API returned 200 but empty tasks list. Response: {data}")
                return tasks
            else:
                error_msg = f"Error getting tasks: {response.status_code} - {response.text[:200]}"
                print(f"[API Client] {error_msg}")
                # Return error info in a way Streamlit can detect
                return []  # Return empty list, but we'll handle this in UI
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
        # Try health endpoint first
        response = requests.get(f"{api_client.base_url}/health", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        # If health doesn't work, try the tasks endpoint as fallback
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
        
        # Show suggestions if query is typed (FIXED - no button conflicts)
        if query and len(query) > 3:
            suggestions = api_client.get_suggestions(query)
            if suggestions:
                st.markdown("**💡 Suggestions:**")
                for suggestion in suggestions[:3]:
                    # Just display suggestions as text, not buttons
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
                    
                    # Check if result has error
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
                        # Force a rerun to show the new task immediately
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
                    "tasks": all_tasks[:5] if all_tasks else [],  # Show first 5 for debugging
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
            # Sort tasks by creation date (newest first) so latest tasks appear at top
            all_tasks = sorted(all_tasks, key=lambda x: x.get("created_at", ""), reverse=True)
            
            # Show task count
            st.caption(f"Total tasks in database: {len(all_tasks)}")
            
            # Filter tasks based on show_all toggle
            if show_all:
                display_tasks = all_tasks
                st.info(f"Showing all {len(display_tasks)} tasks")
            else:
                # Show active tasks AND failed tasks (so user can see what went wrong)
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
                    
                    # Get latest status from API for real-time updates
                    status_data = api_client.get_status(task_id)
                    if status_data:
                        # Handle both string and enum status values
                        status_value = status_data.get("status")
                        if hasattr(status_value, 'value'):
                            status = status_value.value
                        elif isinstance(status_value, str):
                            status = status_value
                        else:
                            status = str(status_value)
                        
                        progress = status_data.get("progress", progress) or 0
                        current_agent = status_data.get("current_agent", current_agent)
                        
                        # Extract error message from status response
                        status_msg = status_data.get("message", "")
                        if status.lower() == "failed":
                            # The message field contains "Task failed: {error_message}"
                            if status_msg and "Task failed:" in status_msg:
                                error_message = status_msg.replace("Task failed: ", "")
                            elif status_msg:
                                error_message = status_msg
                        elif status_msg and "error" in status_msg.lower():
                            error_message = status_msg
                    
                    # Status card
                    with st.container():
                        # Show error message prominently if task failed
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
                            # Progress visualization
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
                        
                        # Show full error details in expander for failed tasks
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
            
                # Auto-refresh
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

# ============ TAB 3: REPORTS ============
with tab3:
    col_header, col_refresh, col_test = st.columns([2, 1, 1])
    with col_header:
        st.markdown("### 📚 Research Reports")
    with col_refresh:
        if st.button("🔄 Refresh", key="refresh_reports"):
            st.rerun()
    with col_test:
        test_api = st.button("🧪 Test API", key="test_api_reports")
    st.markdown("---")
    
    # Direct API test
    if test_api:
        with st.expander("🧪 API Test Results", expanded=True):
            try:
                import requests
                response = requests.get(f"{api_client.base_url}/api/v1/tasks", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    tasks = data.get("tasks", [])
                    st.success(f"✅ API Test: Got {len(tasks)} tasks")
                    
                    tasks_with_reports = [
                        t for t in tasks 
                        if t.get("status", "").lower() in ["completed", "approved", "pending_review"]
                    ]
                    st.info(f"📋 Tasks with reports: {len(tasks_with_reports)}")
                    
                    if tasks_with_reports:
                        st.json({
                            "sample_tasks": [
                                {
                                    "task_id": t.get("task_id"),
                                    "status": t.get("status"),
                                    "query": t.get("query", "")[:50]
                                }
                                for t in tasks_with_reports[:3]
                            ]
                        })
                else:
                    st.error(f"❌ API Test Failed: {response.status_code}")
            except Exception as e:
                st.error(f"❌ API Test Exception: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    # Get all tasks with results (completed, approved, or pending_review)
    try:
        # Show loading state
        with st.spinner("Loading reports from database..."):
            all_tasks = api_client.get_all_tasks()
        
        # CRITICAL DEBUG: Show exactly what we got from API
        st.markdown("### 🔍 API Response Debug")
        st.write(f"**Tasks returned from API:** {len(all_tasks) if all_tasks else 0}")
        
        if all_tasks and len(all_tasks) > 0:
            status_breakdown = {}
            for t in all_tasks:
                status = t.get("status", "unknown")
                status_breakdown[status] = status_breakdown.get(status, 0) + 1
            st.success(f"✅ **Loaded {len(all_tasks)} tasks from API.**")
            st.json(status_breakdown)
            
            # Show first few tasks as proof
            st.write("**Sample tasks (first 3):**")
            for i, t in enumerate(all_tasks[:3], 1):
                st.write(f"{i}. Task ID: `{t.get('task_id', 'N/A')[:8]}...` | Status: `{t.get('status', 'N/A')}` | Query: {t.get('query', 'N/A')[:40]}")
        else:
            st.error("❌ **API returned 0 tasks or None!**")
            st.write(f"Type: {type(all_tasks)}, Value: {all_tasks}")
        
        # Show immediate feedback
        if not all_tasks:
            st.warning("⚠️ No tasks found. The API returned an empty list.")
            st.caption("Try submitting a new query or check if the API is running.")
            
            if st.button("🔄 Retry Loading Tasks", key="retry_tasks"):
                st.rerun()
            st.stop()
        
        # SIMPLIFIED FILTER: Just get reports directly - no complex logic
        tasks_with_reports = []
        status_counts = {}
        
        # Count statuses and filter in one pass
        for t in all_tasks:
            status = t.get("status", "")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Simple, direct check
            status_lower = str(status).lower().strip()
            if status_lower in ["pending_review", "completed", "approved"]:
                tasks_with_reports.append(t)
        
        # Show summary
        st.markdown("---")
        st.markdown("### 📊 Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Tasks", len(all_tasks))
        with col2:
            st.metric("Reports Found", len(tasks_with_reports))
        with col3:
            pending_count = len([t for t in tasks_with_reports if "pending" in str(t.get("status", "")).lower()])
            st.metric("Pending Review", pending_count)
        
        # Show status breakdown
        st.json(status_counts)
        
        # If no reports found, try direct approach
        if len(tasks_with_reports) == 0:
            st.warning("⚠️ Initial filter found 0 reports. Trying direct search...")
            for t in all_tasks:
                status = str(t.get("status", "")).lower()
                if "pending_review" in status or "completed" in status or "approved" in status:
                    tasks_with_reports.append(t)
        
        # Show what we found
        if len(tasks_with_reports) > 0:
            st.success(f"✅ **{len(tasks_with_reports)} REPORT(S) FOUND!**")
            st.balloons()
        else:
            st.error(f"❌ No reports found. Status breakdown: {status_counts}")
        
        debug_reports = st.checkbox("🔧 Show Debug Info", value=False)
        
        # ALWAYS try to display reports - even if tasks_with_reports is empty, show what we have
        st.markdown("---")
        st.markdown("### 📚 Available Reports")
        
        if len(tasks_with_reports) > 0:
            # Show count - make it VERY prominent
            pending_count = len([t for t in tasks_with_reports if "pending" in str(t.get("status", "")).lower()])
            completed_count = len([t for t in tasks_with_reports if "completed" in str(t.get("status", "")).lower() or "approved" in str(t.get("status", "")).lower()])
            
            # Always show the count prominently
            st.success(f"📋 **{len(tasks_with_reports)} report(s) available:** {pending_count} pending review ⏳, {completed_count} completed/approved ✅")
            
            # Show metrics
            col_metric1, col_metric2, col_metric3 = st.columns(3)
            with col_metric1:
                st.metric("Total Reports", len(tasks_with_reports))
            with col_metric2:
                st.metric("Pending Review", pending_count)
            with col_metric3:
                st.metric("Completed", completed_count)
            
            # Create selector with task info
            task_options = {}
            for task in tasks_with_reports:
                task_id = task.get("task_id")
                query = task.get("query", "Unknown")[:50]
                status = task.get("status", "unknown")
                status_emoji = "⏳" if "pending" in str(status).lower() else "✅"
                display_text = f"{status_emoji} {task_id[:8]}... - {query} ({status})"
                task_options[task_id] = display_text
            
            # Show list of all reports
            st.markdown("#### Available Reports:")
            for i, task in enumerate(tasks_with_reports[:15], 1):
                task_id = task.get("task_id")
                query = task.get("query", "Unknown")
                status = task.get("status", "unknown")
                status_emoji = "⏳" if "pending" in str(status).lower() else "✅"
                st.write(f"{i}. {status_emoji} **{query[:60]}** - `{task_id[:8]}...` ({status})")
            
            # Initialize selected_id
            selected_id = None
            
            if len(task_options) > 0:
                # Show a clear label
                st.markdown("#### Select a Report to View:")
                
                # Debug: Show what we're about to display
                if debug_reports:
                    with st.expander("Debug: Task Options"):
                        st.json({
                            "task_options_count": len(task_options),
                            "all_task_ids": [t.get("task_id") for t in tasks_with_reports],
                            "sample_tasks": [{"task_id": t.get("task_id")[:8], "status": t.get("status"), "query": t.get("query", "")[:30]} for t in tasks_with_reports[:5]]
                        })
                
                # Show list of available reports
                st.markdown("**Available Reports:**")
                for i, task in enumerate(tasks_with_reports[:10], 1):  # Show first 10
                    task_id = task.get("task_id")
                    query = task.get("query", "Unknown")[:60]
                    status = task.get("status", "unknown")
                    status_emoji = "⏳" if status.lower() == "pending_review" else "✅"
                    st.caption(f"{i}. {status_emoji} `{task_id[:8]}...` - {query} ({status})")
                
                # Use index for selectbox to ensure it works
                task_ids = list(task_options.keys())
                task_display_texts = [task_options[tid] for tid in task_ids]
                
                # Create selectbox with index
                selected_index = st.selectbox(
                    "Choose Report",
                    options=range(len(task_display_texts)),
                    format_func=lambda i: task_display_texts[i],
                    help="Select a report to view. Reports with ⏳ are pending review, ✅ are completed.",
                    label_visibility="visible",
                    key="report_selector"
                )
                
                # Get the actual task_id from the index
                selected_id = task_ids[selected_index] if selected_index < len(task_ids) else task_ids[0]
                
                # Show which one is selected
                st.caption(f"📄 Selected: {task_options[selected_id]}")
            else:
                # Fallback: if task_options is empty but tasks_with_reports exists, show them directly
                st.warning("⚠️ Task options dictionary is empty, but tasks exist. Showing first task.")
                if tasks_with_reports:
                    selected_id = tasks_with_reports[0].get("task_id")
                    st.info(f"Displaying: {tasks_with_reports[0].get('query', 'Unknown')[:50]}")
            
            # Load and display report if we have a selected_id
            if selected_id:
                # Get report from API
                with st.spinner("Loading report..."):
                    report_data = api_client.get_report(selected_id)
                
                # Check if there's an error
                if report_data and report_data.get("error"):
                    error_msg = report_data.get("message", "Unknown error")
                    st.error(f"❌ **Error loading report:** {error_msg}")
                    if report_data.get("status_code") == 409:
                        st.info("💡 The report endpoint returned 409 (Conflict). This might mean the task status doesn't allow report viewing yet.")
                    if debug_reports:
                        with st.expander("Error Details"):
                            st.json(report_data)
                elif report_data and report_data.get("report"):
                    # Display report with beautiful styling
                    report_text = report_data.get('report', 'No report content available')
                    
                    # Display the report in a beautiful container
                    st.markdown('<div class="report-wrapper">', unsafe_allow_html=True)
                    st.markdown(f"""
                    <div class="report-container-styled">
                        <h2 class="report-title-styled">🧬 Research Report</h2>
                        <div class="report-divider"></div>
                        <div class="report-content-styled">
{html.escape(report_text)}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Metadata section with gradient cards
                    st.markdown("---")
                    st.markdown("### 📊 Report Metrics")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Confidence score with color coding
                        confidence = report_data.get('confidence_score', 0.0)
                        conf_color = "#56ab2f" if confidence > 0.8 else "#f39c12" if confidence > 0.6 else "#e74c3c"
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, {conf_color}15 0%, {conf_color}25 100%); 
                                    padding: 1.5rem; border-radius: 15px; text-align: center;">
                            <h4 style="color: {conf_color}; margin: 0;">Confidence Score</h4>
                            <h2 style="color: {conf_color}; margin: 0.5rem 0;">{confidence:.2%}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        # Sources with icon
                        sources_count = len(report_data.get('sources', []))
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, #3498db15 0%, #3498db25 100%); 
                                    padding: 1.5rem; border-radius: 15px; text-align: center;">
                            <h4 style="color: #3498db; margin: 0;">📚 Sources</h4>
                            <h2 style="color: #3498db; margin: 0.5rem 0;">{sources_count}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        # Status with gradient
                        status = report_data.get('status', 'unknown')
                        status_color = "#56ab2f" if status == "completed" else "#764ba2"
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, {status_color}15 0%, {status_color}25 100%); 
                                    padding: 1.5rem; border-radius: 15px; text-align: center;">
                            <h4 style="color: {status_color}; margin: 0;">✅ Status</h4>
                            <h2 style="color: {status_color}; margin: 0.5rem 0; font-size: 1.5rem;">{status}</h2>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Export options
                    st.markdown("---")
                    st.markdown("### 📥 Export Options")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download as Markdown
                        st.download_button(
                            "📝 Download Markdown",
                            data=report_text,
                            file_name=f"report_{selected_id[:8]}.md",
                            mime="text/markdown",
                            use_container_width=True
                        )
                    
                    with col2:
                        # Export as JSON
                        st.download_button(
                            "📊 Download JSON",
                            data=json.dumps(report_data, indent=2),
                            file_name=f"report_{selected_id[:8]}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    
                    with col3:
                        # Copy to clipboard button
                        if st.button("📋 Copy to Clipboard", use_container_width=True):
                            st.write("Report copied! (Feature requires JavaScript)")
                else:
                    st.warning(f"⚠️ Report not yet available for task {selected_id[:8]}. It may still be processing.")
                    st.caption("💡 If the task shows 'pending_review' status, the report should be available. Try refreshing or check the HITL Review tab.")
                    if debug_reports:
                        with st.expander("Debug: Why report not available"):
                            # Try to get status
                            status_data = api_client.get_status(selected_id)
                            st.json({
                                "task_id": selected_id,
                                "status_from_api": status_data,
                                "report_api_response": report_data if report_data else "None"
                            })
        else:
            st.info("No reports available yet. Reports will appear here once your research tasks are complete or pending review.")
            st.caption("💡 Tasks with status 'pending_review', 'completed', or 'approved' should appear here.")
            
            # Always show debug info if no reports
            with st.expander("🔍 Diagnostic Information", expanded=True):
                st.json({
                    "all_tasks_count": len(all_tasks),
                    "all_task_statuses": [t.get("status") for t in all_tasks],
                    "filtered_count": len(tasks_with_reports),
                    "api_url": f"{api_client.base_url}/api/v1/tasks",
                    "sample_tasks": [
                        {
                            "task_id": t.get("task_id")[:8] + "...",
                            "status": t.get("status"),
                            "query": t.get("query", "")[:40]
                        }
                        for t in all_tasks[:5]
                    ] if all_tasks else []
                })
                st.caption("💡 If you see tasks above but 'filtered_count' is 0, check that status values match exactly.")
    except Exception as e:
        st.error(f"❌ Error loading reports: {str(e)}")
        st.caption("This might indicate the API is not accessible or there's a connection issue.")
        with st.expander("🔍 Full Error Details", expanded=True):
            st.exception(e)
            st.json({
                "api_url": f"{api_client.base_url}/api/v1/tasks",
                "error_type": type(e).__name__,
                "error_message": str(e)
            })
        if st.button("🔄 Retry Loading Reports", key="retry_reports"):
            st.rerun()

# ============ TAB 4: HITL REVIEW ============
with tab4:
    st.markdown("### ✅ Human-in-the-Loop Review")
    st.markdown("---")
    
    # Get tasks with pending_review status from database
    pending_review_tasks = api_client.get_all_tasks(status="pending_review")
    
    if pending_review_tasks:
        # Create selector
        task_options = {}
        for task in pending_review_tasks:
            task_id = task.get("task_id")
            query = task.get("query", "Unknown")[:50]
            task_options[task_id] = f"{task_id[:8]}... - {query}"
        
        selected_review_id = st.selectbox(
            "Select Report for Review",
            options=list(task_options.keys()),
            format_func=lambda x: task_options[x]
        )
        
        if selected_review_id:
            # Get report from API
            report_data = api_client.get_report(selected_review_id)
            
            if report_data:
                report_text = report_data.get('report', 'No content available')
                confidence = report_data.get('confidence_score', 0.0)
                
                # Show report info
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Confidence Score", f"{confidence:.2%}")
                with col2:
                    st.metric("Sources", len(report_data.get('sources', [])))
            
            # Display report for review
                with st.expander("📄 View Full Report", expanded=True):
                    st.markdown(report_text)
            
            # Review actions
            st.markdown("### Review Decision")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Approve", type="primary", use_container_width=True, key="approve_btn"):
                    with st.spinner("Approving report..."):
                        result = api_client.submit_review(selected_review_id, "approve")
                    if result:
                        st.success("✅ Report approved! Status updated to completed.")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Failed to submit review. Please try again.")
            
            with col2:
                st.info("💡 Edit functionality coming soon. For now, you can reject and resubmit.")
            
            with col3:
                feedback = st.text_area(
                    "Rejection Reason (Required for Reject)",
                    placeholder="Enter reason for rejection...",
                    key="reject_feedback"
                )
                if st.button("❌ Reject", use_container_width=True, key="reject_btn"):
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
            st.warning(f"Report not yet available for task {selected_review_id[:8]}. It may still be processing.")
    else:
        st.info("No reports currently pending review. Reports with low confidence scores will appear here for human review.")

# ============ TAB 5: ANALYTICS DASHBOARD ============
with tab5:
    st.markdown("### 📈 Analytics Dashboard")
    st.markdown("---")
    
    # Get analytics data
    analytics = api_client.get_analytics()
    
    if analytics:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #667eea; margin: 0;">Total Queries</h3>
                <h1 style="margin: 0;">{}</h1>
                <p style="color: #999; margin: 0;">All time</p>
            </div>
            """.format(analytics.get('summary', {}).get('total_queries', 0)), 
            unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #764ba2; margin: 0;">Today's Queries</h3>
                <h1 style="margin: 0;">{}</h1>
                <p style="color: #999; margin: 0;">Last 24 hours</p>
            </div>
            """.format(analytics.get('summary', {}).get('queries_today', 0)), 
            unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #56ab2f; margin: 0;">Success Rate</h3>
                <h1 style="margin: 0;">{}%</h1>
                <p style="color: #999; margin: 0;">Completion rate</p>
            </div>
            """.format(int(analytics.get('performance', {}).get('success_rate', 0) * 100)), 
            unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="metric-card">
                <h3 style="color: #ff5858; margin: 0;">Avg Time</h3>
                <h1 style="margin: 0;">{}</h1>
                <p style="color: #999; margin: 0;">Per query</p>
            </div>
            """.format(analytics.get('performance', {}).get('average_completion_time', 'N/A')), 
            unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Popular topics chart
            if 'popular_topics' in analytics:
                topics_df = pd.DataFrame(analytics['popular_topics'])
                fig = px.bar(topics_df, x='count', y='topic', orientation='h',
                            title='Popular Research Topics',
                            color='count',
                            color_continuous_scale='Viridis')
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Daily usage trend - FIXED INDENTATION
            if 'daily_usage' in analytics and analytics['daily_usage']:
                usage_df = pd.DataFrame(analytics['daily_usage'])
                if not usage_df.empty and 'date' in usage_df.columns:
                    fig = px.line(usage_df, x='date', y='queries',
                                 title='Daily Query Trend',
                                 markers=True)
                    fig.update_traces(line_color='#667eea', line_width=3)
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No daily usage data available yet")
            else:
                st.info("Daily usage tracking will be available as you use the system")
        
        # Confidence distribution
        if 'confidence_distribution' in analytics:
            st.markdown("### Confidence Score Distribution")
            conf_data = analytics['confidence_distribution']
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("High Confidence", 
                         f"{conf_data['high']['count']} reports",
                         f"{conf_data['high']['percentage']:.1f}%")
            
            with col2:
                st.metric("Medium Confidence", 
                         f"{conf_data['medium']['count']} reports",
                         f"{conf_data['medium']['percentage']:.1f}%")
            
            with col3:
                st.metric("Low Confidence", 
                         f"{conf_data['low']['count']} reports",
                         f"{conf_data['low']['percentage']:.1f}%")
    else:
        st.info("Analytics data is currently unavailable. Using sample data for demonstration.")
        
        # Show sample analytics for demo
        st.markdown("""
        <div style="text-align: center; padding: 2rem;">
            <h2>Sample Analytics View</h2>
            <p>Analytics will be populated as you use the system</p>
        </div>
        """, unsafe_allow_html=True)

# ============ FOOTER ============
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #999; padding: 2rem 0;">
    <p>AI Research Assistant v2.0 | M4: API & Frontend Development</p>
    <p>Built with ❤️ by Kundana Pooskur | DAMG 7245</p>
</div>
""", unsafe_allow_html=True)

# ============ SIDEBAR (Hidden by default, but accessible) ============
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    
    # API Status Check
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
    
    # Session Info
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