"""
Centralized logging configuration for the AI Research Assistant.

This module provides a unified logging setup with:
- Structured logging format with timestamps
- Separate log files for each agent
- Different log levels (DEBUG, INFO, WARNING, ERROR)
- Log rotation to prevent huge files
- Console and file handlers
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


# Base logs directory
_LOGS_DIR = Path(__file__).parent.parent / "logs"
_LOGS_DIR.mkdir(exist_ok=True)

# Default log format
_LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log rotation settings
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
_BACKUP_COUNT = 5  # Keep 5 backup files


def get_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    console: bool = True,
    file: bool = True,
) -> logging.Logger:
    """
    Get or create a logger with configured handlers.

    Args:
        name: Logger name (typically __name__ of the calling module)
        log_file: Optional log file name (without .log extension). If None, uses logger name.
        level: Logging level (default: INFO)
        console: Whether to add console handler (default: True)
        file: Whether to add file handler with rotation (default: True)

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create formatter
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler with rotation
    if file:
        if log_file is None:
            # Extract log file name from logger name
            # e.g., "src.agents.search_agent" -> "search_agent"
            log_file = name.split(".")[-1]

        log_path = _LOGS_DIR / f"{log_file}.log"

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_root_logger(level: int = logging.INFO) -> None:
    """
    Set up root logger configuration.

    Args:
        level: Root logging level (default: INFO)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_agent_logger(agent_name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a logger configured for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., "search_agent", "synthesis_agent")
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance.
    """
    logger_name = f"src.agents.{agent_name}"
    return get_logger(logger_name, log_file=agent_name, level=level)


def get_workflow_logger(level: int = logging.INFO) -> logging.Logger:
    """
    Get a logger configured for workflow orchestration.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance.
    """
    return get_logger("src.agents.workflow", log_file="workflow", level=level)


def log_function_entry_exit(logger: logging.Logger):
    """
    Decorator to log function entry and exit.

    Args:
        logger: Logger instance to use for logging.

    Usage:
        @log_function_entry_exit(logger)
        def my_function():
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Entering {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Exiting {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise

        return wrapper

    return decorator


def log_state_transition(
    logger: logging.Logger,
    from_state: str,
    to_state: str,
    task_id: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Log a state transition with optional context.

    Args:
        logger: Logger instance to use.
        from_state: Source state/agent name.
        to_state: Target state/agent name.
        task_id: Optional task ID for context.
        **kwargs: Additional context to log.
    """
    context = f" | task_id={task_id}" if task_id else ""
    for key, value in kwargs.items():
        context += f" | {key}={value}"

    logger.info(f"State transition: {from_state} -> {to_state}{context}")


def log_api_call(
    logger: logging.Logger,
    operation: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    duration: float = 0.0,
    cost: float = 0.0,
    task_id: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Log an API call with structured information.

    Args:
        logger: Logger instance to use.
        operation: Operation name (e.g., "query_expansion", "synthesis").
        model: Model used for the API call.
        prompt_tokens: Number of prompt tokens.
        completion_tokens: Number of completion tokens.
        duration: Duration in seconds.
        cost: Estimated cost in USD.
        task_id: Optional task ID for context.
        **kwargs: Additional context to log.
    """
    context = f" | task_id={task_id}" if task_id else ""
    for key, value in kwargs.items():
        context += f" | {key}={value}"

    total_tokens = prompt_tokens + completion_tokens
    logger.info(
        f"API Call | operation={operation} | model={model} | "
        f"tokens={prompt_tokens}+{completion_tokens}={total_tokens} | "
        f"duration={duration:.2f}s | cost=${cost:.6f}{context}"
    )


def log_performance_metrics(
    logger: logging.Logger,
    operation: str,
    duration: float,
    task_id: Optional[str] = None,
    **metrics,
) -> None:
    """
    Log performance metrics for an operation.

    Args:
        logger: Logger instance to use.
        operation: Operation name.
        duration: Duration in seconds.
        task_id: Optional task ID for context.
        **metrics: Additional metrics to log (e.g., items_processed=100).
    """
    context = f" | task_id={task_id}" if task_id else ""
    for key, value in metrics.items():
        context += f" | {key}={value}"

    logger.info(
        f"Performance | operation={operation} | duration={duration:.2f}s{context}"
    )


def log_error_with_context(
    logger: logging.Logger,
    error: Exception,
    operation: str,
    task_id: Optional[str] = None,
    **context,
) -> None:
    """
    Log an error with full context and stack trace.

    Args:
        logger: Logger instance to use.
        error: Exception that occurred.
        operation: Operation where error occurred.
        task_id: Optional task ID for context.
        **context: Additional context to log.
    """
    ctx_str = f" | task_id={task_id}" if task_id else ""
    for key, value in context.items():
        ctx_str += f" | {key}={value}"

    logger.error(
        f"Error in {operation} | {type(error).__name__}: {str(error)}{ctx_str}",
        exc_info=True,
    )


# Initialize root logger on module import
setup_root_logger()

__all__ = [
    "get_logger",
    "setup_root_logger",
    "get_agent_logger",
    "get_workflow_logger",
    "log_function_entry_exit",
    "log_state_transition",
    "log_api_call",
    "log_performance_metrics",
    "log_error_with_context",
]
