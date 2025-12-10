"""
Streamlit Web Interface for AI Research Assistant

Provides an interactive web interface for:
- Submitting research queries
- Real-time status tracking
- Report preview and editing
- HITL review interface
- Cost dashboard
"""

import streamlit as st
import requests
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
import os
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Configuration
# In Docker, use service name; locally, use localhost
API_BASE_URL = os.getenv("API_BASE_URL", os.getenv("API_SERVICE_URL", "http://localhost:8000"))
API_ENDPOINTS = {
    "research": f"{API_BASE_URL}/api/v1/research",
    "status": f"{API_BASE_URL}/api/v1/status",
    "report": f"{API_BASE_URL}/api/v1/report",
    "review": f"{API_BASE_URL}/api/v1/review",
    "health": f"{API_BASE_URL}/api/v1/health"
}

# Initialize session state
if "tasks" not in st.session_state:
    st.session_state.tasks = {}
if "current_task_id" not in st.session_state:
    st.session_state.current_task_id = None
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True  # Default to enabled


def check_api_health() -> bool:
    """Check if API is available"""
    try:
        response = requests.get(API_ENDPOINTS["health"], timeout=5)
        return response.status_code == 200
    except:
        return False


def submit_research_query(query: str, depth: str = "standard", user_id: Optional[str] = None) -> Optional[Dict]:
    """Submit a research query to the API"""
    try:
        payload = {
            "query": query,
            "depth": depth,
            "user_id": user_id
        }
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


