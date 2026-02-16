#!/bin/bash
#SBATCH -J simple_test
#SBATCH -o /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/simple_%j.out
#SBATCH -e /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/simple_%j.err
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH --time=00:10:00

# A simple example job that demonstrates slm monitoring

echo "Starting simple test job..."
echo "Job ID: $SLURM_JOB_ID"

# Wrap your command with slm run
uv run slm run -- python3 -c "
import time
import sys

print('Processing task...')
for i in range(5):
    print(f'Step {i+1}/5')
    time.sleep(2)

print('Task completed!')
"

echo "Job script finished"
