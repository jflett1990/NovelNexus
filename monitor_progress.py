#!/usr/bin/env python3
"""
Monitor progress of a Novel Nexus project in real-time.
This script continuously checks for updates and displays the progress.
"""

import os
import sys
import json
import pickle
import time
from datetime import datetime
from tabulate import tabulate

def get_project_status(project_id):
    """Get the current status of a project."""
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        return {"error": f"Memory file not found for project {project_id}!"}
    
    try:
        with open(memory_path, 'rb') as f:
            memory_data = pickle.load(f)
        
        # Find project status
        status = "Unknown"
        progress = 0
        current_stage = "Unknown"
        completed_stages = []
        
        # Check directly in memory data
        if isinstance(memory_data, dict):
            # First try to find project_status directly
            if "project_status" in memory_data:
                status_data = memory_data["project_status"]
                if isinstance(status_data, dict):
                    status = status_data.get("status", "Unknown")
                    progress = status_data.get("progress", 0)
                    current_stage = status_data.get("current_stage", "Unknown")
                    completed_stages = status_data.get("completed_stages", [])
            
            # If not found, look in documents
            elif "documents" in memory_data:
                docs = memory_data["documents"]
                status_docs = []
                
                for doc in docs:
                    if isinstance(doc, dict) and "metadata" in doc:
                        metadata = doc.get("metadata", {})
                        if metadata.get("type") == "project_status":
                            status_docs.append(doc)
                
                if status_docs:
                    # Get the most recent status document
                    latest_status = max(status_docs, key=lambda x: x.get("metadata", {}).get("timestamp", ""))
                    content = latest_status.get("content", {})
                    
                    if isinstance(content, dict):
                        status = content.get("status", "Unknown")
                        progress = content.get("progress", 0)
                        current_stage = content.get("current_stage", "Unknown")
                        completed_stages = content.get("completed_stages", [])
        
        return {
            "status": status,
            "progress": progress,
            "current_stage": current_stage,
            "completed_stages": completed_stages,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    except Exception as e:
        return {"error": f"Error loading memory file: {e}"}

def count_documents_by_type(project_id):
    """Count documents by type in a project."""
    memory_path = os.path.join("memory_data", project_id, "memory.pkl")
    if not os.path.exists(memory_path):
        return {}
    
    try:
        with open(memory_path, 'rb') as f:
            memory_data = pickle.load(f)
        
        doc_counts = {}
        
        if isinstance(memory_data, dict) and "documents" in memory_data:
            docs = memory_data["documents"]
            
            for doc in docs:
                if isinstance(doc, dict) and "metadata" in doc:
                    doc_type = doc.get("metadata", {}).get("type", "unknown")
                    doc_counts[doc_type] = doc_counts.get(doc_type, 0) + 1
        
        return doc_counts
    
    except Exception:
        return {}

def monitor_project(project_id, refresh_interval=5):
    """Monitor a project for changes and display progress."""
    print(f"Monitoring project: {project_id}")
    print(f"Refresh interval: {refresh_interval} seconds")
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        last_status = None
        last_counts = None
        
        while True:
            # Clear screen
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Get current status
            status = get_project_status(project_id)
            doc_counts = count_documents_by_type(project_id)
            
            # Display status
            print(f"Project: {project_id}")
            print(f"Last check: {status.get('timestamp', 'Unknown')}")
            
            if "error" in status:
                print(f"Error: {status['error']}")
            else:
                print(f"\nStatus: {status['status']}")
                print(f"Progress: {status['progress']}%")
                print(f"Current stage: {status['current_stage']}")
                print(f"Completed stages: {', '.join(status['completed_stages']) if status['completed_stages'] else 'None'}")
                
                # Show a progress bar
                progress = status.get('progress', 0)
                bar_length = 50
                filled_length = int(bar_length * progress / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                print(f"\nProgress: [{bar}] {progress}%")
            
            # Display document counts
            if doc_counts:
                print("\nDocument counts by type:")
                count_table = []
                for doc_type, count in sorted(doc_counts.items()):
                    count_table.append([doc_type, count])
                print(tabulate(count_table, headers=["Document Type", "Count"], tablefmt="grid"))
            
            # Check for changes since last check
            if last_status and last_counts:
                changes = []
                
                # Check for status changes
                if last_status.get('status') != status.get('status'):
                    changes.append(f"Status changed from {last_status.get('status')} to {status.get('status')}")
                
                if last_status.get('progress') != status.get('progress'):
                    changes.append(f"Progress changed from {last_status.get('progress')}% to {status.get('progress')}%")
                
                if last_status.get('current_stage') != status.get('current_stage'):
                    changes.append(f"Stage changed from {last_status.get('current_stage')} to {status.get('current_stage')}")
                
                # Check for document count changes
                for doc_type, count in doc_counts.items():
                    if doc_type in last_counts and last_counts[doc_type] != count:
                        changes.append(f"{doc_type} documents: {last_counts[doc_type]} -> {count}")
                    elif doc_type not in last_counts:
                        changes.append(f"New document type: {doc_type} ({count})")
                
                if changes:
                    print("\nChanges since last check:")
                    for change in changes:
                        print(f"- {change}")
            
            # Update last status and counts
            last_status = status
            last_counts = doc_counts
            
            # Wait for next check
            time.sleep(refresh_interval)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

def main():
    if len(sys.argv) < 2:
        # If no project ID is provided, list all projects and ask the user to select one
        memory_dir = "memory_data"
        if not os.path.exists(memory_dir):
            print(f"Error: Memory directory '{memory_dir}' not found!")
            return
        
        projects = []
        for item in os.listdir(memory_dir):
            item_path = os.path.join(memory_dir, item)
            if os.path.isdir(item_path):
                try:
                    # Get the modification time
                    mod_time = os.path.getmtime(item_path)
                    mod_time_str = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
                    
                    # Get project status
                    status = get_project_status(item)
                    status_str = status.get('status', 'Unknown')
                    progress = status.get('progress', 0)
                    
                    projects.append([item, mod_time_str, f"{status_str} ({progress}%)"])
                except Exception as e:
                    print(f"Error accessing {item_path}: {e}")
        
        if not projects:
            print(f"No projects found in '{memory_dir}'!")
            return
        
        # Sort by modification time (newest first)
        projects.sort(key=lambda x: datetime.strptime(x[1], '%Y-%m-%d %H:%M:%S'), reverse=True)
        
        print("Available Projects:\n")
        for i, (project_id, mod_time, status) in enumerate(projects):
            print(f"{i+1}. {project_id} - Last modified: {mod_time} - Status: {status}")
        
        try:
            selection = int(input("\nEnter the number of the project to monitor (or 0 to quit): "))
            if selection < 1 or selection > len(projects):
                print("Invalid selection. Exiting.")
                return
            
            project_id = projects[selection-1][0]
        except (ValueError, KeyboardInterrupt):
            print("Invalid selection. Exiting.")
            return
    else:
        project_id = sys.argv[1]
    
    # Get refresh interval
    refresh_interval = 5  # default
    if len(sys.argv) > 2:
        try:
            refresh_interval = int(sys.argv[2])
        except ValueError:
            pass
    
    monitor_project(project_id, refresh_interval)

if __name__ == "__main__":
    main() 