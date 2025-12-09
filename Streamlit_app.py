"""
AI Research Assistant - Web Interface
Refactored implementation with same functionality
"""

import streamlit as st
import requests
import json
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import os
from dataclasses import dataclass
from enum import Enum


# Configuration
class Config:
    PAGE_TITLE = "AI Research Assistant"
    PAGE_ICON = "🔬"
    LAYOUT = "wide"
    SIDEBAR_STATE = "expanded"
    
    @staticmethod
    def get_api_base():
        return os.getenv("API_BASE_URL", os.getenv("API_SERVICE_URL", "http://localhost:8000"))
    
    @classmethod
    def get_endpoints(cls):
        base = cls.get_api_base()
        return {
            "research": f"{base}/api/v1/research",
            "status": f"{base}/api/v1/status",
            "report": f"{base}/api/v1/report",
            "review": f"{base}/api/v1/review",
            "health": f"{base}/api/v1/health"
        }


class TaskStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_REVIEW = "pending_review"


class PageType(Enum):
    HOME = "HomePage"
    HISTORY = "Task History"
    COSTS = "Cost Dashboard"
    ANALYTICS = "Analytics"


@dataclass
class ResearchTask:
    task_id: str
    query: str
    depth: str
    status: str
    created_at: str
    progress: Optional[int] = None
    message: Optional[str] = None


# Initialize page configuration
st.set_page_config(
    page_title=Config.PAGE_TITLE,
    page_icon=Config.PAGE_ICON,
    layout=Config.LAYOUT,
    initial_sidebar_state=Config.SIDEBAR_STATE
)