def get_task_status(task_id: str) -> Optional[Dict]:
    """Get task status from API"""
    try:
        response = requests.get(
            f"{API_ENDPOINTS['status']}/{task_id}",
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching status: {str(e)}")
        return None


def get_report(task_id: str, format: str = "json") -> Optional[Dict]:
    """Get report from API"""
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
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching report: {str(e)}")
        return None


def submit_review(task_id: str, action: str, edited_report: Optional[str] = None, rejection_reason: Optional[str] = None) -> bool:
    """Submit HITL review"""
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
    except requests.exceptions.RequestException as e:
        st.error(f"Error submitting review: {str(e)}")
        return False


def load_cost_data() -> Optional[Dict]:
    """Load cost tracking data from JSON file and format it for display"""
    # Try multiple possible paths
    possible_paths = [
        Path("/app/logs/cost_tracking.json"),  # Docker container path
        Path("logs/cost_tracking.json"),  # Relative to current directory
        Path(__file__).parent / "logs" / "cost_tracking.json",  # Relative to streamlit_app.py
        Path(__file__).parent.parent / "logs" / "cost_tracking.json",  # Project root
    ]
    
    for cost_file in possible_paths:
        if cost_file.exists():
            try:
                # Check if file is readable
                if not cost_file.is_file():
                    continue
                with open(cost_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # The cost tracker saves data in format:
                    # { "last_updated": "...", "total_records": N, "records": [...] }
                    # We need to calculate summary stats if not present
                    if 'records' in data:
                        records = data.get('records', [])
                        
                        # Calculate totals if not present
                        total_cost = sum(r.get('cost', 0.0) for r in records)
                        total_tokens = sum(r.get('total_tokens', 0) for r in records)
                        
                        # Format data for display
                        formatted_data = {
                            'total_cost': total_cost,
                            'total_tokens': total_tokens,
                            'calls': records,  # Rename 'records' to 'calls' for consistency
                            'last_updated': data.get('last_updated', ''),
                            'total_records': len(records),
                            '_metadata': {
                                'file_path': str(cost_file),
                                'last_modified': datetime.fromtimestamp(cost_file.stat().st_mtime).isoformat()
                            }
                        }
                        return formatted_data
                    else:
                        # If data is already in display format, just add metadata
                        data['_metadata'] = {
                            'file_path': str(cost_file),
                            'last_modified': datetime.fromtimestamp(cost_file.stat().st_mtime).isoformat()
                        }
                        return data
            except Exception as e:
                # Log error for debugging but continue trying other paths
                import logging
                logging.getLogger(__name__).debug(f"Error loading cost file {cost_file}: {e}")
                continue
    
    # If we get here, no file was found - return None
    return None


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable string"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp_str


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
    created_at = status_data.get("created_at")
    updated_at = status_data.get("updated_at")
    
    # Status badge with user-friendly labels
    status_labels = {
        "queued": ("🟡", "SUBMITTED"),
        "processing": ("🔵", "PROCESSING"),
        "completed": ("🟢", "COMPLETED"),
        "failed": ("🔴", "FAILED"),
        "pending_review": ("🟠", "PENDING")
    }
    
    col1, col2 = st.columns([1, 3])
    with col1:
        status_info = status_labels.get(status, ("⚪", status.upper()))
        status_emoji, status_label = status_info
        st.markdown(f"### {status_emoji} {status_label}")
    with col2:
        if progress is not None:
            st.progress(progress / 100.0)
            st.caption(f"Progress: {progress}%")
        else:
            # Show indeterminate progress for processing tasks without specific progress
            if status == "processing":
                st.progress(0.5)  # Indeterminate progress
                st.caption("Processing...")
    
    # Status details
    if message:
        st.info(f"📝 {message}")
    
    if error:
        st.error(f"❌ Error: {error}")
    
    # Timestamps
    col1, col2 = st.columns(2)
    with col1:
        if created_at:
            st.caption(f"🕐 Created: {format_timestamp(created_at)}")
    with col2:
        if updated_at:
            st.caption(f"🕐 Updated: {format_timestamp(updated_at)}")
    
    # Note: Auto-refresh is handled at the page level, not here
    # This prevents multiple refresh triggers


def display_task_details(task_id: str):
    """Display detailed task information and report"""
    # Get status
    status_data = get_task_status(task_id)
    
    if not status_data:
        st.error("Task not found")
        return
    
    status = status_data.get("status", "unknown")
    
    # Display status
    display_task_status(task_id)
    
    st.markdown("---")
    
    # Show report if completed
    if status in ["completed", "pending_review"]:
        st.subheader("Research Report")
        
        # Get report
        report_data = get_report(task_id, format="json")
        
        if report_data:
            # Report metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                confidence = report_data.get("confidence_score", 0.0)
                st.metric("Confidence Score", f"{confidence:.2%}")
            with col2:
                sources_count = len(report_data.get("sources", []))
                st.metric("Sources", sources_count)
            with col3:
                needs_hitl = report_data.get("needs_hitl", False)
                st.metric("Needs Review", "Yes" if needs_hitl else "No")
            
            st.markdown("---")
            
            # Report content
            report_content = report_data.get("report", "")
            st.markdown(report_content)
            
            # Sources
            sources = report_data.get("sources", [])
            if sources:
                st.markdown("---")
                st.subheader("Sources")
                for source in sources:
                    with st.expander(f"Source {source.get('source_id', '?')}: {source.get('title', 'Unknown')}"):
                        st.write(f"**URL:** {source.get('url', 'N/A')}")
                        st.write(f"**Relevance Score:** {source.get('relevance_score', 0.0):.2%}")
            
            # Actions
            st.markdown("---")
            st.subheader("Download Report")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # JSON Download
                json_data = get_report(task_id, format="json")
                if json_data:
                    # Format JSON for download
                    json_str = json.dumps(json_data, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📋 Download JSON",
                        data=json_str,
                        file_name=f"report_{task_id[:8]}.json",
                        mime="application/json",
                        use_container_width=True,
                        help="Download report as structured JSON with metadata, sources, and confidence score"
                    )
            
            with col2:
                # Markdown Download
                md_data = get_report(task_id, format="markdown")
                if md_data:
                    st.download_button(
                        label="📥 Download Markdown",
                        data=md_data.get("content", ""),
                        file_name=f"report_{task_id[:8]}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        help="Download report as Markdown text with sources"
                    )
            
            with col3:
                # PDF Download
                pdf_data = get_report(task_id, format="pdf")
                if pdf_data:
                    st.download_button(
                        label="📄 Download PDF",
                        data=pdf_data.get("content", b""),
                        file_name=f"report_{task_id[:8]}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        help="Download report as formatted PDF document"
                    )
            
        else:
            st.warning("Report not available yet")
        
        # HITL Review Notice and Interface - Show for pending_review regardless of report availability
        if status == "pending_review":
            st.markdown("---")
            st.warning("⚠️ **Human Review Required** - This report requires your review before finalization.")
            
            # Get confidence from report_data if available, otherwise from status_data
            confidence = report_data.get("confidence_score", 0.0) if report_data else 0.0
            if confidence < 0.7:
                st.info(f"📊 **Confidence Score: {confidence:.2%}** - Below threshold (0.70). Review recommended.")
            
            # Display validation breakdown showing what caused deductions
            metadata = report_data.get("metadata", {}) if report_data else {}
            validation_result = metadata.get("validation_result", {})
            
            if validation_result:
                st.markdown("---")
                st.subheader("📋 Validation Breakdown")
                
                # Calculate deductions
                llm_confidence = validation_result.get("confidence", 0.0)
                final_confidence = validation_result.get("final_confidence", confidence)
                
                # Determine what deductions were applied
                invalid_citations = validation_result.get("invalid_citations", [])
                unsupported_claims = validation_result.get("unsupported_claims", [])
                has_contradictions = validation_result.get("has_contradictions", False)
                issues = validation_result.get("issues", [])
                
                deductions = []
                if invalid_citations:
                    deductions.append({
                        "reason": f"Invalid Citations ({len(invalid_citations)} found)",
                        "details": f"Citations {invalid_citations} are outside the valid source range",
                        "penalty": -0.3,
                        "icon": "❌"
                    })
                
                if len(unsupported_claims) >= 3:
                    deductions.append({
                        "reason": f"Unsupported Claims ({len(unsupported_claims)} found)",
                        "details": f"{len(unsupported_claims)} claims lack proper citations",
                        "penalty": -0.2,
                        "icon": "⚠️"
                    })
                elif unsupported_claims:
                    # Show but no penalty yet
                    deductions.append({
                        "reason": f"Unsupported Claims ({len(unsupported_claims)} found)",
                        "details": f"{len(unsupported_claims)} claims lack proper citations (no penalty: <3)",
                        "penalty": 0.0,
                        "icon": "ℹ️"
                    })
                
                if has_contradictions:
                    deductions.append({
                        "reason": "Contradictions Detected",
                        "details": "Report contains contradictory information or inconsistent claims",
                        "penalty": -0.3,
                        "icon": "⚠️"
                    })
                
                # Display confidence score breakdown
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Base Confidence", f"{llm_confidence:.2%}", 
                             help="Initial confidence score from LLM validation")
                with col2:
                    total_deduction = sum(d["penalty"] for d in deductions)
                    if total_deduction < 0:
                        st.metric("Total Deductions", f"{total_deduction:.2f}",
                                 help="Total penalty points deducted")
                    else:
                        st.metric("Total Deductions", "None")
                with col3:
                    st.metric("Final Confidence", f"{final_confidence:.2%}",
                             help="Final confidence after applying deductions")
                
                # Display deductions
                if deductions:
                    st.markdown("#### Deductions Applied:")
                    for deduction in deductions:
                        with st.expander(f"{deduction['icon']} {deduction['reason']} (-{abs(deduction['penalty']):.1f} points)" if deduction['penalty'] < 0 else f"{deduction['icon']} {deduction['reason']}"):
                            st.write(deduction['details'])
                            if deduction['reason'].startswith("Invalid Citations"):
                                st.code(f"Invalid citation numbers: {invalid_citations}", language=None)
                            elif deduction['reason'].startswith("Unsupported Claims") and len(unsupported_claims) > 0:
                                st.write("**Unsupported Claims:**")
                                for i, claim in enumerate(unsupported_claims[:5], 1):  # Show first 5
                                    st.write(f"{i}. {claim}")
                                if len(unsupported_claims) > 5:
                                    st.write(f"... and {len(unsupported_claims) - 5} more")
                
                # Display general issues
                if issues:
                    st.markdown("#### General Issues:")
                    for i, issue in enumerate(issues[:5], 1):  # Show first 5 issues
                        st.write(f"{i}. {issue}")
                    if len(issues) > 5:
                        st.write(f"... and {len(issues) - 5} more issues")
                
                # Citation coverage
                citation_coverage = validation_result.get("citation_coverage", 0.0)
                if citation_coverage > 0:
                    st.markdown(f"**Citation Coverage:** {citation_coverage:.2%}")
                
                if not deductions and not issues:
                    st.success("✅ No validation issues found. Confidence deductions are based solely on LLM assessment.")
            
            st.markdown("---")
            st.subheader("🔍 Human-in-the-Loop Review")
            
            # Review action tabs
            tab1, tab2, tab3 = st.tabs(["✅ Approve", "✏️ Edit", "❌ Reject"])
            
            # Get report content for editing (use empty string if not available)
            report_content = report_data.get("report", "") if report_data else ""
            
            with tab1:
                st.markdown("**Approve this report as-is**")
                st.markdown("The report will be finalized and marked as completed.")
                if st.button("✅ Approve Report", type="primary", use_container_width=True):
                    with st.spinner("Submitting approval..."):
                        if submit_review(task_id, "approve"):
                            st.success("✅ Report approved successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to approve report. Please try again.")
            
            with tab2:
                st.markdown("**Edit the report before approval**")
                st.markdown("Make any necessary changes to the report content.")
                if not report_content:
                    st.info("💡 **Note:** Report draft is not available. You can create a new report by typing below.")
                edited_report = st.text_area(
                    "Edit Report Content",
                    value=report_content if report_content else "Enter your report content here...",
                    height=400,
                    help="Modify the report text as needed. The edited version will be saved as the final report."
                )
                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("✏️ Submit Edited Report", type="primary"):
                        placeholder_text = "Enter your report content here..."
                        current_value = edited_report.strip()
                        original_value = report_content.strip() if report_content else placeholder_text
                        
                        if current_value and current_value != original_value:
                            with st.spinner("Submitting edited report..."):
                                if submit_review(task_id, "edit", edited_report=edited_report):
                                    st.success("✅ Report edited and approved!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to submit edited report. Please try again.")
                        else:
                            st.warning("Please make changes to the report before submitting.")
            
            with tab3:
                st.markdown("**Reject this report**")
                st.markdown("The report will be rejected and the workflow will regenerate a new report.")
                rejection_reason = st.text_area(
                    "Rejection Reason",
                    placeholder="Explain why this report is being rejected (e.g., inaccurate information, missing citations, poor quality)...",
                    height=150,
                    help="Provide a reason for rejection. This will help improve future reports."
                )
                if st.button("❌ Submit Rejection", type="primary", use_container_width=True):
                    if rejection_reason.strip():
                        with st.spinner("Submitting rejection..."):
                            if submit_review(task_id, "reject", rejection_reason=rejection_reason):
                                st.success("❌ Report rejected. A new report will be generated.")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("Failed to reject report. Please try again.")
                    else:
                        st.warning("Please provide a reason for rejection.")
    elif status == "failed":
        st.error("Task failed. Check the error message above.")
    else:
        st.info(f"Task is {status}. Report will appear here when processing is complete.")
        
        # Auto-refresh for processing tasks
        if status in ["queued", "processing", "pending_review"]:
            if st.session_state.auto_refresh:
                # Refresh task status before rerun
                refresh_task_status(task_id)
                time.sleep(3)  # Refresh every 3 seconds
                st.rerun()
            else:
                # Show manual refresh hint
                st.info("💡 Enable auto-refresh in the sidebar to see real-time progress updates")


# Sidebar
with st.sidebar:
    st.title("🔬 AI Research Assistant")
    st.markdown("---")
    
    # API Health Check
    api_healthy = check_api_health()
    if api_healthy:
        st.success("✅ API Connected")
    else:
        st.error("❌ API Unavailable")
        st.info(f"Make sure the API is running at {API_BASE_URL}")
        st.stop()
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["🏠 Home", "📊 Task History", "💰 Cost Dashboard", "⚙️ Settings"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # Auto-refresh toggle
    st.session_state.auto_refresh = st.checkbox("🔄 Auto-refresh", value=st.session_state.auto_refresh)
    
    if st.session_state.auto_refresh:
        st.caption("Auto-refreshing every 3 seconds for active tasks")


# Helper function to refresh task status
def refresh_task_status(task_id: str):
    """Refresh task status from API and update session state"""
    status_data = get_task_status(task_id)
    if status_data and task_id in st.session_state.tasks:
        st.session_state.tasks[task_id]['status'] = status_data.get('status', 'unknown')
        st.session_state.tasks[task_id]['progress'] = status_data.get('progress')
        st.session_state.tasks[task_id]['message'] = status_data.get('message')


# Main Content
if page == "🏠 Home":
    st.title("Research Query Submission")
    
    # Refresh button - more visible
    col1, col2, col3 = st.columns([8, 1, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, help="Refresh current task status"):
            # Refresh current task if exists
            if st.session_state.current_task_id:
                refresh_task_status(st.session_state.current_task_id)
            st.rerun()
    
    st.markdown("Submit a research question to generate an AI-powered research report with citations.")
    
    # Query Form
    with st.form("research_form", clear_on_submit=True):
        query = st.text_area(
            "Research Question",
            placeholder="e.g., What are the latest advances in transformer architectures?",
            height=100,
            help="Enter your research question (10-500 characters)"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            depth = st.selectbox(
                "Research Depth",
                ["quick", "standard", "comprehensive"],
                index=1,
                help="Quick: Fast results, Standard: Balanced, Comprehensive: Thorough analysis"
            )
        with col2:
            user_id = st.text_input(
                "User ID (Optional)",
                placeholder="user_123",
                help="Optional identifier for tracking"
            )
        
        submitted = st.form_submit_button("Submit Research Query", type="primary", use_container_width=True)
        
        if submitted:
            if not query or len(query) < 10:
                st.error("Please enter a research question (minimum 10 characters)")
            elif len(query) > 500:
                st.error("Research question is too long (maximum 500 characters)")
            else:
                with st.spinner("Submitting research query..."):
                    result = submit_research_query(query, depth, user_id if user_id else None)
                    
                    if result:
                        task_id = result.get("task_id")
                        st.session_state.current_task_id = task_id
                        st.session_state.tasks[task_id] = {
                            "query": query,
                            "depth": depth,
                            "status": result.get("status"),
                            "created_at": result.get("created_at"),
                            "user_id": user_id
                        }
                        st.success(f"✅ Research task created! Task ID: `{task_id}`")
                        st.rerun()  # Refresh to show task details immediately
    
    # Current Task Status and Details - Show on Home page
    if st.session_state.current_task_id:
        st.markdown("---")
        st.subheader("Current Task")
        # Refresh status before displaying
        refresh_task_status(st.session_state.current_task_id)
        
        # Display full task details (moved from Task History)
        display_task_details(st.session_state.current_task_id)
        
        # Auto-refresh if task is still processing
        task = st.session_state.tasks.get(st.session_state.current_task_id, {})
        if task.get('status') in ['queued', 'processing', 'pending_review'] and st.session_state.auto_refresh:
            time.sleep(3)
            st.rerun()


elif page == "📊 Task History":
    st.title("Task History")
    st.markdown("View completed research tasks")
    
    # Refresh button - more visible
    col1, col2, col3 = st.columns([8, 1, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, help="Refresh all task statuses"):
            # Refresh all task statuses
            for task_id in list(st.session_state.tasks.keys()):
                refresh_task_status(task_id)
            st.rerun()
    
    # Task Selection - Only show completed tasks
    if st.session_state.tasks:
        # Filter to only completed tasks
        completed_task_ids = []
        for task_id in st.session_state.tasks.keys():
            task = st.session_state.tasks.get(task_id, {})
            # Refresh status to get latest
            refresh_task_status(task_id)
            task = st.session_state.tasks.get(task_id, {})
            if task.get('status') == 'completed':
                completed_task_ids.append(task_id)
        
        if completed_task_ids:
            def format_task_option(task_id):
                """Format task option for dropdown with full text"""
                task = st.session_state.tasks.get(task_id, {})
                query = task.get('query', 'Unknown')
                created_at = task.get('created_at', '')
                # Show full query and task ID
                return f"{query} | ID: {task_id}"
            
            selected_task_id = st.selectbox(
                "Select Completed Task",
                completed_task_ids,
                index=0 if completed_task_ids else None,
                format_func=format_task_option
            )
            
            if selected_task_id:
                # Refresh task status before displaying
                refresh_task_status(selected_task_id)
                display_task_details(selected_task_id)
        else:
            st.info("No completed tasks yet. Completed tasks will appear here after processing finishes.")
    else:
        st.info("No tasks yet. Submit a research query from the Home page to get started.")


elif page == "💰 Cost Dashboard":
    st.title("Cost Dashboard")
    
    # Refresh button - more visible
    col1, col2, col3 = st.columns([8, 1, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, help="Refresh cost data"):
            st.rerun()
    
    # Auto-refresh indicator
    if st.session_state.auto_refresh:
        st.info("🔄 Auto-refresh enabled (every 3 seconds)")
    
    # Load cost data
    cost_data = load_cost_data()
    
    # Note: Auto-refresh moved to end of page to avoid interrupting rendering
    
    if cost_data:
        # Show last updated time if available
        if '_metadata' in cost_data:
            metadata = cost_data['_metadata']
            last_modified = metadata.get('last_modified', '')
            if last_modified:
                try:
                    dt = datetime.fromisoformat(last_modified)
                    st.caption(f"📅 Last updated: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    st.caption(f"📅 Last updated: {last_modified}")
            file_path = metadata.get('file_path', '')
            if file_path:
                st.caption(f"📁 Data source: {file_path}")
        
        st.markdown("---")
        
        # Summary Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        total_cost = cost_data.get("total_cost", 0.0)
        total_tokens = cost_data.get("total_tokens", 0)
        total_calls = len(cost_data.get("calls", []))
        avg_cost_per_call = total_cost / total_calls if total_calls > 0 else 0
        
        with col1:
            st.metric("Total Cost", f"${total_cost:.4f}")
        with col2:
            st.metric("Total Tokens", f"{total_tokens:,}")
        with col3:
            st.metric("Total API Calls", f"{total_calls:,}")
        with col4:
            st.metric("Avg Cost/Call", f"${avg_cost_per_call:.6f}")
        
        st.markdown("---")
        
        # Cost Over Time
        calls = cost_data.get("calls", [])
        if calls:
            df = pd.DataFrame(calls)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df['cumulative_cost'] = df['cost'].cumsum()
            
            # Daily aggregation
            df['date'] = df['timestamp'].dt.date
            daily_costs = df.groupby('date')['cost'].sum().reset_index()
            daily_costs['date'] = pd.to_datetime(daily_costs['date'])
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Cost Over Time")
                fig = px.line(
                    daily_costs,
                    x='date',
                    y='cost',
                    title="Daily API Costs",
                    labels={'cost': 'Cost ($)', 'date': 'Date'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Cumulative Cost")
                fig = px.line(
                    df,
                    x='timestamp',
                    y='cumulative_cost',
                    title="Cumulative API Costs",
                    labels={'cumulative_cost': 'Cumulative Cost ($)', 'timestamp': 'Time'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Cost by Operation
            st.subheader("Cost by Operation Type")
            operation_costs = df.groupby('operation')['cost'].sum().reset_index()
            operation_costs = operation_costs.sort_values('cost', ascending=False)
            
            fig = px.bar(
                operation_costs,
                x='operation',
                y='cost',
                title="Total Cost by Operation",
                labels={'cost': 'Cost ($)', 'operation': 'Operation'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Recent Calls Table
            st.subheader("Recent API Calls")
            recent_calls = df.tail(20)[['timestamp', 'operation', 'model', 'total_tokens', 'cost']].copy()
            recent_calls['timestamp'] = recent_calls['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            recent_calls['cost'] = recent_calls['cost'].apply(lambda x: f"${x:.6f}")
            st.dataframe(recent_calls, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No cost data available")
        st.info("""
        Cost tracking data will appear here after API calls are made.
        
        **Troubleshooting:**
        - Make sure the API server is running and processing requests
        - Check if `logs/cost_tracking.json` exists in the project directory
        - Try clicking the "🔄 Refresh Data" button above
        - Verify that cost tracking is enabled in the workflow
        """)
        
        # Show possible file paths for debugging
        with st.expander("🔍 Debug: Check file locations"):
            st.code("""
Possible cost tracking file locations:
1. logs/cost_tracking.json (relative to current directory)
2. {project_root}/logs/cost_tracking.json
3. {streamlit_dir}/logs/cost_tracking.json
            """)
            st.write("**Current working directory:**", os.getcwd())
            st.write("**Streamlit app location:**", Path(__file__).parent)
            
            # Check if logs directory exists
            logs_dir = Path("logs")
            if logs_dir.exists():
                st.success(f"✅ 'logs' directory exists at: {logs_dir.absolute()}")
                cost_file = logs_dir / "cost_tracking.json"
                if cost_file.exists():
                    st.success(f"✅ Cost tracking file found: {cost_file.absolute()}")
                    st.write(f"File size: {cost_file.stat().st_size} bytes")
                else:
                    st.warning(f"❌ Cost tracking file not found: {cost_file.absolute()}")
            else:
                st.warning(f"❌ 'logs' directory not found at: {logs_dir.absolute()}")
    
    # Auto-refresh at the end (after all content is rendered)
    if st.session_state.auto_refresh:
        time.sleep(3)
        st.rerun()


elif page == "⚙️ Settings":
    st.title("Settings")
    
    # Refresh button - more visible
    col1, col2, col3 = st.columns([8, 1, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, help="Refresh page"):
            st.rerun()
    
    st.subheader("API Configuration")
    api_url = st.text_input(
        "API Base URL",
        value=API_BASE_URL,
        help="Base URL for the FastAPI backend"
    )
    
    if st.button("Update API URL"):
        os.environ["API_BASE_URL"] = api_url
        st.success("API URL updated! Please refresh the page.")
        st.rerun()
    
    st.markdown("---")
    
    st.subheader("About")
    st.info("""
    **AI Research Assistant** v1.0.0
    
    A multi-agent RAG system for generating research reports with citations.
    
    Features:
    - Semantic search using Pinecone
    - Multi-agent workflow (Search → Synthesis → Validation → HITL)
    - Automated citation validation
    - Cost tracking and monitoring
    """)
    
    if st.button("Clear All Tasks", type="secondary"):
        st.session_state.tasks = {}
        st.session_state.current_task_id = None
        st.success("All tasks cleared!")
