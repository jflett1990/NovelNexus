# This file has been refactored into a modular architecture
# The original workflow.py has been moved to workflow_original.py for backup
# The new modular workflow is in workflow_new.py and its components

from .workflow_new import ManuscriptWorkflow

# For backward compatibility, export the main class
__all__ = ['ManuscriptWorkflow']
