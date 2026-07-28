"""Native tool implementations.

Every module here registers its tool with the singleton ``tool_registry`` via
``@register_tool``; the plugin scanner imports them at startup (``app.tools`` is
already in ``DEFAULT_PLUGIN_PACKAGES``), so no central import list exists.
"""

from app.tools.context import ToolContext
from app.tools.create_task import CreateTaskTool
from app.tools.vector_search import VectorSearchTool
from app.tools.web_search import WebSearchTool

__all__ = ["CreateTaskTool", "ToolContext", "VectorSearchTool", "WebSearchTool"]
