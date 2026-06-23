import os
import signal
import subprocess

def execute_targeted_strike(log_file_path="data.csv"):
    latest_states = {}
    
    try:
        # Pull only the last 2000 lines for speed
        tail_process = subprocess.run(
            ['tail', '-n', '2000', log_file_path], 
            stdout=subprocess.PIPE, 
            text=True,
            check=True
        )
        lines = tail_process.stdout.strip().split('\n')
    except Exception as e:
        print(f"Error reading log: {e}")
        return

    for line in lines:
        line = line.strip()
        if not line or 'state_change;leadership=' not in line:
            continue
        
        parts = line.split(';')
        if len(parts) < 5:
            continue
        
        try:
            # Format: NodeID;OSPID;Timestamp;state_change;leadership=X
            node_id = parts[0]
            pid = int(parts[1])
            l_val = float(parts[4].replace('leadership=', ''))
            
            # Verify process is alive before adding to the targeting list
            try:
                os.kill(pid, 0)
                latest_states[pid] = (l_val, node_id)
            except OSError:
                continue
        except ValueError:
            continue

    if not latest_states:
        print("No active nodes found.")
        return

    # Sort nodes by leadership value (descending)
    sorted_nodes = sorted(latest_states.items(), key=lambda x: x[1][0], reverse=True)

    # Print the full list of survivors and their current weights
    print("\n--- Current Swarm Intelligence ---")
    for pid, (l_val, n_id) in sorted_nodes:
        print(f"Node: {n_id} | PID: {pid} | L-Value: {l_val:.6f}")
    print("----------------------------------")

    # Instant execution on the leader
    target_pid, (max_l, target_node_id) = sorted_nodes[0]
    print(f"Targeting Node {target_node_id} (PID {target_pid})...")
    
    try:
        os.kill(target_pid, signal.SIGKILL)
        print("SIGKILL dispatched.")
    except ProcessLookupError:
        print("Target already dead.")

if __name__ == "__main__":
    execute_targeted_strike()