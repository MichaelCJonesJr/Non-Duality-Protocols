import time
import sys
from raft_node import RaftNode 

if __name__ == '__main__':
    # Dynamically generate partners based on the test size
    num_nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    partners = [f'127.0.0.1:{6000 + i}' for i in range(1, num_nodes + 1)]
    
    # We don't bind to a port, we just observe
    client = RaftNode(None, partners) 
    print(f"[*] Raft Monitor Active watching {num_nodes} nodes. Pushing data...")

    with open("raft_sniper_metrics.csv", "w") as f:
        f.write("timestamp,rtt_ms,throughput_status\n")
        
        msg_id = 0
        while True:
            try:
                leader = client._getLeader()
                if leader:
                    start_time = time.time()
                    try:
                        # INCREASE TIMEOUT: 1.5s is too short for 80 nodes on localhost
                        # Use 5.0s to allow the OS to clear the socket backlog
                        client.add_data(f"payload_{msg_id}", sync=True, timeout=5.0)
                        rtt_ms = (time.time() - start_time) * 1000
                        
                        f.write(f"{time.time()},{rtt_ms:.2f},1\n")
                        msg_id += 1
                        # Slow down polling to prevent the monitor from DDOSing the leader
                        time.sleep(0.2) 
                    except Exception:
                        f.write(f"{time.time()},0.00,0\n")
                else:
                    f.write(f"{time.time()},0.00,0\n")
                
                f.flush()
                time.sleep(0.1) 
            except KeyboardInterrupt:
                break