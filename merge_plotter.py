import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

def merge_and_plot(num_nodes, attack_freq, max_time):
    raft_path = os.path.join("resulteddata", "raft_results.csv")
    research_path = os.path.join("resulteddata", "research_results.csv")
    strike_log_path = os.path.join("resulteddata", "strike_log.csv")
    
    print(f"[*] Generating Unified Plot | Nodes: {num_nodes} | Attack Interval: {attack_freq}s")


    raft_times, raft_cumulatives = [0], [0]
    all_events = []
    raft_df = pd.DataFrame()

    try:
        log_files = [f for f in os.listdir('.') if f.startswith('node_') and f.endswith('.log')]
        
        for log in log_files:
            with open(log, 'r') as f:
                for line in f:
                    clean_line = line.strip()
                    if 'payload_' in clean_line and '|' in clean_line:
                        try:
                            parts = clean_line.split('|')
                            msg_label = parts[0]
                            msg_id = int(msg_label.split('_')[1])
                            timestamp = float(parts[1])
                            all_events.append({'id': msg_id, 'ts': timestamp})
                        except (ValueError, IndexError):
                            continue
        
        if all_events:
            df_all = pd.DataFrame(all_events)
            #Find the FIRST time any node saw this specific message ID
            first_seen = df_all.groupby('id')['ts'].min().sort_values().reset_index()
            
            raft_t0 = first_seen['ts'].min()
            first_seen['rel_sec'] = first_seen['ts'] - raft_t0
            
            #Filter by max_time
            valid_raft = first_seen[first_seen['rel_sec'] <= max_time].copy()
            
            #Build the staircase data
            # Use the sorted message IDs to ensure the Y-axis increments correctly
            raft_times = [0] + valid_raft['rel_sec'].tolist()
            raft_cumulatives = [0] + list(range(1, len(valid_raft) + 1))
            
            print(f"[+] Raft Parsed: {len(valid_raft)} unique messages found.")
                
    except Exception as e:
        print(f"[-] Multi-Log Parse Error: {e}")

    # Ensure the line reaches the end of the graph
    raft_times.append(max_time)
    raft_cumulatives.append(raft_cumulatives[-1])

    flex_times, flex_cumulatives = [0], [0]
    completed_messages = 0

    try:
        df_raw = pd.read_csv(research_path, sep=';', header=None)
        if len(df_raw.columns) >= 4:
            df_raw.columns = ['node', 'pid', 'timestamp', 'event', 'data'][:len(df_raw.columns)]
            df_raw = df_raw.dropna(subset=['data', 'timestamp'])
            state_changes = df_raw[df_raw['data'].str.contains(r'accepted_messages=\d+', na=False)].copy()
            
            if not state_changes.empty:
                t0 = state_changes['timestamp'].astype(float).min()
                is_ms = t0 > 10**11
                state_changes['rel_sec'] = (state_changes['timestamp'].astype(float) - t0) / 1000.0 if is_ms else (state_changes['timestamp'].astype(float) - t0)
                valid_states = state_changes[state_changes['rel_sec'] <= max_time].sort_values('rel_sec')
                
                current_threshold = num_nodes
                counter = 0
                for index, row in valid_states.iterrows():
                    t = row['rel_sec']
                    counter += 1
                    if counter >= current_threshold:
                        completed_messages += 1
                        flex_times.append(t)
                        flex_cumulatives.append(completed_messages)
                        counter = 0 
                        current_threshold = max(1, num_nodes - int(t / attack_freq))
    except Exception as e:
        print(f"[-] FlexMode Error: {e}")

    flex_times.append(max_time)
    flex_cumulatives.append(completed_messages)

    strike_events = []
    try:
        # Use the sniper's actual hit log for perfect alignment
        strikes_raw = pd.read_csv(strike_log_path, names=['ts'])
        for s_ts in strikes_raw['ts']:
            rel_s = s_ts - raft_t0
            if 0 <= rel_s <= max_time:
                strike_events.append(rel_s)
    except:
        # Fallback to detected failures in data if log is missing
        print("Strike log missing.")
        if not raft_df.empty:
            for i in range(1, len(raft_df)):
                if raft_df.iloc[i-1]['throughput_status'] == 1 and raft_df.iloc[i]['throughput_status'] == 0:
                    strike_events.append(raft_df.iloc[i]['rel_sec'])

    plt.figure(figsize=(16, 10))
    
    if raft_times:
        plt.step(raft_times, raft_cumulatives, where='post', color='#d62728', linewidth=2, label='Raft (Centralized Consistency)')
    plt.step(flex_times, flex_cumulatives, where='post', color='#1f77b4', linewidth=2.5, label='FlexMode Protocol (Decentralized)')
        
    max_y = max(max(raft_cumulatives) if raft_times else 0, completed_messages, 3)

    for idx, t_s in enumerate(strike_events):
        plt.axvline(x=t_s, color='gray', linestyle=':', linewidth=1.5, alpha=0.7)
        plt.text(t_s, -(max_y * 0.05), f"S{idx+1}", rotation=90, fontsize=9, weight='bold', verticalalignment='top')

        if len(raft_times) > 1:
            # Find the index of the time closest to the strike
            r_idx = np.searchsorted(raft_times, t_s) - 1
            if r_idx >= 0:
                plt.plot(t_s, raft_cumulatives[r_idx], 'rx', markersize=10, mew=2)
            
        # Mark impact on FlexMode line
        f_idx = np.searchsorted(flex_times, t_s) - 1
        if f_idx >= 0:
            plt.plot(t_s, flex_cumulatives[f_idx], 'bx', markersize=8, mew=1.5)

    plt.title(f'Throughput Comparison ({num_nodes} Nodes, {attack_freq}s Strikes)', fontsize=36)
    plt.xlabel('Seconds from Test Start', fontsize=32)
    plt.ylabel('Total Messages Fully Traversed', fontsize=32)
    plt.tick_params(axis='both', labelsize=28)
    plt.xlim(0, max_time)
    plt.ylim(0, max_y + (max_y * 0.1))
    plt.grid(True, linestyle='--', alpha=0.2)
    plt.legend(loc='upper left', fontsize=22)
    plt.tight_layout()
    
    plt.savefig('final_comparison_results.png', dpi=300)
    print(f"[+] Output rendered. FlexMode total: {completed_messages}")

if __name__ == '__main__':
    if len(sys.argv) < 4:
        sys.exit(1)
    merge_and_plot(int(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3]))