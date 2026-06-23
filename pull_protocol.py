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
# This file implements the pull protocol. The pull protocol requests
# updates from other nodes and receives these updates within the response
# to the request (i.e., within the same session).
# -------------------------------------------------------------------------


import egess_api
import random
import time

def pull_protocol(config_json, node_state, state_lock, this_port, number_of_nodes, push_queue):
    """
    Pull protocol implementation function.

    Args:
        config_json (dict[str, Any]): JSON object with all-nodes configuration.
        node_state (dict[str, Any]): The state of this current node.
        state_lock (threading.Lock): The lock object for thread-safety of the state.
        this_port (int): The port this node listens.
        number_of_nodes (int): The total number of nodes in the network (if known).
        push_queue (queue.Queue): The queue for messages to be pushed to other node(s).
    """    

    # Request for information/update (a.k.a. "polling" message)
    msg = {
        "op": "pull",
        "data": {},
        "metadata": {
            "relay": 0
        }
    }
    msg["metadata"]["relay"] = this_port
    
    if(not node_state["active"]):#if node is not active ie off dont do anything
        return;

    neighbors = node_state["neighbor_nodes"]
    # Take a random sample of one from the list of other nodes.
    fanout = config_json["pull_fanout_value"]
    
    #Acquire a state lock as we are accesing the nodes state and modifying it
    #releasing state lock as we are no longer performing operations on the nodes state
    # Send the polling (pull) request to the single randomly selected node from the list of other nodes
    target_port = 0
    resp = 0
    node_sample = select_neighbor(config_json, node_state, state_lock, this_port, fanout)
    while (node_sample):
        target_port = node_sample.pop()
        ping_msg = time.time()
        print("pull is working2")
        resp = egess_api.send_msg(config_json, node_state, state_lock, this_port, msg, target_port)
        print("pull is working3")
        if(not resp is None and resp["metadata"]["active"]):
            print("pull is working")
            latency = time.time() - ping_msg
            index = node_state["neighbor_nodes"].index(target_port)
            weight = config_json["latency_weight"]
            node_state["latency_matrix"][index] = (weight * latency) + (1 - weight) * node_state["latency_matrix"][index]
            print("MESSAGE FORWARDED {} {}\n".format(str(target_port), str(this_port)))
            state_lock.acquire()
            node_state["known_leadership"][neighbors.index(target_port)] = [resp["data"]["node_state"]["leadership"], time.time()]
            node_state["leadership"] = max(node_state["leadership"] - .05, -1)
            egess_api.write_state_change_data_point(this_port, node_state, "leadership")
            fanout -= 1
            incoming_msg = resp["data"]["node_state"]["seen_messages"]
            for msg_id in incoming_msg:
                if msg_id not in node_state["seen_messages"]:
                    node_state["seen_messages"].append(msg_id)
                    node_state["accepted_messages"] += 1
                    egess_api.write_data_point(this_port, "message_accepted", "id={}".format(msg_id))
                    egess_api.write_state_change_data_point(this_port, node_state, "accepted_messages")
                    egess_api.write_data_point(this_port, "message_accepted", "from={}".format(target_port))
            state_lock.release()
        else:
            state_lock.acquire()
            index = node_state["neighbor_nodes"].index(target_port)
            node_state["neighbor_nodes"].pop(index)
            node_state["known_leadership"].pop(index)
            msg["data"]["leadership_matrix"] = node_state["known_leadership"]
            msg["data"]["neighbor_nodes"] = node_state["neighbor_nodes"]
            state_lock.release()
            node_sample.extend(select_neighbor(config_json, node_state, state_lock, this_port, fanout))
    

    # merge retrieved message data into current leadership matrix
    other_leadership = resp["data"]["node_state"]["known_leadership"]
    other_neighbors  = resp["data"]["node_state"]["neighbor_nodes"]
    #meant to get index of self to pop out of their neighbors for combining if we are in their neighbors list
    if this_port in resp["data"]["node_state"]["neighbor_nodes"]:
        index = resp["data"]["node_state"]["neighbor_nodes"].index(this_port)
        other_leadership.pop(index)
        other_neighbors.pop(index)
    #leadership var holds this nodes leadership matrix
    #neighbors var holds this nodes neighbors
    i = 0
    j = 0
    leadership = node_state["known_leadership"]
    while i < len(neighbors) and j < len(other_neighbors):
        if neighbors[i] < other_neighbors[j]:
            i += 1
        elif neighbors[i] > other_neighbors[j]:
            j += 1
        else:
            if leadership[i][1] < other_leadership[j][1]:
                leadership[i] = other_leadership[j]
            i += 1
            j += 1
    egess_api.log_current_node_state(this_port,node_state)

    # returns a list of valid neighbors based on leadership formulas, config fanout, and dead nodes.
def select_neighbor(config_json, node_state, state_lock, this_port, fanout):
    state_lock.acquire()
    neighbors = node_state["neighbor_nodes"]
    if(abs(node_state["leadership"]) * .3 + .5 > random.random()):
        index = 0
        value = 0
        for j in range(len(neighbors)):
            value = (node_state["known_leadership"][index][0])/(node_state["latency_matrix"][index] + .0000001)
            index = index if value < node_state["known_leadership"][j][0]/(node_state["latency_matrix"][j] + .0000001) else j 
        node_sample.append(neighbors[index]) 
    else:
        node_sample = random.sample(neighbors, 1)
    state_lock.release()
    return node_sample

