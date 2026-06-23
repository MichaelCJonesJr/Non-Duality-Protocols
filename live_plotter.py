import os
import time
import math
from collections import defaultdict, deque

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

DATA_FILE = "data.csv"


def parse_data():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame(columns=["port", "timestamp", "event", "data"]), []

    df = pd.read_csv(DATA_FILE, sep=';', names=['port', 'pid', 'timestamp', 'event', 'data'])
    df['port'] = df['port'].astype(int)
    df['timestamp'] = df['timestamp'].astype(float)
    return df, sorted(df['port'].unique())


def compute_positions(ports, radius=10):
    n = len(ports)
    positions = {}
    if n == 0:
        return positions
    for i, p in enumerate(sorted(ports)):
        theta = (2 * math.pi * i) / n
        positions[p] = (radius * math.cos(theta), radius * math.sin(theta))
    return positions


def get_latest_events(df, since_t):
    if since_t is None:
        since_t = 0
    return df[df['timestamp'] > since_t]


class LiveGraph:
    def __init__(self):
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.ports = []
        self.pos = {}
        self.last_time = None

        # Keep recent events for visual animation (FIFO)
        self.recent_sends = deque(maxlen=50)
        self.recent_accepts = deque(maxlen=50)
        self.recent_pull_requests = deque(maxlen=50)
        self.neighbors = defaultdict(set)

        self.ax.set_aspect('equal', 'box')
        self.ax.set_xlim(-32, 32)
        self.ax.set_ylim(-32, 32)
        self.annotations = []

    def update(self, frame):
        df, ports = parse_data()
        if len(ports) == 0:
            return

        if self.ports != ports:
            self.ports = ports
            self.radius = 36
            self.pos = compute_positions(ports, radius=self.radius)

        if self.last_time is None:
            self.last_time = df['timestamp'].min() if not df.empty else 0

        new_df = get_latest_events(df, self.last_time)
        if not new_df.empty:
            self.last_time = new_df['timestamp'].max()

        send_events = new_df[new_df['event'] == 'message_sent']
        accept_events = new_df[new_df['event'] == 'message_accepted']
        pull_events = new_df[new_df['event'] == 'pull_request_received']
        neighbor_events = new_df[new_df['event'] == 'state_change']

        for _, row in neighbor_events.iterrows():
            if 'neighbor_nodes' in str(row['data']):
                node = int(row['port'])

                raw = str(row['data'])
                start = raw.find('[')
                end = raw.find(']')

                if start != -1 and end != -1:
                    neighbor_list = raw[start+1:end].split()

                    for n in neighbor_list:
                        try:
                            neighbor = int(n)
                            self.neighbors[node].add(neighbor)
                            self.neighbors[neighbor].add(node)  # make symmetric
                        except ValueError:
                            continue

        for _, row in send_events.iterrows():
            source = int(row['port'])
            target_str = str(row['data']).replace('to=', '').strip()
            try:
                target = int(target_str)
            except ValueError:
                continue
            self.recent_sends.append((source, target, row['timestamp']))

        for _, row in accept_events.iterrows():
            node = int(row['port'])
            target_str = str(row['data']).replace('from=', '').strip()
            try:
                target = int(target_str)
            except ValueError:
                continue
            self.recent_accepts.append((node, row['data'], row['timestamp']))

        for _, row in pull_events.iterrows():
            target = int(row['port'])  # receiver
            try:
                source = int(str(row['data']).strip())  # sender
            except ValueError:
                continue

            self.recent_pull_requests.append((source, target, row['timestamp']))

        # Axes clear for fresh frame
        self.ax.clear()
        margin = self.radius * 0.1  # space around nodes
        limit = self.radius + margin
        self.ax.set_xlim(-limit, limit)
        self.ax.set_ylim(-limit, limit)
        self.ax.set_aspect('equal', 'box')
        self.ax.axis('off')
        # Compute node color intensity by total accepted events
        accepted_by_node = defaultdict(int)
        all_accepts = df[df['event'] == 'message_accepted']
        for _, row in all_accepts.iterrows():
            accepted_by_node[int(row['port'])] += 1

        max_accepts = max(accepted_by_node.values()) if accepted_by_node else 1

        active_events = {}

        now = time.time()

        # Draw neighbor edges (thick black lines)
        drawn = set()

        for node, nbrs in self.neighbors.items():
            for nbr in nbrs:
                edge = tuple(sorted((node, nbr)))
                if edge in drawn:
                    continue
                drawn.add(edge)

                if node not in self.pos or nbr not in self.pos:
                    continue

                x0, y0 = self.pos[node]
                x1, y1 = self.pos[nbr]

                self.ax.plot([x0, x1], [y0, y1], color='black', linewidth=3, zorder=1)

        for node, data, ts in list(self.recent_accepts):
            age = now - ts
            if age < 8.0:
                label = str(data).replace('from=', '').strip()
                active_events[node] = (ts, label)
        # Draw nodes
        for node, (x, y) in self.pos.items():
            count = accepted_by_node.get(node, 0)
            cmap = plt.cm.OrRd
            color = cmap(min(1, count / max_accepts))
            edge_color = 'green' if node in active_events else 'black'
            line_width = 2.5 if node in active_events else 1.0

            self.ax.scatter(x, y, s=1200, color=color, edgecolors=edge_color, linewidths=line_width, zorder=2)
            self.ax.text(x, y, f"{node}", ha='center', va='center', fontsize=9, fontweight='bold')
            self.ax.text(x, y - 1.5, f"{count}", ha='center', va='center', fontsize=7, color='black')

        # Draw send edges and arrows for recent send events
        now = time.time()
        for src, dst, ts in list(self.recent_sends):
            if src not in self.pos or dst not in self.pos:
                continue
            x0, y0 = self.pos[src]
            x1, y1 = self.pos[dst]
            # Fade with age
            age = now - ts
            alpha = max(0.1, 1.0 - age / 8.0)
            self.ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='->', color='blue', alpha=alpha, lw=1.5))

        # Draw pull request arrows (purple, dashed)
        now = time.time()

        for src, dst, ts in list(self.recent_pull_requests):
            if src not in self.pos or dst not in self.pos:
                continue

            x0, y0 = self.pos[src]
            x1, y1 = self.pos[dst]

            age = now - ts
            alpha = max(0.1, 1.0 - age / 8.0)

            self.ax.annotate(
                '',
                xy=(x1, y1),
                xytext=(x0, y0),
                arrowprops=dict(
                    arrowstyle='->',
                    color='orange',      # 👈 different color
                    linestyle='dashed',  # 👈 visually distinct
                    alpha=alpha,
                    lw=1.0               # slightly thicker
                )
            )
        # Show accepts as temporary highlight text
        for node, (ts, label) in active_events.items():
            if node not in self.pos or label is None:
                continue

            x, y = self.pos[node]
            age = now - ts
            alpha = max(0.1, 1.0 - age / 8.0)
            self.ax.text(x, y + 4.0, f"accepted from {label}", ha='center', va='center', fontsize=8, color='green', alpha=alpha)

if __name__ == '__main__':
    plt.ion()
    graph = LiveGraph()
    ani = FuncAnimation(graph.fig, graph.update, interval=500)
    plt.show(block=True)