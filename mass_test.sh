#!/bin/bash

# Ensure root output directory exists
mkdir -p resulteddata

# Outer Loop: Node Sizes (5 sizes total for 45 runs)
for N in 10 20 40 80; do
    
    # Middle Loop: Parameter Sets (F=6/T=15, F=8/T=30, F=10/T=45)
    for P_IDX in 0 1 2; do
        
        FREQS=(6 8 10)
        TIMES=(15 30 45)
        F=${FREQS[$P_IDX]}
        T=${TIMES[$P_IDX]}

        # Inner Loop: 3 Repeats
        for R in 1 2 3; do
            
            echo "[*] STARTING: N=$N, F=$F, T=$T, Run=$R"

            # 1. Execute Test Suite
            ./duel_research_suite.sh "$N" "$F" "$T"

            # 2. Setup ID and Archive Folders
            ID="N${N}_F${F}_T${T}_R${R}"
            LOG_DIR="resulteddata/LOGS_${ID}"
            mkdir -p "$LOG_DIR"

            # 3. Move EVERYTHING (Logs, Plots, CSVs)
            # Moving logs from the root to the new log subfolder
            mv *.log "$LOG_DIR/" 2>/dev/null
            
            # Moving the plot from the root (where it is generated) to resulteddata
            mv final_comparison_results.png "resulteddata/PLOT_${ID}.png" 2>/dev/null
            
            # Renaming CSVs already inside resulteddata to their permanent ID
            mv resulteddata/raft_results.csv "resulteddata/RAFT_${ID}.csv" 2>/dev/null
            mv resulteddata/research_results.csv "resulteddata/FLEX_${ID}.csv" 2>/dev/null

            echo "[+] Archive Complete for $ID"

            # 4. Standard Cleanup
            ./cleanup.sh
            ./stop_nodes.sh
            
            # Brief pause for the network stack
            sleep 2
            
        done
    done
done