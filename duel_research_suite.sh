#!/bin/bash

if [ "$#" -ne 3 ]; then
    echo "Usage: ./research_suite.sh <nodes> <attack_freq_sec> <max_time_sec>"
    exit 1
fi

NODES=$1
ATTACK_FREQ=$2
MAX_TIME=$3

# Ensure output directory exists
mkdir -p resulteddata

# --- Environment Cleanup ---
cleanup() {
    ./stop_nodes.sh >/dev/null 2>&1
    pkill -f "python3 raft_node.py" >/dev/null 2>&1
    pkill -f "python3 raft_monitor.py" >/dev/null 2>&1
    pkill -9 -f "python.*node"
    pkill -9 -f "python.*raft"
    pkill -9 -f "python.*research"
    rm -f *.bin *.journal raft_startup_debug.log
}

cleanup
echo "Raft ($NODES Nodes) | Freq: ${ATTACK_FREQ}s | Max: ${MAX_TIME}s"

# Generate Port List dynamically based on N
ALL_PORTS=()
for ((p=1; p<=NODES; p++)); do
    ALL_PORTS+=($((6000 + p)))
done

# Start Raft Nodes with N-1 partner arguments
for MY_PORT in "${ALL_PORTS[@]}"; do
    PARTNERS=""
    for P in "${ALL_PORTS[@]}"; do
        if [ "$MY_PORT" != "$P" ]; then
            # Format explicitly with IPs to prevent PySyncObj parsing crashes
            PARTNERS="$PARTNERS $P" 
        fi
    done
    
    # Log errors instead of hiding them, and disown to keep terminal clean
    python3 raft_node.py "$MY_PORT" $PARTNERS >> raft_startup_debug.log 2>&1 &
    disown
    
    # Stagger boot to prevent the 20-node split-vote death spiral
    sleep 0.2
done

# Start the monitor
python3 raft_monitor.py "$NODES" > /dev/null 2>&1 &
MON_PID=$!
disown

#Wait until the monitor successfully writes the first row of data
while [ ! -f raft_sniper_metrics.csv ] || [ $(wc -l < raft_sniper_metrics.csv 2>/dev/null || echo 0) -lt 2 ]; do
    sleep 0.5
done
echo "[+] Raft Leader active! Test clock started."

# Synchronous Raft Attack Loop
START=$(date +%s)
while [ $(( $(date +%s) - START )) -lt $MAX_TIME ]; do
    sleep "$ATTACK_FREQ"
    python3 raft_sniper.py "$NODES"
done

kill $MON_PID 2>/dev/null
mv raft_sniper_metrics.csv resulteddata/raft_results.csv

cleanup
echo "FlexMode Protocol ($NODES Nodes) | Freq: ${ATTACK_FREQ}s | Max: ${MAX_TIME}s"

./start_nodes.sh "$NODES"
sleep 5

# 1. Asynchronous Background Sniper
(
    SNIPER_START=$(date +%s)
    while [ $(( $(date +%s) - SNIPER_START )) -lt $MAX_TIME ]; do
        sleep "$ATTACK_FREQ"
        python3 targeted_attack.py
    done
) &
SNIPER_PID=$!
disown

# 2. Synchronous Smart Trigger Loop
TEST_START=$(date +%s)
MSG_COUNT=1

while [ $(( $(date +%s) - TEST_START )) -lt $MAX_TIME ]; do
    
    # Grab the first available node port dynamically
    TARGET_PORT=$(ss -lptn | grep 'python' | awk '{print $4}' | cut -d':' -f2 | head -n 1)
    
    if [ -z "$TARGET_PORT" ]; then
        echo "[-] Swarm annihilated. Stopping trigger loop."
        break
    fi

    echo "[*] Injecting Message $MSG_COUNT via Port $TARGET_PORT..."
    python3 trigger.py "$TARGET_PORT" trigger_msg.json > /dev/null 2>&1

    # 3. Dynamic Consensus Block
    while [ $(( $(date +%s) - TEST_START )) -lt $MAX_TIME ]; do
        
        # Recalculate physical survivors
        ALIVE=$(ss -lptn | grep 'python' | wc -l)
        
        if [ "$ALIVE" -eq 0 ]; then
            break 2 # Break both loops if swarm is dead
        fi
        
        # Tally acceptances for the CURRENT message
        ACKS=$(grep "accepted_messages=$MSG_COUNT" data.csv 2>/dev/null | wc -l)
        
        # Unblock and proceed the millisecond consensus is reached
        if [ "$ACKS" -ge "$ALIVE" ]; then
            echo "[+] Message $MSG_COUNT achieved consensus ($ACKS/$ALIVE nodes)."
            MSG_COUNT=$((MSG_COUNT + 1))
            break 
        fi
        
        # High-frequency polling to maximize throughput
        sleep 0.1 
    done
done

# Terminate the background sniper and clean up
kill $SNIPER_PID 2>/dev/null
./stop_nodes.sh
mv data.csv resulteddata/research_results.csv

cleanup
echo "[*] Generating Unified Research Plot..."

# Call the plotter with the exact parameters used for the test
python3 merge_plotter.py "$NODES" "$ATTACK_FREQ" "$MAX_TIME"