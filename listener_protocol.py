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
# This file implements the listener protocol of the node. This protocol
# is triggered each time the node receives a message (in JSON format).
# -------------------------------------------------------------------------

#This handles incoming to curr node

import egess_api # Used for invoking commonly used EGESS API functions
import time #used for time stamping message data


def listener_protocol(config_json, node_state, state_lock, this_port, number_of_nodes, push_queue, msg):
    """
    Listener protocol function.

    Args:
        config_json (dict[str, Any]): JSON object with all-nodes configuration.
        node_state (dict[str, Any]): The state of this current node.
        state_lock (threading.Lock): The lock object for thread-safety of the state.
        this_port (int): The port this node listens.
        number_of_nodes (int): The total number of nodes in the network (if known).
        push_queue (queue.Queue): The queue for messages to be pushed to other node(s).
        msg (dict[str, Any]): JSON object received via POST protocol.
    """    
    if msg["op"] == "pull": # Indicates that the message is a "pull" request
        print("red red")
        egess_api.write_data_point(msg["metadata"]["relay"], "message_sent", "to={}".format(this_port))
        if(not node_state["active"]):#if node is not active ie off dont do anything
            print("inactive port ", this_port, " has been pulled")
            return {
                "op": "receipt",
                "data": {
                    "success": False,
                    "message": "Node is asleep"
                },
                "metadata": {
                    "active" : False
                }
            };
        print("PULL REQUEST RECEIVED at port:", this_port," during this time: ",time.time()) # Log receiving the request
        # And add it to the data storage with "pull_request_received" type
        egess_api.write_data_point(this_port, "pull_request_received", msg["metadata"]["relay"])

        #acquire and release state lock to increase leadership value from node interactions
        state_lock.acquire()
        node_state["leadership"] = min(node_state["leadership"] + .05, 1)
        egess_api.write_state_change_data_point(this_port, node_state, "leadership")
        state_lock.release()

        # Pull requests are basically requests for updates, and they are
        # to be responded immediately within the same session. This response,
        # for example, sends the state of the current node to the pull requester.
        # Each message, regardless of purpose, must be a JSON object with three keys:
        # 1) op - singifying the type of operation;
        # 2) data - signifying the payload;
        # 3) metadata - providing some transport information about he message itself.
        return {
            "op": "receipt",
            "data": {
                "success": True,
                "message": "",
                "node_state": node_state,
            },
            "metadata": {
                "active" : True
            }
        }
    elif msg["op"] == "push": # If the message is a "push" message
        if(not node_state["active"]):#if node is not active ie off dont do anything
            print("inactive port ", this_port, " has been pulled")
            return {
                "op": "receipt",
                "data": {
                    "success": False,
                    "message": "Node is asleep"
                },
                "metadata": {
                    "active" : False
                }
            };
        # Safeguard prefenting the message from being forwarded forever
        if msg["metadata"]["forward_count"] < config_json["max_forwards"]:
            # We are going to access the state of the node, so we have to lock it first
            # If we are here, the push message has been accepted. Increment the number
            # of accepted messages in the state and increase leadership value as other nodes are interacting with the current node.
            #merge known leadership lists according to time priority.
            if(msg["metadata"]["relay"] != 0):
                egess_api.write_data_point(msg["metadata"]["relay"], "message_sent", "to={}".format(this_port))
                state_lock.acquire()
                node_state["leadership"] = min(node_state["leadership"] + .05, 1)
                egess_api.write_state_change_data_point(this_port, node_state, "leadership")
                if msg["metadata"]["msg_id"] not in node_state["seen_messages"]:
                    node_state["seen_messages"].append(msg["metadata"]["msg_id"])
                    node_state["accepted_messages"] = node_state["accepted_messages"] + 1
                    # Add the state change data point.
                    egess_api.write_data_point(this_port, "message_accepted", "id={}".format(msg["metadata"]["msg_id"]))
                    egess_api.write_state_change_data_point(this_port, node_state, "accepted_messages")
                    # Record accept event for visualization
                    egess_api.write_data_point(this_port, "message_accepted", "from={}".format(msg["metadata"]["relay"]))

                # The parameter metadata.relay stores the port (node ID) of the node that forwarded the message.
                # If this node hasn't seen this relay before, add it to the list of known nodes in the state
                # of the node. However, if the relay is 0, it means that the message is not forwarded, so we
                # should not add it to the list of known nodes.
                if msg["metadata"]["relay"] not in node_state["neighbor_nodes"]:
                    node_state["neighbor_nodes"].append(msg["metadata"]["relay"])
                    node_state["known_leadership"].append([msg["metadata"]["leadership"], time.time()])
                    # Add the state change data point.
                    egess_api.write_state_change_data_point(this_port, node_state, "neighbor_nodes")
                state_lock.release()
                #checks that it isnt initial message and its safe to try a merge
                index = msg["data"]["neighbor_nodes"].index(this_port)#meant to get index of self to pop out of their neighbors for combining
                state_lock.acquire()
                neighbors = node_state["neighbor_nodes"]
                leadership = node_state["known_leadership"]
                other_leadership = msg["data"]["leadership_matrix"]
                node_state["known_leadership"][neighbors.index(msg["metadata"]["relay"])] = [msg["metadata"]["leadership"], time.time()] #updates based on appended piggy back value carrying self leadrship during push
                state_lock.release()
                other_neighbors = msg["data"]["neighbor_nodes"]
                other_leadership.pop(index)
                other_neighbors.pop(index)
                #leadership var holds this nodes leadership matrix
                #neighbors var holds this nodes neighbors
                i = 0
                j = 0
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
                # We finished the atomic access to the state of the node; now allow other threads to access it.
                node_state["known_leadership"] = leadership
            else:
                    state_lock.acquire()
                    if msg["metadata"]["msg_id"] not in node_state["seen_messages"]:
                        node_state["seen_messages"].append(msg["metadata"]["msg_id"])
                        node_state["accepted_messages"] = node_state["accepted_messages"] + 1
                        # Add the state change data point.
                        egess_api.write_data_point(this_port, "message_accepted", "id={}".format(msg["metadata"]["msg_id"]))
                        egess_api.write_state_change_data_point(this_port, node_state, "accepted_messages")
                    state_lock.release()
            # The forward count and the relay port are stored in the metadata of the message.
            # The metadata field allows not to contaminate the data with transportation-related
            # parameters. This may be important if the data is digitally signed by the original sender.
            
            # Before we push the message to the push queue for further forwarding, we have to update the
            # metadata of the message. First, we record that the message is coming from this port.
            msg["metadata"]["relay"] = this_port

            # Second, we increment the forwarding count to make sure that the message is not forwarded
            # within the network forever.
            msg["metadata"]["forward_count"] = msg["metadata"]["forward_count"] + 1

            # Add the message to the push queue. It will be received by the push thread and processed
            # by the push protocol.
            push_queue.put(msg)

            # The returned message will be sent back to the caller as a response.
            return {
                "op": "receipt",
                "data": {
                    "success": True,
                    "message": "message enqueued",
                },
                "metadata": {
                    "active" : True
                }
            }
        else:
            # If the maximum number of forwards has been reached, the message will no longer be
            # pushed forward
            return {
                "op": "receipt",
                "data": {
                    "success": False,
                    "message": "message is not enqueued"
                },
                "metadata": {
                    "active" : True
                }
            }
    elif msg["op"] == "sleep":
        node_state["active"] = False
        egess_api.log_current_node_state(this_port,node_state)
        return {
            "op": "receipt",
            "data": {
                "success": True,
                "message": "Node is asleep"
            },
            "metadata": {
                "active" : False
            }};
    elif msg["op"] == "revive":
        node_state["active"] = True
        egess_api.log_current_node_state(this_port,node_state)
        return {
            "op": "receipt",
            "data": {
                "success": True,
                "message": "Node is revived"
                },
            "metadata": {
                "active" : False
                }};
    else: # The listener protocol must not receive any other types of messages
        print("ERROR: listener_protocol: unknown type of message: {}\n".format(msg["op"]))
        return {
                "op": "receipt",
                "data": {
                    "success": False,
                    "message": "unknown operation"
                },
                "metadata": {}
            }
