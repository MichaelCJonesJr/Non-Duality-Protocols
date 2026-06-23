#first arg is number of nodes
import sys
import random
size = int(sys.argv[1])
node_list = list(range(9000, size + 9000))
random.shuffle(node_list)
adjacency_list = [[] for _ in range(size)]
density = .5
if len(sys.argv) > 2:
    density = float(sys.argv[2])
    print("non default value used for node density")
edges = int(((size * (size - 1) / 2) - size - 1) * density) #calculated number of edges
#first scramble and linear connect for baseline of 2 neighbors
for i in range(size):
    adjacency_list[node_list[i] - 9000].append(node_list[((i + 1) % size)]) #node connects to neighbor
    adjacency_list[node_list[((i + 1) % size)] - 9000].append(node_list[i]) #neighbor connects to node

random.shuffle(node_list) #scramble again
i = 0
while edges > 0:
    if random.random() < 0.7:
        step = random.randint(2, 5) #short range connection
    else:
        step = random.randint(min(6, size - 1), max(6, size - 1)) #long range connection

    if (i + step) % size != i and node_list[((i + step) % size)] not in adjacency_list[node_list[i] - 9000]:
            adjacency_list[node_list[i] - 9000].append(node_list[((i + step) % size)])
            adjacency_list[node_list[((i + step) % size)] - 9000].append(node_list[i])
            edges = edges - 1

    i = (i + 1) % size
    
for neighbors in adjacency_list:
    neighbors.sort()
    print(neighbors)