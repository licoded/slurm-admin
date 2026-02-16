#!/bin/bash
#SBATCH -J train_model
#SBATCH -o /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/train_%j.out
#SBATCH -e /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/train_%j.err
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH --time=48:00:00

# Example ML training job with slm monitoring

set -e

echo "========================================"
echo "Training Job Configuration"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $SLURM_JOB_NODELIST"
echo "GPU: $CUDA_VISIBLE_DEVICES"
echo "========================================"

# Activate your conda/virtual environment if needed
# source /path/to/conda/etc/profile.d/conda.sh
# conda activate myenv

# Wrap the training command with slm run
uv run slm run -- bash <<'EOF'

set -e

echo "Starting training at $(date)"

# Your training command here
# Example: python train.py --config config.yaml --epochs 100

# Simulated training
echo "Epoch 1/100: loss=2.345"
sleep 5
echo "Epoch 2/100: loss=1.987"
sleep 5
echo "Epoch 3/100: loss=1.654"
sleep 5

echo "Training completed at $(date)"
echo "Model saved to: /path/to/model.pth"

EOF

echo "Training job script finished"