class SessionManager:
    """Manages session state"""
    
    @staticmethod
    def initialize():
        defaults = {
            "research_tasks": {},
            "active_task": None,
            "refresh_enabled": True
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def add_task(task_id: str, task_data: dict):
        st.session_state.research_tasks[task_id] = task_data
        st.session_state.active_task = task_id
    
    @staticmethod
    def get_task(task_id: str) -> Optional[dict]:
        return st.session_state.research_tasks.get(task_id)
    
    @staticmethod
    def update_task(task_id: str, updates: dict):
        if task_id in st.session_state.research_tasks:
            st.session_state.research_tasks[task_id].update(updates)
    
    @staticmethod
    def clear_tasks():
        st.session_state.research_tasks = {}
        st.session_state.active_task = None


class APIClient:
    """Handles all API interactions"""
    
    def __init__(self):
        self.endpoints = Config.get_endpoints()
        self.timeout_short = 5
        self.timeout_long = 10
    
    def check_health(self) -> bool:
        try:
            resp = requests.get(self.endpoints["health"], timeout=self.timeout_short)
            return resp.status_code == 200
        except:
            return False
    
    def create_research_task(self, query_text: str, research_depth: str) -> Optional[Dict]:
        try:
            data = {
                "query": query_text,
                "depth": research_depth
            }
            resp = requests.post(
                self.endpoints["research"],
                json=data,
                timeout=self.timeout_long
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as err:
            st.error(f"Failed to create research task: {str(err)}")
            return None
    
    def fetch_status(self, task_identifier: str) -> Optional[Dict]:
        try:
            resp = requests.get(
                f"{self.endpoints['status']}/{task_identifier}",
                timeout=self.timeout_short
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as err:
            st.error(f"Could not fetch task status: {str(err)}")
            return None
    
    def fetch_report(self, task_identifier: str, output_format: str = "json") -> Optional[Dict]:
        try:
            resp = requests.get(
                f"{self.endpoints['report']}/{task_identifier}",
                params={"format": output_format},
                timeout=self.timeout_long
            )
            resp.raise_for_status()
            
            if output_format == "json":
                return resp.json()
            elif output_format == "markdown":
                return {"content": resp.text, "format": "markdown"}
            elif output_format == "pdf":
                return {"content": resp.content, "format": "pdf"}
        except requests.exceptions.RequestException as err:
            st.error(f"Could not fetch report: {str(err)}")
            return None
    
    def submit_review_decision(self, task_identifier: str, decision: str, 
                               modified_content: Optional[str] = None, 
                               rejection_note: Optional[str] = None) -> bool:
        try:
            data = {"action": decision, "task_id": task_identifier}
            if modified_content:
                data["edited_report"] = modified_content
            if rejection_note:
                data["rejection_reason"] = rejection_note
            
            resp = requests.post(
                f"{self.endpoints['review']}/{task_identifier}",
                json=data,
                timeout=self.timeout_long
            )
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException as err:
            st.error(f"Review submission failed: {str(err)}")
            return False


class CostAnalyzer:
    """Handles cost tracking and analysis"""
    
    @staticmethod
    def load_cost_records() -> Optional[Dict]:
        search_paths = [
            Path("logs/cost_tracking.json"),
            Path(__file__).parent / "logs" / "cost_tracking.json",
            Path(__file__).parent.parent / "logs" / "cost_tracking.json",
        ]
        
        for path in search_paths:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as file:
                        raw_data = json.load(file)
                        
                        if 'records' in raw_data:
                            records = raw_data['records']
                            
                            return {
                                'total_cost': sum(r.get('cost', 0.0) for r in records),
                                'total_tokens': sum(r.get('total_tokens', 0) for r in records),
                                'calls': records,
                                'last_updated': raw_data.get('last_updated', ''),
                                'total_records': len(records),
                                '_metadata': {
                                    'file_path': str(path),
                                    'last_modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                                }
                            }
                        else:
                            raw_data['_metadata'] = {
                                'file_path': str(path),
                                'last_modified': datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                            }
                            return raw_data
                except Exception:
                    continue
        
        return None


class UIComponents:
    """Reusable UI components"""
    
    @staticmethod
    def format_datetime(iso_string: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return iso_string
    
    @staticmethod
    def status_indicator(status_value: str) -> tuple:
        indicators = {
            "queued": ("🟡", "SUBMITTED"),
            "processing": ("🔵", "PROCESSING"),
            "completed": ("🟢", "COMPLETED"),
            "failed": ("🔴", "FAILED"),
            "pending_review": ("🟠", "PENDING")
        }
        return indicators.get(status_value, ("⚪", status_value.upper()))
    
    @staticmethod
    def refresh_button(label: str = "🔄 Refresh"):
        cols = st.columns([8, 1, 1])
        with cols[1]:
            return st.button(label, use_container_width=True, help="Refresh data")
        return False
    
    @staticmethod
    def render_task_progress(task_data: dict):
        status_val = task_data.get("status", "unknown")
        progress_val = task_data.get("progress")
        msg = task_data.get("message", "")
        err = task_data.get("error")
        created = task_data.get("created_at")
        updated = task_data.get("updated_at")
        
        emoji, label = UIComponents.status_indicator(status_val)
        
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(f"### {emoji} {label}")
        with c2:
            if progress_val is not None:
                st.progress(progress_val / 100.0)
                st.caption(f"Progress: {progress_val}%")
            elif status_val == "processing":
                st.progress(0.5)
                st.caption("Processing...")
        
        if msg:
            st.info(f"📝 {msg}")
        
        if err:
            st.error(f"❌ Error: {err}")
        
        c1, c2 = st.columns(2)
        with c1:
            if created:
                st.caption(f"🕐 Created: {UIComponents.format_datetime(created)}")
        with c2:
            if updated:
                st.caption(f"🕐 Updated: {UIComponents.format_datetime(updated)}")


class ReportViewer:
    """Handles report display and download"""
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
    
    def display_report(self, task_id: str, report_data: dict):
        # Metrics
        c1, c2, c3 = st.columns(3)
        with c1:
            confidence = report_data.get("confidence_score", 0.0)
            st.metric("Confidence Score", f"{confidence:.2%}")
        with c2:
            sources = len(report_data.get("sources", []))
            st.metric("Sources", sources)
        with c3:
            needs_review = report_data.get("needs_hitl", False)
            st.metric("Needs Review", "Yes" if needs_review else "No")
        
        st.markdown("---")
        
        # Report content
        content = report_data.get("report", "")
        st.markdown(content)
        
        # Sources
        source_list = report_data.get("sources", [])
        if source_list:
            st.markdown("---")
            st.subheader("Sources")
            for src in source_list:
                with st.expander(f"Source {src.get('source_id', '?')}: {src.get('title', 'Unknown')}"):
                    st.write(f"**URL:** {src.get('url', 'N/A')}")
                    st.write(f"**Relevance Score:** {src.get('relevance_score', 0.0):.2%}")
        
        # Download options
        st.markdown("---")
        st.subheader("Download Report")
        self._render_download_buttons(task_id)
    
    def _render_download_buttons(self, task_id: str):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            json_report = self.api.fetch_report(task_id, "json")
            if json_report:
                json_str = json.dumps(json_report, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📋 Download JSON",
                    data=json_str,
                    file_name=f"report_{task_id[:8]}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with c2:
            md_report = self.api.fetch_report(task_id, "markdown")
            if md_report:
                st.download_button(
                    label="📥 Download Markdown",
                    data=md_report.get("content", ""),
                    file_name=f"report_{task_id[:8]}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
        
        with c3:
            pdf_report = self.api.fetch_report(task_id, "pdf")
            if pdf_report:
                st.download_button(
                    label="📄 Download PDF",
                    data=pdf_report.get("content", b""),
                    file_name=f"report_{task_id[:8]}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )


class HITLReview:
    """Human-in-the-Loop review interface"""
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
    
    def render_review_interface(self, task_id: str, report_data: Optional[dict]):
        st.markdown("---")
        st.warning("⚠️ **Human Review Required** - This report requires your review before finalization.")
        
        if report_data:
            confidence = report_data.get("confidence_score", 0.0)
            if confidence < 0.7:
                st.info(f"📊 **Confidence Score: {confidence:.2%}** - Below threshold (0.70). Review recommended.")
            
            self._show_validation_details(report_data)
        
        st.markdown("---")
        st.subheader("🔍 Human-in-the-Loop Review")
        
        tabs = st.tabs(["✅ Approve", "✏️ Edit", "❌ Reject"])
        
        report_text = report_data.get("report", "") if report_data else ""
        
        with tabs[0]:
            self._render_approve_tab(task_id)
        
        with tabs[1]:
            self._render_edit_tab(task_id, report_text)
        
        with tabs[2]:
            self._render_reject_tab(task_id)
    
    def _show_validation_details(self, report_data: dict):
        metadata = report_data.get("metadata", {})
        validation = metadata.get("validation_result", {})
        
        if not validation:
            return
        
        st.markdown("---")
        st.subheader("📋 Validation Breakdown")
        
        base_conf = validation.get("confidence", 0.0)
        final_conf = validation.get("final_confidence", 0.0)
        invalid_cites = validation.get("invalid_citations", [])
        unsupported = validation.get("unsupported_claims", [])
        contradictions = validation.get("has_contradictions", False)
        issues = validation.get("issues", [])
        
        deductions = self._calculate_deductions(invalid_cites, unsupported, contradictions)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Base Confidence", f"{base_conf:.2%}")
        with c2:
            total_deduct = sum(d["penalty"] for d in deductions)
            if total_deduct < 0:
                st.metric("Total Deductions", f"{total_deduct:.2f}")
            else:
                st.metric("Total Deductions", "None")
        with c3:
            st.metric("Final Confidence", f"{final_conf:.2%}")
        
        if deductions:
            st.markdown("#### Deductions Applied:")
            for ded in deductions:
                title = f"{ded['icon']} {ded['reason']}"
                if ded['penalty'] < 0:
                    title += f" (-{abs(ded['penalty']):.1f} points)"
                
                with st.expander(title):
                    st.write(ded['details'])
                    if "Invalid Citations" in ded['reason'] and invalid_cites:
                        st.code(f"Invalid citation numbers: {invalid_cites}", language=None)
                    elif "Unsupported Claims" in ded['reason'] and unsupported:
                        st.write("**Unsupported Claims:**")
                        for i, claim in enumerate(unsupported[:5], 1):
                            st.write(f"{i}. {claim}")
                        if len(unsupported) > 5:
                            st.write(f"... and {len(unsupported) - 5} more")
        
        if issues:
            st.markdown("#### General Issues:")
            for i, issue in enumerate(issues[:5], 1):
                st.write(f"{i}. {issue}")
            if len(issues) > 5:
                st.write(f"... and {len(issues) - 5} more issues")
    
    def _calculate_deductions(self, invalid_cites, unsupported, contradictions):
        deductions = []
        
        if invalid_cites:
            deductions.append({
                "reason": f"Invalid Citations ({len(invalid_cites)} found)",
                "details": f"Citations {invalid_cites} are outside the valid source range",
                "penalty": -0.3,
                "icon": "❌"
            })
        
        if len(unsupported) >= 3:
            deductions.append({
                "reason": f"Unsupported Claims ({len(unsupported)} found)",
                "details": f"{len(unsupported)} claims lack proper citations",
                "penalty": -0.2,
                "icon": "⚠️"
            })
        elif unsupported:
            deductions.append({
                "reason": f"Unsupported Claims ({len(unsupported)} found)",
                "details": f"{len(unsupported)} claims lack proper citations (no penalty: <3)",
                "penalty": 0.0,
                "icon": "ℹ️"
            })
        
        if contradictions:
            deductions.append({
                "reason": "Contradictions Detected",
                "details": "Report contains contradictory information or inconsistent claims",
                "penalty": -0.3,
                "icon": "⚠️"
            })
        
        return deductions
    
    def _render_approve_tab(self, task_id: str):
        st.markdown("**Approve this report as-is**")
        st.markdown("The report will be finalized and marked as completed.")
        if st.button("✅ Approve Report", type="primary", use_container_width=True):
            with st.spinner("Submitting approval..."):
                if self.api.submit_review_decision(task_id, "approve"):
                    st.success("✅ Report approved successfully!")
                    time.sleep(1)
                    st.rerun()
    
    def _render_edit_tab(self, task_id: str, original_content: str):
        st.markdown("**Edit the report before approval**")
        st.markdown("Make any necessary changes to the report content.")
        
        if not original_content:
            st.info("💡 **Note:** Report draft is not available. You can create a new report by typing below.")
        
        edited_content = st.text_area(
            "Edit Report Content",
            value=original_content if original_content else "Enter your report content here...",
            height=400,
            help="Modify the report text as needed."
        )
        
        if st.button("✏️ Submit Edited Report", type="primary"):
            placeholder = "Enter your report content here..."
            current = edited_content.strip()
            original = original_content.strip() if original_content else placeholder
            
            if current and current != original:
                with st.spinner("Submitting edited report..."):
                    if self.api.submit_review_decision(task_id, "edit", modified_content=edited_content):
                        st.success("✅ Report edited and approved!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.warning("Please make changes to the report before submitting.")
    
    def _render_reject_tab(self, task_id: str):
        st.markdown("**Reject this report**")
        st.markdown("The report will be rejected and the workflow will regenerate a new report.")
        
        reason = st.text_area(
            "Rejection Reason",
            placeholder="Explain why this report is being rejected...",
            height=150,
            help="Provide a reason for rejection."
        )
        
        if st.button("❌ Submit Rejection", type="primary", use_container_width=True):
            if reason.strip():
                with st.spinner("Submitting rejection..."):
                    if self.api.submit_review_decision(task_id, "reject", rejection_note=reason):
                        st.success("❌ Report rejected. A new report will be generated.")
                        time.sleep(2)
                        st.rerun()
            else:
                st.warning("Please provide a reason for rejection.")


class Application:
    """Main application controller"""
    
    def __init__(self):
        SessionManager.initialize()
        self.api = APIClient()
        self.report_viewer = ReportViewer(self.api)
        self.hitl_review = HITLReview(self.api)
        self.cost_analyzer = CostAnalyzer()
    
    def run(self):
        self.render_sidebar()
        page = st.session_state.get("current_page", PageType.HOME.value)
        
        if page == PageType.HOME.value:
            self.page_home()
        elif page == PageType.HISTORY.value:
            self.page_history()
        elif page == PageType.COSTS.value:
            self.page_costs()
        elif page == PageType.ANALYTICS.value:
            self.page_analytics()
    
    def render_sidebar(self):
        with st.sidebar:
            st.title("🔬 AI Research Assistant")
            st.markdown("---")
            
            # Connection status
            if self.api.check_health():
                st.success("✅ API Connected")
            else:
                st.error("❌ API Unavailable")
                st.info(f"Make sure the API is running at {Config.get_api_base()}")
                st.stop()
            
            st.markdown("---")
            
            # Navigation
            page = st.radio(
                "Navigation",
                [p.value for p in PageType],
                label_visibility="collapsed"
            )
            st.session_state.current_page = page
            
            st.markdown("---")
            
            # Auto-refresh control
            st.session_state.refresh_enabled = st.checkbox(
                "🔄 Auto-refresh",
                value=st.session_state.refresh_enabled
            )
            
            if st.session_state.refresh_enabled:
                st.caption("Auto-refreshing every 3 seconds for active tasks")
    
    def page_home(self):
        st.title("Research Query Submission")
        
        if UIComponents.refresh_button():
            if st.session_state.active_task:
                self.refresh_task(st.session_state.active_task)
            st.rerun()
        
        st.markdown("Submit a research question to generate an AI-powered research report with citations.")
        
        # Query submission form
        with st.form("research_submission", clear_on_submit=True):
            query_text = st.text_area(
                "Research Question",
                placeholder="e.g., What are the latest advances in transformer architectures?",
                height=100,
                help="Enter your research question (10-500 characters)"
            )
            
            depth_level = st.selectbox(
                "Research Depth",
                ["quick", "standard", "comprehensive"],
                index=1,
                help="Quick: Fast results, Standard: Balanced, Comprehensive: Thorough analysis"
            )
            
            submit_btn = st.form_submit_button("Submit Research Query", type="primary", use_container_width=True)
            
            if submit_btn:
                if not query_text or len(query_text) < 10:
                    st.error("Please enter a research question (minimum 10 characters)")
                elif len(query_text) > 500:
                    st.error("Research question is too long (maximum 500 characters)")
                else:
                    with st.spinner("Submitting research query..."):
                        result = self.api.create_research_task(
                            query_text, 
                            depth_level
                        )
                        
                        if result:
                            task_id = result.get("task_id")
                            SessionManager.add_task(task_id, {
                                "query": query_text,
                                "depth": depth_level,
                                "status": result.get("status"),
                                "created_at": result.get("created_at")
                            })
                            st.success(f"✅ Research task created! Task ID: `{task_id}`")
                            st.rerun()
        
        # Show current task
        if st.session_state.active_task:
            st.markdown("---")
            st.subheader("Current Task")
            self.refresh_task(st.session_state.active_task)
            self.show_task_details(st.session_state.active_task)
            
            # Auto-refresh logic
            task_info = SessionManager.get_task(st.session_state.active_task)
            if task_info and task_info.get('status') in ['queued', 'processing', 'pending_review']:
                if st.session_state.refresh_enabled:
                    time.sleep(3)
                    st.rerun()
    
    def page_history(self):
        st.title("Task History")
        st.markdown("View completed research tasks")
        
        if UIComponents.refresh_button():
            for tid in st.session_state.research_tasks.keys():
                self.refresh_task(tid)
            st.rerun()
        
        if st.session_state.research_tasks:
            completed = []
            for tid in st.session_state.research_tasks.keys():
                self.refresh_task(tid)
                task_info = SessionManager.get_task(tid)
                if task_info and task_info.get('status') == 'completed':
                    completed.append(tid)
            
            if completed:
                def format_option(tid):
                    task_info = SessionManager.get_task(tid)
                    q = task_info.get('query', 'Unknown')
                    return f"{q} | ID: {tid}"
                
                selected = st.selectbox(
                    "Select Completed Task",
                    completed,
                    index=0 if completed else None,
                    format_func=format_option
                )
                
                if selected:
                    self.refresh_task(selected)
                    self.show_task_details(selected)
            else:
                st.info("No completed tasks yet. Completed tasks will appear here after processing finishes.")
        else:
            st.info("No tasks yet. Submit a research query from the Home page to get started.")
    
    def page_costs(self):
        st.title("Cost Dashboard")
        
        if UIComponents.refresh_button():
            st.rerun()
        
        if st.session_state.refresh_enabled:
            st.info("🔄 Auto-refresh enabled (every 3 seconds)")
        
        cost_data = self.cost_analyzer.load_cost_records()
        
        if st.session_state.refresh_enabled:
            time.sleep(3)
            st.rerun()
        
        if cost_data:
            self.render_cost_dashboard(cost_data)
        else:
            self.render_cost_troubleshooting()
    
    def page_analytics(self):
        st.title("📈 Analytics Dashboard")
        
        if UIComponents.refresh_button():
            st.rerun()
        
        # Task Analytics
        st.subheader("Task Analytics")
        
        if st.session_state.research_tasks:
            # Refresh all tasks
            for tid in st.session_state.research_tasks.keys():
                self.refresh_task(tid)
            
            # Gather statistics
            total_tasks = len(st.session_state.research_tasks)
            status_counts = {}
            depth_counts = {}
            task_durations = []
            
            for tid, task in st.session_state.research_tasks.items():
                # Count by status
                status = task.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # Count by depth
                depth = task.get('depth', 'unknown')
                depth_counts[depth] = depth_counts.get(depth, 0) + 1
                
                # Calculate duration if completed
                if status == 'completed' and 'created_at' in task:
                    # Fetch latest status for completion time
                    status_info = self.api.fetch_status(tid)
                    if status_info and 'updated_at' in status_info:
                        try:
                            created = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                            completed = datetime.fromisoformat(status_info['updated_at'].replace('Z', '+00:00'))
                            duration = (completed - created).total_seconds() / 60  # in minutes
                            task_durations.append(duration)
                        except:
                            pass
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tasks", total_tasks)
            with col2:
                completed_count = status_counts.get('completed', 0)
                st.metric("Completed", completed_count)
            with col3:
                if total_tasks > 0:
                    completion_rate = (completed_count / total_tasks) * 100
                    st.metric("Completion Rate", f"{completion_rate:.1f}%")
                else:
                    st.metric("Completion Rate", "0%")
            with col4:
                if task_durations:
                    avg_duration = sum(task_durations) / len(task_durations)
                    st.metric("Avg Duration", f"{avg_duration:.1f} min")
                else:
                    st.metric("Avg Duration", "N/A")
            
            st.markdown("---")
            
            # Visualizations
            col1, col2 = st.columns(2)
            
            with col1:
                # Status distribution
                if status_counts:
                    st.subheader("Tasks by Status")
                    status_df = pd.DataFrame(
                        list(status_counts.items()),
                        columns=['Status', 'Count']
                    )
                    fig = px.pie(
                        status_df,
                        values='Count',
                        names='Status',
                        title="Task Status Distribution",
                        color_discrete_map={
                            'queued': '#FFC107',
                            'processing': '#2196F3',
                            'completed': '#4CAF50',
                            'failed': '#F44336',
                            'pending_review': '#FF9800'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Depth distribution
                if depth_counts:
                    st.subheader("Tasks by Research Depth")
                    depth_df = pd.DataFrame(
                        list(depth_counts.items()),
                        columns=['Depth', 'Count']
                    )
                    fig = px.bar(
                        depth_df,
                        x='Depth',
                        y='Count',
                        title="Research Depth Distribution",
                        color='Depth',
                        color_discrete_map={
                            'quick': '#90EE90',
                            'standard': '#87CEEB',
                            'comprehensive': '#9370DB'
                        }
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            # Task timeline
            if st.session_state.research_tasks:
                st.subheader("Task Timeline")
                timeline_data = []
                for tid, task in st.session_state.research_tasks.items():
                    if 'created_at' in task:
                        try:
                            created_time = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                            timeline_data.append({
                                'Task': task.get('query', 'Unknown')[:50] + '...' if len(task.get('query', '')) > 50 else task.get('query', 'Unknown'),
                                'Created': created_time,
                                'Status': task.get('status', 'unknown'),
                                'Depth': task.get('depth', 'unknown')
                            })
                        except:
                            pass
                
                if timeline_data:
                    timeline_df = pd.DataFrame(timeline_data)
                    timeline_df = timeline_df.sort_values('Created')
                    
                    fig = px.scatter(
                        timeline_df,
                        x='Created',
                        y='Task',
                        color='Status',
                        symbol='Depth',
                        title="Task Creation Timeline",
                        labels={'Created': 'Creation Time', 'Task': 'Research Query'},
                        hover_data=['Status', 'Depth']
                    )
                    fig.update_yaxis(showticklabels=False)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Success metrics
            st.markdown("---")
            st.subheader("Performance Metrics")
            
            # Calculate additional metrics
            failed_count = status_counts.get('failed', 0)
            pending_count = status_counts.get('pending_review', 0)
            processing_count = status_counts.get('processing', 0)
            queued_count = status_counts.get('queued', 0)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if total_tasks > 0:
                    success_rate = ((completed_count + pending_count) / total_tasks) * 100
                    st.metric("Success Rate", f"{success_rate:.1f}%", 
                             help="Percentage of tasks completed or pending review")
                else:
                    st.metric("Success Rate", "0%")
            
            with col2:
                st.metric("In Progress", processing_count + queued_count,
                         help="Tasks currently being processed")
            
            with col3:
                st.metric("Failed Tasks", failed_count,
                         help="Tasks that encountered errors")
            
            # Recent activity
            st.markdown("---")
            st.subheader("Recent Activity")
            
            recent_tasks = sorted(
                st.session_state.research_tasks.items(),
                key=lambda x: x[1].get('created_at', ''),
                reverse=True
            )[:10]
            
            if recent_tasks:
                activity_data = []
                for tid, task in recent_tasks:
                    activity_data.append({
                        'Time': UIComponents.format_datetime(task.get('created_at', '')),
                        'Query': task.get('query', 'Unknown')[:50] + '...' if len(task.get('query', '')) > 50 else task.get('query', 'Unknown'),
                        'Status': task.get('status', 'unknown').replace('_', ' ').title(),
                        'Depth': task.get('depth', 'unknown').title()
                    })
                
                activity_df = pd.DataFrame(activity_data)
                st.dataframe(activity_df, use_container_width=True, hide_index=True)
            
        else:
            st.info("No tasks to analyze yet. Submit research queries from the Home page to see analytics.")
            
            # Show placeholder metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Tasks", "0")
            with col2:
                st.metric("Completed", "0")
            with col3:
                st.metric("Completion Rate", "0%")
            with col4:
                st.metric("Avg Duration", "N/A")
    
    def refresh_task(self, task_id: str):
        """Refresh task status from API"""
        status_info = self.api.fetch_status(task_id)
        if status_info:
            SessionManager.update_task(task_id, {
                'status': status_info.get('status', 'unknown'),
                'progress': status_info.get('progress'),
                'message': status_info.get('message')
            })
    
    def show_task_details(self, task_id: str):
        """Display comprehensive task details"""
        status_info = self.api.fetch_status(task_id)
        
        if not status_info:
            st.error("Task not found")
            return
        
        status = status_info.get("status", "unknown")
        
        # Show status
        UIComponents.render_task_progress(status_info)
        
        st.markdown("---")
        
        # Show report if available
        if status in ["completed", "pending_review"]:
            st.subheader("Research Report")
            
            report_data = self.api.fetch_report(task_id, "json")
            
            if report_data:
                self.report_viewer.display_report(task_id, report_data)
            else:
                st.warning("Report not available yet")
            
            # HITL Review for pending tasks
            if status == "pending_review":
                self.hitl_review.render_review_interface(task_id, report_data)
        elif status == "failed":
            st.error("Task failed. Check the error message above.")
        else:
            st.info(f"Task is {status}. Report will appear here when processing is complete.")
            
            if status in ["queued", "processing", "pending_review"]:
                if st.session_state.refresh_enabled:
                    self.refresh_task(task_id)
                    time.sleep(3)
                    st.rerun()
                else:
                    st.info("💡 Enable auto-refresh in the sidebar to see real-time progress updates")
    
    def render_cost_dashboard(self, cost_data: dict):
        """Render cost analytics dashboard"""
        if '_metadata' in cost_data:
            metadata = cost_data['_metadata']
            last_mod = metadata.get('last_modified', '')
            if last_mod:
                try:
                    dt = datetime.fromisoformat(last_mod)
                    st.caption(f"📅 Last updated: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except:
                    st.caption(f"📅 Last updated: {last_mod}")
        
        st.markdown("---")
        
        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        
        total_cost = cost_data.get("total_cost", 0.0)
        total_tokens = cost_data.get("total_tokens", 0)
        total_calls = len(cost_data.get("calls", []))
        avg_cost = total_cost / total_calls if total_calls > 0 else 0
        
        with c1:
            st.metric("Total Cost", f"${total_cost:.4f}")
        with c2:
            st.metric("Total Tokens", f"{total_tokens:,}")
        with c3:
            st.metric("Total API Calls", f"{total_calls:,}")
        with c4:
            st.metric("Avg Cost/Call", f"${avg_cost:.6f}")
        
        st.markdown("---")
        
        # Visualizations
        calls = cost_data.get("calls", [])
        if calls:
            df = pd.DataFrame(calls)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            df['cumulative_cost'] = df['cost'].cumsum()
            
            df['date'] = df['timestamp'].dt.date
            daily = df.groupby('date')['cost'].sum().reset_index()
            daily['date'] = pd.to_datetime(daily['date'])
            
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("Cost Over Time")
                fig = px.line(
                    daily,
                    x='date',
                    y='cost',
                    title="Daily API Costs",
                    labels={'cost': 'Cost ($)', 'date': 'Date'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with c2:
                st.subheader("Cumulative Cost")
                fig = px.line(
                    df,
                    x='timestamp',
                    y='cumulative_cost',
                    title="Cumulative API Costs",
                    labels={'cumulative_cost': 'Cumulative Cost ($)', 'timestamp': 'Time'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Cost by Operation Type")
            op_costs = df.groupby('operation')['cost'].sum().reset_index()
            op_costs = op_costs.sort_values('cost', ascending=False)
            
            fig = px.bar(
                op_costs,
                x='operation',
                y='cost',
                title="Total Cost by Operation",
                labels={'cost': 'Cost ($)', 'operation': 'Operation'}
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Recent API Calls")
            recent = df.tail(20)[['timestamp', 'operation', 'model', 'total_tokens', 'cost']].copy()
            recent['timestamp'] = recent['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
            recent['cost'] = recent['cost'].apply(lambda x: f"${x:.6f}")
            st.dataframe(recent, use_container_width=True, hide_index=True)
    
    def render_cost_troubleshooting(self):
        """Show troubleshooting info when cost data is unavailable"""
        st.warning("⚠️ No cost data available")
        st.info("""
        Cost tracking data will appear here after API calls are made.
        
        **Troubleshooting:**
        - Make sure the API server is running and processing requests
        - Check if `logs/cost_tracking.json` exists in the project directory
        - Try clicking the "🔄 Refresh" button above
        - Verify that cost tracking is enabled in the workflow
        """)
        
        with st.expander("🔍 Debug: Check file locations"):
            st.code("""
Possible cost tracking file locations:
1. logs/cost_tracking.json (relative to current directory)
2. {project_root}/logs/cost_tracking.json
3. {streamlit_dir}/logs/cost_tracking.json
            """)
            st.write("**Current working directory:**", os.getcwd())
            st.write("**Streamlit app location:**", Path(__file__).parent)
            
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


# Main execution
if __name__ == "__main__":
    app = Application()
    app.run()
