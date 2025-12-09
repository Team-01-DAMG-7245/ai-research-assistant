"""
AI Research Assistant - Enhanced Streamlit Frontend
With HITL page and advanced features
"""

import streamlit as st
import requests
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import os
from pathlib import Path
import pandas as pd
import uuid

# Page configuration
st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# V1 Endpoints (existing)
API_ENDPOINTS = {
    "research": f"{API_BASE_URL}/api/v1/research",
    "status": f"{API_BASE_URL}/api/v1/status",
    "report": f"{API_BASE_URL}/api/v1/report",
    "review": f"{API_BASE_URL}/api/v1/review",
    "health": f"{API_BASE_URL}/api/v1/health"
}

# V2 Endpoints (enhanced features)
API_V2_ENDPOINTS = {
    "batch_research": f"{API_BASE_URL}/api/v2/research/batch",
    "stream_report": f"{API_BASE_URL}/api/v2/report/stream",
    "analytics": f"{API_BASE_URL}/api/v2/analytics/dashboard",
    "export": f"{API_BASE_URL}/api/v2/export",
    "session_create": f"{API_BASE_URL}/api/v2/session/create",
    "session_history": f"{API_BASE_URL}/api/v2/session",
    "session_add_query": f"{API_BASE_URL}/api/v2/session",
    "enhanced_review": f"{API_BASE_URL}/api/v2/review/enhanced",
    "suggestions": f"{API_BASE_URL}/api/v2/suggestions",
    "system_status": f"{API_BASE_URL}/api/v2/system/status"
}

# Initialize session state
if "tasks" not in st.session_state:
    st.session_state.tasks = {}
if "current_task_id" not in st.session_state:
    st.session_state.current_task_id = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "batch_mode" not in st.session_state:
    st.session_state.batch_mode = False
if "pending_reviews" not in st.session_state:
    st.session_state.pending_reviews = []


# API Helper Functions
def check_api_health() -> bool:
    """Check if API is available"""
    try:
        response = requests.get(API_ENDPOINTS["health"], timeout=5)
        return response.status_code == 200
    except:
        return False


