# EGESS - Experimental Gear for Evaluation of Swarm Systems
# Copyright (C) 2026  Nick Ivanov and ACSUS Lab <ivanov@rowan.edu>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


# -------------------------------------------------------------------------
# This file implements the push protocol of the node. The push protocol
# sends the message from the push queue to other nodes.
# -------------------------------------------------------------------------

import copy  # For copying lists' data, not references.
import random  # For randomly selecting nodes to forward the message to.
import egess_api  # For invoking commonly used functions.
import time  # for managing time stamped data


def push_protocol(config_json, node_state, state_lock, this_port, number_of_nodes, push_queue, msg):
    """
    This function implements the push protocol for a message taken from the push queue.

    Args:
        config_json (dict[str, Any]): JSON object with all-nodes configuration.
        node_state (dict[str, Any]): The state of this current node.
        state_lock (threading.Lock): The lock object for thread-safety of the state.
        this_port (int): The port this node listens.
        number_of_nodes (int): The total number of nodes in the network (if known).
        push_queue (queue.Queue): The queue for messages to be pushed to other node(s).
        msg (dict[str, Any]): The message (in JSON format) to be pushed.
    """
    if(not node_state["active"]):#if node is not active ie. off dont do anything
        return;
    # Now let's take a random node to push too
    # releasing state lock as we are no longer performing operations on the nodes state
    # Iterate over the randomly selected sample of nodes.
    state_lock.acquire()
    msg["data"]["leadership_matrix"] = node_state["known_leadership"]
    msg["data"]["neighbor_nodes"] = node_state["neighbor_nodes"]
    msg["metadata"]["relay"] = this_port
    state_lock.release()
    
    fanout = min(config_json["push_fanout_value"], len(node_state["neighbor_nodes"]))
    
    node_sample = select_neighbor(config_json, node_state, state_lock, this_port, fanout)
    while (node_sample):
        target_port = node_sample.pop()
        ping_msg = time.time()
        resp = egess_api.send_msg(config_json, node_state, state_lock, this_port, msg, target_port)
        if(not resp is None and resp["metadata"]["active"]): #message succesfully sent if true
            latency = time.time() - ping_msg
            index = node_state["neighbor_nodes"].index(target_port)
            weight = config_json["latency_weight"]
            node_state["latency_matrix"][index] = (weight * latency) + (1 - weight) * node_state["latency_matrix"][index]
            node_state["leadership"] = max(node_state["leadership"] - .05, -1)
            egess_api.write_state_change_data_point(this_port, node_state, "leadership")
            fanout -= 1
            print("MESSAGE FORWARDED {} {}\n".format(str(this_port), str(target_port)))
        else: #message failed to send meaning we sent to a dead node
            state_lock.acquire()
            if(target_port in node_state["neighbor_nodes"]):
                index = node_state["neighbor_nodes"].index(target_port)
                node_state["neighbor_nodes"].pop(index)
                node_state["known_leadership"].pop(index)
            msg["data"]["leadership_matrix"] = node_state["known_leadership"]
            msg["data"]["neighbor_nodes"] = node_state["neighbor_nodes"]
            state_lock.release()
            node_sample.extend(select_neighbor(config_json, node_state, state_lock, this_port, fanout))
    egess_api.log_current_node_state(this_port,node_state)

def select_neighbor(config_json, node_state, state_lock, this_port, fanout):
    node_sample = []
    state_lock.acquire()
    neighbors = node_state["neighbor_nodes"]
    for i in range(fanout):
        if (abs(node_state["leadership"]) * .3 + .5 > random.random()):
            index = 0
            value = 0
            for j in range(len(neighbors)):
                index = index if value < node_state["known_leadership"][j][0]/(node_state["latency_matrix"][j] + .0000001) else j
                value = (node_state["known_leadership"][index][0])/(node_state["latency_matrix"][index]  + .0000001)
            node_sample.append(neighbors[index])
        else:
            node_sample = (random.sample(neighbors, 2))
    state_lock.release()
    return node_sample