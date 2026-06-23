import os
import sys
import signal
import subprocess
import re
import time

from raft_node import RaftNode 

def execute_single_strike(num_nodes):
    # Dynamically build the target list so it works for 5, 20, or 100 nodes
    partners = [f'127.0.0.1:{6000 + i}' for i in range(1, num_nodes + 1)]
    
    attacker = RaftNode(None, partners)
    
    # Brief 0.5s pause purely to allow PySyncObj to sync and fetch the current leader
    time.sleep(0.5) 
    
    target_leader = attacker._getLeader()
    if not target_leader:
        print("[-] Swarm is leaderless or election in progress. Missed strike.")
        return

    # Extract the port
    if hasattr(target_leader, 'port'):
        target_port = str(target_leader.port)
    else:
        leader_str = target_leader.id if hasattr(target_leader, 'id') else str(target_leader)
        target_port = leader_str.split(':')[-1]
        
    print(f"[*] Target Identified: Leader Node on Port {target_port}")
    

    try:
        ss_out = subprocess.check_output("ss -lptn", shell=True, text=True)
        target_pid = None
        
        for line in ss_out.splitlines():
            if f":{target_port}" in line:
                match = re.search(r'pid=(\d+)', line)
                if match:
                    target_pid = int(match.group(1))
                    break
                    
        if target_pid:
            try:
                with open("resulteddata/strike_log.csv", "a") as f:
                    f.write(f"{time.time()}\n")
                print(f"[+] Executing SIGKILL on PID {target_pid}...")
                os.kill(target_pid, signal.SIGKILL)
                print("[!] TARGET NEUTRALIZED.")
            except ProcessLookupError:
                print("[-] Target process already terminated.")
        else:
            print(f"[-] Could not isolate PID for port {target_port}.")
            
    except Exception as e:
        print(f"[-] System error during strike sequence: {e}")

if __name__ == "__main__":
    # Pull the swarm size from the shell script arguments
    if len(sys.argv) < 2:
        print("Usage: python3 raft_sniper.py <num_nodes>")
        sys.exit(1)
        
    execute_single_strike(int(sys.argv[1]))