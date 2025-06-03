#!/usr/bin/env python
"""
Script to update all agent files to use OpenAI models based on the agent name.
This script adds the agent_name parameter to all OpenAI generate calls.
"""

import os
import re
import glob

def update_file(file_path):
    """Update a file to add the agent_name parameter to OpenAI generate calls."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract the agent name from the file
    agent_name_match = re.search(r'self\.name\s*=\s*[\'"]([^\'"]+)[\'"]', content)
    if not agent_name_match:
        print(f"Could not find agent name in {file_path}")
        return False
    
    agent_name = agent_name_match.group(1)
    print(f"Agent name in {file_path}: {agent_name}")
    
    # Define a pattern that looks for OpenAI generate methods but without the agent_name parameter
    pattern = r'(self\.openai_client\.generate\(\s*(?:[^,)]*,\s*)*?)(\s*\)\s*)'
    
    # Check if there are any matches that don't already have agent_name
    openai_calls = re.findall(pattern, content)
    valid_calls = []
    
    for call_start, call_end in openai_calls:
        if 'agent_name=' not in call_start:
            valid_calls.append((call_start, call_end))
    
    if not valid_calls:
        print(f"No OpenAI calls without agent_name found in {file_path}")
        return False
    
    # Modify the content with the agent_name parameter
    modified_content = content
    for call_start, call_end in valid_calls:
        # Check if the call_start ends with a comma
        if call_start.rstrip().endswith(','):
            replacement = f"{call_start}\n        agent_name='{agent_name}'{call_end}"
        else:
            replacement = f"{call_start},\n        agent_name='{agent_name}'{call_end}"
        
        # Create a regex-safe version of the original
        safe_original = re.escape(call_start + call_end)
        modified_content = re.sub(safe_original, replacement, modified_content, count=1)
    
    # Check if any changes were made
    if content != modified_content:
        with open(file_path, 'w') as f:
            f.write(modified_content)
        print(f"Updated {file_path} with {len(valid_calls)} OpenAI generate calls")
        return True
    else:
        print(f"No changes made to {file_path}")
        return False

def main():
    """Main function to update all agent files."""
    agents_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'agents')
    agent_files = glob.glob(os.path.join(agents_dir, '*_agent.py'))
    
    print(f"Found {len(agent_files)} agent files to update.")
    
    updated_count = 0
    for file_path in agent_files:
        try:
            if update_file(file_path):
                updated_count += 1
        except Exception as e:
            print(f"Error updating {file_path}: {e}")
    
    print(f"Updated {updated_count} agent files.")

if __name__ == "__main__":
    main() 