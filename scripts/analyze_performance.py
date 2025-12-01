
import json
import glob
import os
import re
from datetime import datetime
from collections import defaultdict
import statistics

def parse_timestamp(ts_str):
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        try:
            # Handle timestamps with Z or other formats if necessary
            # Simple fallback for now
            return datetime.strptime(ts_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None

def analyze_logs(log_dir):
    files = glob.glob(os.path.join(log_dir, "*.json"))
    
    # Sort files by modification time (newest first)
    files.sort(key=os.path.getmtime, reverse=True)
    
    stats = {
        "coleman": {"total": 0, "success": 0, "failure": 0, "durations": [], "errors": defaultdict(int), "steps_at_failure": defaultdict(int)},
        "guidepoint": {"total": 0, "success": 0, "failure": 0, "durations": [], "errors": defaultdict(int), "steps_at_failure": defaultdict(int)},
        "glg": {"total": 0, "success": 0, "failure": 0, "durations": [], "errors": defaultdict(int), "steps_at_failure": defaultdict(int)},
        "office_hours": {"total": 0, "success": 0, "failure": 0, "durations": [], "errors": defaultdict(int), "steps_at_failure": defaultdict(int)}
    }

    print(f"Analyzing {len(files)} log files...\n")

    for file_path in files:
        filename = os.path.basename(file_path)
        
        # Determine platform
        platform = None
        if "coleman" in filename.lower():
            platform = "coleman"
        elif "guidepoint" in filename.lower():
            platform = "guidepoint"
        elif "glg" in filename.lower():
            platform = "glg"
        elif "office_hours" in filename.lower():
            platform = "office_hours"
        
        if not platform:
            continue

        stats[platform]["total"] += 1
        is_success = "success" in filename.lower()
        if is_success:
            stats[platform]["success"] += 1
        else:
            stats[platform]["failure"] += 1

        try:
            with open(file_path, 'r') as f:
                content = f.read()
                if not content.strip():
                    stats[platform]["errors"]["Empty Log File"] += 1
                    continue
                data = json.loads(content)
            
            actions = []
            if isinstance(data, list):
                actions = data
            elif isinstance(data, dict):
                # Sometimes the log might be a dict wrapping the actions or a single action
                if "actions" in data:
                    actions = data["actions"]
                else:
                    actions = [data] # Treat as single action log

            # Filter valid actions with timestamps
            valid_actions = [x for x in actions if isinstance(x, dict) and x.get("timestamp")]
            
            if valid_actions:
                start_time = parse_timestamp(valid_actions[0]["timestamp"])
                end_time = parse_timestamp(valid_actions[-1]["timestamp"])
                
                if start_time and end_time:
                    duration = (end_time - start_time).total_seconds()
                    # Filter out unreasonable durations (e.g. < 0 or > 1 hour for single task if outlier)
                    if duration > 0:
                        stats[platform]["durations"].append(duration)
            
            # Analyze Failures
            if not is_success:
                error_found = False
                
                # Check for explicit error fields
                if isinstance(data, dict) and data.get("error"):
                     stats[platform]["errors"].append(data["error"]) # Changed from += 1 to append
                     error_found = True
                
                # Check list for error steps
                if not error_found and isinstance(actions, list):
                    # Check for batch summary with failure
                    batch_summary = next((x for x in actions if x.get("action") == "batch_summary"), None)
                    if batch_summary:
                        if not batch_summary.get("results"):
                             stats[platform]["errors"]["Batch Failure (Empty Results)"] += 1
                             error_found = True
                    
                    # Check last action for context
                    if not error_found and valid_actions:
                        last_action = valid_actions[-1]
                        step_name = last_action.get("action", "unknown")
                        stats[platform]["steps_at_failure"][step_name] += 1
                        
                        # Look for error indicators in content
                        if "error" in str(last_action).lower():
                             stats[platform]["errors"][f"Error in step: {step_name}"] += 1

                if not error_found:
                    stats[platform]["errors"]["Unknown Failure Pattern"] += 1

        except json.JSONDecodeError:
            stats[platform]["errors"]["Invalid JSON"] += 1
        except Exception as e:
            # print(f"Error parsing {filename}: {e}")
            pass

    # Generate Report
    print("=== Performance & Error Analysis Report ===")
    
    for platform, data in stats.items():
        if data["total"] == 0:
            continue
            
        print(f"\n--- {platform.upper()} ---")
        print(f"Total Runs: {data['total']}")
        success_rate = (data['success'] / data['total']) * 100
        print(f"Success Rate: {data['success']}/{data['total']} ({success_rate:.1f}%)")
        
        if data["durations"]:
            avg_duration = statistics.mean(data["durations"])
            print(f"Avg Duration: {avg_duration:.2f}s")
            print(f"Min Duration: {min(data['durations']):.2f}s")
            print(f"Max Duration: {max(data['durations']):.2f}s")
        
        if data["failure"] > 0:
            print("\nError Patterns:")
            if data["errors"]:
                for err, count in sorted(data["errors"].items(), key=lambda x: x[1], reverse=True):
                    print(f"  - {err}: {count}")
            else:
                 print("  - No explicit error messages found in logs.")
                 
            if data["steps_at_failure"]:
                 print("Last Step Before Failure:")
                 for step, count in sorted(data["steps_at_failure"].items(), key=lambda x: x[1], reverse=True):
                    print(f"  - {step}: {count}")

if __name__ == "__main__":
    analyze_logs("logs/runs")
