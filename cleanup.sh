#!/bin/bash
# Targets python processes specifically related to your nodes/raft to avoid killing background OS tasks
pkill -9 -f "python.*node"
pkill -9 -f "python.*raft"
pkill -9 -f "python.*research"

# Wipes the data directory so old CSV artifacts don't pollute the next graph
rm -f resulteddata/*.csv
rm -f resulteddata/*.log
rm -f resulteddata/*.dat
rm -f *.log
