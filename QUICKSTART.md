# Quick Start Guide

## 1. Setup (5 minutes)

### Install dependencies
```bash
uv sync
```

### Configure webhook
```bash
# Option 1: Environment variable (recommended)
export SLM_WEBHOOK="https://your-webhook-url.com"

# Option 2: Add to ~/.bashrc for persistence
echo 'export SLM_WEBHOOK="https://your-webhook-url.com"' >> ~/.bashrc
source ~/.bashrc
```

## 2. Test the installation

```bash
# Test basic command
uv run slm.py run -- echo "Test successful!"

# Test with Python
uv run slm.py run -- python -c "print('Python test!')"
```

## 3. Create your first monitored job

### Step 1: Create a job script
```bash
cat > my_first_job.sh <<'EOF'
#!/bin/bash
#SBATCH -J my_first_job
#SBATCH -o logs/my_first_job_%j.out
#SBATCH -e logs/my_first_job_%j.err
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH --time=00:05:00

echo "Starting job..."
echo "Job ID: $SLURM_JOB_ID"

# Wrap your command with slm run
uv run /path/to/slurm-admin/slm.py run -- python -c "
import time
print('Processing...')
time.sleep(10)
print('Done!')
"

echo "Job finished!"
EOF

chmod +x my_first_job.sh
```

### Step 2: Submit the job
```bash
# Option 1: Direct sbatch (no SUBMITTED notification)
sbatch my_first_job.sh

# Option 2: Use slm submit (with SUBMITTED notification)
uv run /path/to/slurm-admin/slm.py submit my_first_job.sh
```

### Step 3: Monitor the job
```bash
# Check job status
squeue -u $USER

# View output logs
tail -f logs/my_first_job_*.out

# If you configured a webhook, check your notifications
```

## 4. Test signal handling

```bash
# Submit a long-running job
cat > long_job.sh <<'EOF'
#!/bin/bash
#SBATCH -J long_job
#SBATCH -c 1
#SBATCH --time=01:00:00

uv run /path/to/slurm-admin/slm.py run -- bash -c '
echo "Starting long job..."
for i in {1..60}; do
    echo "Step $i/60"
    sleep 10
done
echo "Job completed!"
'
EOF

chmod +x long_job.sh
sbatch long_job.sh

# Wait for job to start, then test signals
JOB_ID=$(squeue -u $USER -h -j long_job -o %A)
echo "Testing signals on job $JOB_ID"

# Pause the job
scontrol suspend $JOB_ID
# Check: You should receive a PAUSED notification

# Resume the job
scontrol resume $JOB_ID
# Check: You should receive a RESUMED notification

# Cancel the job
scancel $JOB_ID
# Check: You should receive a TERMINATING notification
```

## 5. Integrate into your existing scripts

### Before (Original Script)
```bash
#!/bin/bash
#SBATCH -J my_script
#SBATCH -c 4

# Your existing logic
python process.py
./analyze.sh
```

### After (With SLM - 2 lines changed)
```bash
#!/bin/bash
#SBATCH -J my_script
#SBATCH -c 4

# Add this wrapper
uv run /path/to/slurm-admin/slm.py run -- bash <<'EOF'

# Your existing logic (unchanged)
python process.py
./analyze.sh

EOF
# End wrapper
```

That's it! Your script now has full lifecycle monitoring.

## 6. Common patterns

### Pattern 1: Python training job
```bash
#!/bin/bash
#SBATCH -J train
#SBATCH -p gpu
#SBATCH --gres=gpu:1

source ~/.bashrc
conda activate myenv

uv run /path/to/slurm-admin/slm.py run -- python train.py --epochs 100
```

### Pattern 2: Data processing pipeline
```bash
#!/bin/bash
#SBATCH -J process_data
#SBATCH -c 8

uv run /path/to/slurm-admin/slm.py run -- bash <<'EOF'
set -e  # Exit on error

python download.py
python extract.py
python transform.py
python load.py
EOF
```

### Pattern 3: ML inference batch job
```bash
#!/bin/bash
#SBATCH -J inference
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH --array=0-99

uv run /path/to/slurm-admin/slm.py run -- python inference.py \
    --input batch_$SLURM_ARRAY_TASK_ID \
    --output result_$SLURM_ARRAY_TASK_ID
```

## 7. Troubleshooting

### Problem: Command not found
```bash
# Solution: Use absolute path or add to PATH
export PATH="/path/to/slurm-admin:$PATH"
```

### Problem: Webhook not sending
```bash
# Check environment variable
echo $SLM_WEBHOOK

# Test webhook connectivity
curl -X POST $SLM_WEBHOOK -H "Content-Type: application/json" \
  -d '{"msg_type":"text","content":{"text":"Test message"}}'
```

### Problem: Signal handling not working
- Ensure you're using `slm run` wrapper
- Check if you're sending signals to correct job
- Remember: signals only work when job is running (not pending)

## 8. Next steps

- Check `examples/` directory for more examples
- Customize webhook format in `slm.py` for your needs
- Add SLM to all your critical Slurm jobs
- Set up webhook to send to your team's chat channel

## 9. Cheat Sheet

```bash
# Submit job with notification
uv run slm.py submit script.sh

# Run command with monitoring
uv run slm.py run -- python script.py

# Run bash script with monitoring
uv run slm.py run -- bash script.sh

# Run inline bash with monitoring
uv run slm.py run -- bash <<'EOF'
# Your commands here
EOF

# Pause/Resume job
scontrol suspend <job_id>
scontrol resume <job_id>

# Cancel job
scancel <job_id>
```