def get_system_status() -> Optional[Dict]:
    """Get detailed system status (V2)"""
    try:
        response = requests.get(API_V2_ENDPOINTS["system_status"], timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None


def create_session() -> Optional[str]:
    """Create a new research session (V2)"""
    try:
        response = requests.post(API_V2_ENDPOINTS["session_create"], timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("session_id")
    except:
        pass
    return None


def get_search_suggestions(query: str) -> List[str]:
    """Get search suggestions (V2)"""
    try:
        response = requests.get(
            API_V2_ENDPOINTS["suggestions"],
            params={"query": query},
            timeout=3
        )
        if response.status_code == 200:
            return response.json().get("suggestions", [])
    except:
        pass
    return []


def submit_research_query(query: str, depth: str = "standard", session_id: Optional[str] = None) -> Optional[Dict]:
    """Submit a single research query"""
    try:
        payload = {
            "query": query,
            "depth": depth
        }
        if session_id:
            payload["session_id"] = session_id
            
        response = requests.post(
            API_ENDPOINTS["research"],
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error submitting query: {str(e)}")
        return None


def submit_batch_research(queries: List[Dict], session_id: Optional[str] = None) -> Optional[List[Dict]]:
    """Submit batch research queries (V2)"""
    try:
        payload = {
            "queries": queries,
            "session_id": session_id
        }
        response = requests.post(
            API_V2_ENDPOINTS["batch_research"],
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json().get("tasks", [])
    except:
        pass
    return None


def get_task_status(task_id: str) -> Optional[Dict]:
    """Get task status"""
    try:
        response = requests.get(
            f"{API_ENDPOINTS['status']}/{task_id}",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except:
        return None


def get_report(task_id: str, format: str = "json") -> Optional[Any]:
    """Get report"""
    try:
        response = requests.get(
            f"{API_ENDPOINTS['report']}/{task_id}",
            params={"format": format},
            timeout=10
        )
        response.raise_for_status()
        if format == "json":
            return response.json()
        elif format == "markdown":
            return {"content": response.text, "format": "markdown"}
        elif format == "pdf":
            return {"content": response.content, "format": "pdf"}
    except:
        return None


def stream_report(task_id: str):
    """Stream report generation in real-time (V2)"""
    try:
        response = requests.get(
            f"{API_V2_ENDPOINTS['stream_report']}/{task_id}",
            stream=True,
            timeout=30
        )
        if response.status_code == 200:
            return response.iter_lines()
    except:
        pass
    return None


def submit_review(task_id: str, action: str, edited_report: Optional[str] = None, 
                  rejection_reason: Optional[str] = None) -> bool:
    """Submit standard HITL review"""
    try:
        payload = {
            "action": action,
            "task_id": task_id
        }
        if edited_report:
            payload["edited_report"] = edited_report
        if rejection_reason:
            payload["rejection_reason"] = rejection_reason
        
        response = requests.post(
            f"{API_ENDPOINTS['review']}/{task_id}",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return True
    except:
        return False


def submit_enhanced_review(task_id: str, review_data: Dict) -> bool:
    """Submit enhanced review with detailed feedback (V2)"""
    try:
        response = requests.post(
            f"{API_V2_ENDPOINTS['enhanced_review']}/{task_id}",
            json=review_data,
            timeout=10
        )
        return response.status_code == 200
    except:
        return False


def export_report(task_id: str, format: str = "pdf", options: Dict = None) -> Optional[bytes]:
    """Export report with custom formatting (V2)"""
    try:
        params = {"format": format}
        if options:
            params.update(options)
        
        response = requests.get(
            f"{API_V2_ENDPOINTS['export']}/{task_id}",
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            return response.content
    except:
        pass
    return None


def get_analytics_dashboard() -> Optional[Dict]:
    """Get analytics dashboard data (V2)"""
    try:
        response = requests.get(API_V2_ENDPOINTS["analytics"], timeout=10)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None


def get_session_history(session_id: str) -> Optional[List[Dict]]:
    """Get session history (V2)"""
    try:
        response = requests.get(
            f"{API_V2_ENDPOINTS['session_history']}/{session_id}/history",
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("queries", [])
    except:
        pass
    return None


def display_task_status(task_id: str):
    """Display task status with real-time updates"""
    status_data = get_task_status(task_id)
    
    if not status_data:
        st.error("Could not fetch task status")
        return
    
    status = status_data.get("status", "unknown")
    progress = status_data.get("progress")
    message = status_data.get("message", "")
    error = status_data.get("error")
    
    # Status badge
    status_colors = {
        "queued": "🟡",
        "processing": "🔵",
        "completed": "🟢",
        "failed": "🔴",
        "pending_review": "🟠"
    }
    
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        status_emoji = status_colors.get(status, "⚪")
        st.markdown(f"### {status_emoji} {status.upper()}")
    with col2:
        if progress is not None:
            st.progress(progress / 100.0)
            st.caption(f"Progress: {progress}%")
    with col3:
        if message:
            st.info(f"📝 {message}")
    
    if error:
        st.error(f"❌ Error: {error}")


# Sidebar
with st.sidebar:
    st.title("🧬 AI Research Assistant")
    
    # System Status
    system_status = get_system_status()
    if system_status:
        col1, col2 = st.columns(2)
        with col1:
            if system_status.get("api_healthy"):
                st.success("✅ API Online")
            else:
                st.error("❌ API Offline")
        with col2:
            active_tasks = system_status.get("active_tasks", 0)
            st.metric("Active Tasks", active_tasks)
    else:
        # Fallback to simple health check
        if check_api_health():
            st.success("✅ API Connected")
        else:
            st.error("❌ API Unavailable")
            st.stop()
    
    st.divider()
    
    # Session Management
    st.subheader("📁 Session")
    if not st.session_state.session_id:
        if st.button("Start New Session"):
            session_id = create_session()
            if session_id:
                st.session_state.session_id = session_id
                st.success(f"Session created: {session_id[:8]}...")
            else:
                # Fallback: create local session
                st.session_state.session_id = str(uuid.uuid4())
                st.info("Using local session")
    else:
        st.info(f"Session: {st.session_state.session_id[:8]}...")
        if st.button("End Session"):
            st.session_state.session_id = None
            st.rerun()
    
    st.divider()
    
    # Navigation
    st.subheader("Navigation")
    page = st.radio(
        "Select Page",
        ["HomePage", "Task History", "HITL Review", "Analytics"],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Settings
    st.subheader("⚙️ Settings")
    st.session_state.auto_refresh = st.checkbox("🔄 Auto-refresh", value=st.session_state.auto_refresh)
    st.session_state.batch_mode = st.checkbox("📦 Batch Mode", value=st.session_state.batch_mode)
    
    if st.session_state.auto_refresh:
        refresh_interval = st.slider("Refresh interval (sec)", 3, 30, 7)
        st.caption(f"Auto-refreshing every {refresh_interval} seconds")


# Main Content
if page == "HomePage":
    st.title("AI Research Assistant")
    
    # Search suggestions
    search_query = st.text_input("Start typing for suggestions...", key="search_suggestions")
    if search_query and len(search_query) > 2:
        suggestions = get_search_suggestions(search_query)
        if suggestions:
            st.info("💡 Suggestions: " + " | ".join(suggestions[:5]))
    
    st.divider()
    
    # Batch Mode
    if st.session_state.batch_mode:
        st.subheader("📦 Batch Research Submission")
        st.markdown("Submit multiple research queries at once")
        
        num_queries = st.number_input("Number of queries", min_value=2, max_value=10, value=3)
        
        queries = []
        for i in range(num_queries):
            with st.expander(f"Query {i+1}"):
                query = st.text_area(f"Research Question {i+1}", key=f"batch_query_{i}")
                depth = st.selectbox(f"Depth {i+1}", ["quick", "standard", "comprehensive"], 
                                   key=f"batch_depth_{i}", index=1)
                if query:
                    queries.append({"query": query, "depth": depth})
        
        if st.button("Submit Batch", type="primary", use_container_width=True):
            if len(queries) >= 2:
                with st.spinner(f"Submitting {len(queries)} queries..."):
                    results = submit_batch_research(queries, st.session_state.session_id)
                    if results:
                        st.success(f"✅ {len(results)} tasks created!")
                        for result in results:
                            task_id = result.get("task_id")
                            st.session_state.tasks[task_id] = result
                    else:
                        # Fallback: submit individually
                        for q in queries:
                            result = submit_research_query(q["query"], q["depth"], 
                                                         st.session_state.session_id)
                            if result:
                                st.success(f"✅ Task created: {result['task_id'][:8]}...")
            else:
                st.warning("Please enter at least 2 queries")
    
    else:
        # Single Query Mode
        st.subheader("Submit Research Query")
        
        with st.form("research_form", clear_on_submit=True):
            query = st.text_area(
                "Research Question",
                placeholder="e.g., What are the latest advances in transformer architectures?",
                height=100
            )
            
            col1, col2 = st.columns(2)
            with col1:
                depth = st.selectbox(
                    "Research Depth",
                    ["quick", "standard", "comprehensive"],
                    index=1
                )
            
            submitted = st.form_submit_button("Submit Research Query", type="primary", 
                                            use_container_width=True)
            
            if submitted and len(query) >= 10:
                with st.spinner("Submitting research query..."):
                    result = submit_research_query(query, depth, st.session_state.session_id)
                    
                    if result:
                        task_id = result.get("task_id")
                        st.session_state.current_task_id = task_id
                        st.session_state.tasks[task_id] = {
                            "query": query,
                            "depth": depth,
                            "status": result.get("status"),
                            "created_at": result.get("created_at")
                        }
                        st.success(f"✅ Task created! ID: `{task_id}`")
                        st.balloons()
    
    # Current Session History
    if st.session_state.session_id:
        st.divider()
        st.subheader("📜 Session History")
        history = get_session_history(st.session_state.session_id)
        if history:
            for item in history[-5:]:  # Show last 5
                st.caption(f"• {item.get('query', 'Unknown')} - {item.get('status', 'pending')}")
        else:
            # Fallback: show from local session state
            for task_id, task in list(st.session_state.tasks.items())[-5:]:
                st.caption(f"• {task['query'][:50]}... - {task.get('status', 'pending')}")


elif page == "📊 Task History":
    st.title("Task History & Management")
    
    if st.session_state.tasks:
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            filter_status = st.selectbox("Filter by Status", 
                                        ["All", "completed", "pending_review", "processing", "failed"])
        
        # Filter tasks
        filtered_tasks = st.session_state.tasks
        if filter_status != "All":
            filtered_tasks = {k: v for k, v in filtered_tasks.items() 
                             if v.get("status") == filter_status}
        
        if filtered_tasks:
            selected_task_id = st.selectbox(
                "Select Task",
                list(filtered_tasks.keys()),
                format_func=lambda x: f"{x[:8]}... - {filtered_tasks[x].get('query', 'Unknown')[:50]}"
            )
            
            if selected_task_id:
                # Display task details
                display_task_status(selected_task_id)
                
                st.divider()
                
                # Get and display report
                status_data = get_task_status(selected_task_id)
                if status_data and status_data.get("status") in ["completed", "pending_review"]:
                    
                    report_data = get_report(selected_task_id)
                    if report_data:
                        # Report metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Confidence", f"{report_data.get('confidence_score', 0):.2%}")
                        with col2:
                            st.metric("Sources", len(report_data.get('sources', [])))
                        with col3:
                            needs_review = "Yes" if report_data.get('needs_hitl') else "No"
                            st.metric("Needs Review", needs_review)
                        
                        # Stream report option (V2)
                        if st.button("📡 Stream Report"):
                            stream = stream_report(selected_task_id)
                            if stream:
                                report_placeholder = st.empty()
                                full_report = ""
                                for line in stream:
                                    if line:
                                        full_report += line.decode() + "\n"
                                        report_placeholder.markdown(full_report)
                            else:
                                st.markdown(report_data.get('report', ''))
                        else:
                            st.markdown(report_data.get('report', ''))
                        
                        # Enhanced Export Options (V2)
                        st.divider()
                        st.subheader("📤 Export Options")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if st.button("📄 Export PDF"):
                                content = export_report(selected_task_id, "pdf")
                                if content:
                                    st.download_button(
                                        "Download PDF",
                                        data=content,
                                        file_name=f"report_{selected_task_id[:8]}.pdf",
                                        mime="application/pdf"
                                    )
                        with col2:
                            if st.button("📊 Export DOCX"):
                                content = export_report(selected_task_id, "docx")
                                if content:
                                    st.download_button(
                                        "Download DOCX",
                                        data=content,
                                        file_name=f"report_{selected_task_id[:8]}.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                    )
                        with col3:
                            if st.button("📈 Export HTML"):
                                content = export_report(selected_task_id, "html")
                                if content:
                                    st.download_button(
                                        "Download HTML",
                                        data=content,
                                        file_name=f"report_{selected_task_id[:8]}.html",
                                        mime="text/html"
                                    )
                        with col4:
                            # Standard downloads
                            json_str = json.dumps(report_data, indent=2)
                            st.download_button(
                                "📋 JSON",
                                data=json_str,
                                file_name=f"report_{selected_task_id[:8]}.json",
                                mime="application/json"
                            )
        else:
            st.info(f"No tasks found with status: {filter_status}")
    else:
        st.info("No tasks yet. Submit a research query to get started.")


elif page == "🟠 HITL Review":
    st.title("🟠 Human-In-The-Loop Review")
    st.markdown("Review and validate AI-generated research reports")
    
    # Get pending review tasks
    pending_tasks = {k: v for k, v in st.session_state.tasks.items() 
                     if v.get("status") == "pending_review"}
    
    if pending_tasks:
        st.success(f"📋 {len(pending_tasks)} report(s) pending review")
        
        selected_task_id = st.selectbox(
            "Select Report to Review",
            list(pending_tasks.keys()),
            format_func=lambda x: f"{x[:8]}... - {pending_tasks[x].get('query', 'Unknown')[:50]}"
        )
        
        if selected_task_id:
            report_data = get_report(selected_task_id)
            
            if report_data:
                # Display report info
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(f"Query: {pending_tasks[selected_task_id].get('query')}")
                with col2:
                    confidence = report_data.get('confidence_score', 0)
                    st.metric("Confidence", f"{confidence:.2%}")
                
                # Report content
                with st.expander("📄 View Report", expanded=True):
                    st.markdown(report_data.get('report', ''))
                
                # Enhanced Review Options (V2)
                st.divider()
                st.subheader("Review Options")
                
                use_enhanced = st.checkbox("Use Enhanced Review (detailed feedback)")
                
                if use_enhanced:
                    # Enhanced Review Form
                    with st.form("enhanced_review_form"):
                        st.markdown("### Detailed Review")
                        
                        # Quality ratings
                        col1, col2 = st.columns(2)
                        with col1:
                            accuracy_rating = st.slider("Accuracy", 1, 5, 3)
                            completeness_rating = st.slider("Completeness", 1, 5, 3)
                            clarity_rating = st.slider("Clarity", 1, 5, 3)
                        with col2:
                            citation_quality = st.slider("Citation Quality", 1, 5, 3)
                            relevance_rating = st.slider("Relevance", 1, 5, 3)
                            overall_rating = st.slider("Overall Quality", 1, 5, 3)
                        
                        # Specific feedback
                        feedback_text = st.text_area("Detailed Feedback", height=150)
                        
                        # Suggestions for improvement
                        suggestions = st.text_area("Suggestions for Improvement", height=100)
                        
                        # Action
                        action = st.radio("Action", ["approve", "needs_revision", "reject"])
                        
                        if action == "needs_revision":
                            edited_report = st.text_area("Edit Report", 
                                                        value=report_data.get('report', ''),
                                                        height=400)
                        
                        submitted = st.form_submit_button("Submit Enhanced Review", type="primary")
                        
                        if submitted:
                            review_data = {
                                "action": action,
                                "ratings": {
                                    "accuracy": accuracy_rating,
                                    "completeness": completeness_rating,
                                    "clarity": clarity_rating,
                                    "citation_quality": citation_quality,
                                    "relevance": relevance_rating,
                                    "overall": overall_rating
                                },
                                "feedback": feedback_text,
                                "suggestions": suggestions
                            }
                            
                            if action == "needs_revision":
                                review_data["edited_report"] = edited_report
                            
                            if submit_enhanced_review(selected_task_id, review_data):
                                st.success("✅ Enhanced review submitted!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                # Fallback to standard review
                                if submit_review(selected_task_id, action):
                                    st.success("✅ Review submitted!")
                                    time.sleep(1)
                                    st.rerun()
                
                else:
                    # Standard Review
                    tab1, tab2, tab3 = st.tabs(["✅ Approve", "✏️ Edit", "❌ Reject"])
                    
                    with tab1:
                        if st.button("Approve Report", type="primary", use_container_width=True):
                            if submit_review(selected_task_id, "approve"):
                                st.success("✅ Report approved!")
                                time.sleep(1)
                                st.rerun()
                    
                    with tab2:
                        edited_report = st.text_area("Edit Report", 
                                                    value=report_data.get('report', ''),
                                                    height=400)
                        if st.button("Submit Edited Report", type="primary"):
                            if submit_review(selected_task_id, "edit", edited_report=edited_report):
                                st.success("✅ Report edited and approved!")
                                time.sleep(1)
                                st.rerun()
                    
                    with tab3:
                        rejection_reason = st.text_area("Rejection Reason", height=100)
                        if st.button("Reject Report", type="primary"):
                            if rejection_reason and submit_review(selected_task_id, "reject", 
                                                                 rejection_reason=rejection_reason):
                                st.success("Report rejected for regeneration")
                                time.sleep(1)
                                st.rerun()
    else:
        st.info("🎉 No reports pending review!")
        st.balloons()


elif page == "📈 Analytics":
    st.title("📈 Analytics Dashboard")
    
    analytics = get_analytics_dashboard()
    
    if analytics:
        # Display V2 analytics
        st.subheader("System Analytics")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tasks", analytics.get("total_tasks", 0))
        with col2:
            st.metric("Success Rate", f"{analytics.get('success_rate', 0):.1%}")
        with col3:
            st.metric("Avg Confidence", f"{analytics.get('avg_confidence', 0):.1%}")
        with col4:
            st.metric("HITL Rate", f"{analytics.get('hitl_rate', 0):.1%}")
        
        # Charts would go here if data is available
        if analytics.get("daily_stats"):
            st.subheader("Daily Statistics")
            df = pd.DataFrame(analytics["daily_stats"])
            st.line_chart(df)
        
        if analytics.get("query_topics"):
            st.subheader("Popular Topics")
            st.bar_chart(analytics["query_topics"])
    
    else:
        # Fallback: Show local statistics
        st.subheader("Session Statistics")
        
        if st.session_state.tasks:
            total_tasks = len(st.session_state.tasks)
            completed = sum(1 for t in st.session_state.tasks.values() 
                          if t.get('status') == 'completed')
            pending = sum(1 for t in st.session_state.tasks.values() 
                        if t.get('status') == 'pending_review')
            failed = sum(1 for t in st.session_state.tasks.values() 
                       if t.get('status') == 'failed')
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tasks", total_tasks)
            with col2:
                st.metric("Completed", completed)
            with col3:
                st.metric("Pending Review", pending)
            with col4:
                st.metric("Failed", failed)
            
            # Task timeline
            st.subheader("Task Timeline")
            task_list = []
            for task_id, task in st.session_state.tasks.items():
                task_list.append({
                    "Task ID": task_id[:8],
                    "Query": task['query'][:50],
                    "Status": task.get('status', 'unknown'),
                    "Created": task.get('created_at', 'N/A')
                })
            
            if task_list:
                df = pd.DataFrame(task_list)
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No analytics data available yet. Submit some research queries to see statistics.")


# Auto-refresh logic
if st.session_state.auto_refresh:
    # Check for active tasks
    active_tasks = [t for t in st.session_state.tasks.values() 
                   if t.get('status') in ['queued', 'processing']]
    if active_tasks:
        time.sleep(7)  # Default 7 seconds, could use refresh_interval from sidebar
        st.rerun()
