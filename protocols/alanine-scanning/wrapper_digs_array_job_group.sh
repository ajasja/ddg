#!/bin/bash
#SBATCH -p short 
#SBATCH --mem=4g 

GROUP_SIZE=${GROUP_SIZE:-10}
echo "GROUP SIZE IS: $GROUP_SIZE"

for I in $(seq 1 $GROUP_SIZE)
do
    echo "Hello from job $SLURM_JOB_ID on $(hostname) at $(date)"
    echo "PWD:"
    pwd
    echo ""
    J=$(($SLURM_ARRAY_TASK_ID * $GROUP_SIZE + $I - $GROUP_SIZE))
    CMD=$(sed -n "${J}p" $1)
    echo "COMMAND: ${CMD}"
    eval ${CMD}
done


#####command:
#####sbatch -a 1-$(cat 01_run_filter.tasks|wc -l) digs_array_job.sh 01_run_filter.tasks
