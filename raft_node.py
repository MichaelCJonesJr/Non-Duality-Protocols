import sys
import os
import time
from pysyncobj import SyncObj, replicated, SyncObjConf

class RaftNode(SyncObj):
    def __init__(self, self_addr, partner_addrs):
        conf = SyncObjConf(journalFile=None, fullDumpFile=None)
        super(RaftNode, self).__init__(self_addr, partner_addrs, conf=conf)
        self.addr = self_addr 
        self.__storage = []

    @replicated
    def add_data(self, value):
        self.__storage.append(value)
        if self.addr is not None:
            port = self.addr.split(':')[-1]
            try:
                with open(f"node_{port}.log", "a") as f:
                    f.write(f"{value}|{time.time()}\n")
            except IOError:
                pass

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)

    my_port = sys.argv[1]
    partners = [f"127.0.0.1:{p}" for p in sys.argv[2:]]
    
    node = RaftNode(f"127.0.0.1:{my_port}", partners)
    print(f"[*] Node active on port {my_port}.")

    try:
        while True:
            time.sleep(2) # 2-second interval for readable logs
            leader = node._getLeader()
            # Safely extract the ID whether it's an object, string, or None
            leader_id = getattr(leader, 'id', str(leader)) if leader else "NONE (Election)"
            
            print(f"[NODE {my_port}] Thinks Leader is: {leader_id}")
            
    except KeyboardInterrupt:
        sys.exit(0)