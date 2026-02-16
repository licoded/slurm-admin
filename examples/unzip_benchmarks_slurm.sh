#!/bin/bash
#SBATCH -J unzip_benchmarks
#SBATCH -o /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/unzip_benchmarks_%j.out
#SBATCH -e /public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/logs/unzip_benchmarks_%j.err
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH --time=24:00:00

# Exit on error
set -e

# Configuration
ZIP_FILE="/public/home/jwli/workSpace/yongkang26/datasets/benchmarks.zip"
OUTPUT_DIR="/public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/output/benchmarks"

# Create output directory
mkdir -p "$OUTPUT_DIR"
mkdir -p "$(dirname "$SLURM_JOB_NODELIST")"

echo "========================================"
echo "Job Information:"
echo "Job ID: $SLURM_JOB_ID"
echo "Job Name: $SLURM_JOB_NAME"
echo "Node: $SLURM_JOB_NODELIST"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "========================================"

# --- KEY: Wrap the core logic with slm run ---
/public/home/jwli/workSpace/yongkang26/26Feb-labs/slurm-admin/slm run -- bash <<'EOF'

set -e

echo "Starting extraction at $(date)"
echo "Source: $ZIP_FILE"
echo "Target: $OUTPUT_DIR"

# Check if zip file exists
if [ ! -f "$ZIP_FILE" ]; then
    echo "Error: ZIP file not found: $ZIP_FILE"
    exit 1
fi

# Extract files (excluding .tlsf files)
echo "Extracting files..."
unzip -q "$ZIP_FILE" -d "$OUTPUT_DIR" -x "*.tlsf"

# Count extracted files
file_count=$(find "$OUTPUT_DIR" -type f | wc -l)
echo "Total files extracted: $file_count"

# Show disk usage
echo "Disk usage:"
du -sh "$OUTPUT_DIR"

echo "Extraction completed successfully at $(date)"

EOF
# --- End of slm run wrapper ---
