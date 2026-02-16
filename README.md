# Slurm Lifecycle Monitor (SLM)

A low-coupling, high-reusability Python CLI tool for monitoring Slurm job lifecycle events.

## 🎯 Core Philosophy

**Zero pollution to existing logic** - You don't need to modify your complex shell scripts. Just wrap them with `slm run` and get automatic lifecycle monitoring.

## 🏗️ Architecture

Two-layer decoupled design:

### 1. Submission Layer (`slm submit`)
- Sends "SUBMITTED" notification
- Delegates to actual `sbatch` command
- Captures submission failures

### 2. Execution Layer (`slm run`)
- Wraps your core logic
- Captures signals (suspend/resume/terminate)
- Monitors exit status
- Sends webhook notifications for all lifecycle events

## 📦 Installation

### Using uv (Recommended)

```bash
# Install dependencies (includes urllib3<2.0 for OpenSSL 1.0.2 compatibility)
uv sync

# Make slm.py executable
chmod +x slm
```

**Note**: For systems with OpenSSL 1.0.2 (common in older HPC environments), the project automatically uses `urllib3<2.0` for compatibility.

### Manual Installation

```bash
# Install dependencies
pip install requests "urllib3<2.0"

# Or using pip
pip install -r requirements.txt
```

## ⚙️ Configuration

Set your webhook URL via environment variable:

```bash
# Add to ~/.bashrc or ~/.zshrc
export SLM_WEBHOOK="https://your-webhook-url.com"

# Or use command-line argument
slm --webhook "https://your-webhook-url.com" run -- python script.py
```

## 🚀 Usage

### Basic Pattern

```bash
# 1. Submit a job (captures SUBMITTED status)
uv run slm submit job_script.sh

# 2. In your job script, wrap logic with slm run
uv run slm run -- bash <<'EOF'
# Your original shell code here
echo "Processing..."
python my_script.py
EOF
```

### Example 1: Simple Job

```bash
#!/bin/bash
#SBATCH -J simple_test
#SBATCH -c 2
#SBATCH --mem=4G

# Wrap your command
uv run slm run -- python3 -c "
import time
for i in range(5):
    print(f'Step {i+1}/5')
    time.sleep(2)
"
```

Submit the job:
```bash
# Option 1: Direct sbatch (no SUBMITTED notification)
sbatch simple_job.sh

# Option 2: Use slm submit (with SUBMITTED notification)
uv run slm submit simple_job.sh
```

### Example 2: Complex Pipeline

```bash
#!/bin/bash
#SBATCH -J data_pipeline
#SBATCH -c 8
#SBATCH --mem=32G

set -e

# Your entire pipeline wrapped with slm
uv run slm run -- bash <<'EOF'

set -e  # Exit on error

echo "Starting pipeline..."
# Step 1: Data preparation
python prepare_data.py

# Step 2: Processing
python process.py --input data/raw --output data/processed

# Step 3: Validation
python validate.py --data data/processed

echo "Pipeline completed!"

EOF
```

### Example 3: Training Job

```bash
#!/bin/bash
#SBATCH -J train_model
#SBATCH -p gpu
#SBATCH --gres=gpu:1

# Activate your environment
source ~/.bashrc
conda activate myenv

# Wrap training command
uv run slm run -- python train.py --config config.yaml --epochs 100
```

## 📡 Monitored Events

| Event | Trigger | Emoji | Signal |
|-------|---------|-------|--------|
| SUBMITTED | Job submitted to Slurm | 📤 | - |
| RUNNING | Job starts execution | ▶️ | - |
| PAUSED | Job suspended by admin | ⏸️ | SIGTSTP |
| RESUMED | Job resumed | ▶️ | SIGCONT |
| TERMINATING | Job cancelled/timeout | ⏹️ | SIGTERM |
| COMPLETED | Job finished successfully | ✅ | exit 0 |
| FAILED | Job failed | ❌ | exit != 0 |

## 🧪 Testing

Test webhook connectivity:

```bash
# Test with simple command
uv run slm run -- echo "Hello, Slurm!"

# Test signal handling
uv run slm run -- bash -c 'echo "Starting..."; sleep 30; echo "Done"'
```

In another terminal:
```bash
# Find the process and send signals
kill -TSTP <pid>   # Should send PAUSED notification
kill -CONT <pid>   # Should send RESUMED notification
kill -TERM <pid>   # Should send TERMINATING notification
```

## 📁 Project Structure

```
slurm-admin/
├── slm.py                    # Core SDK
├── pyproject.toml           # Project config (uv)
├── examples/
│   ├── simple_job.sh        # Simple example
│   ├── unzip_benchmarks_slurm.sh  # File extraction job
│   └── train_model.sh       # ML training job
├── logs/                    # Slurm output logs (auto-created)
└── README.md
```

## 🔧 Advanced Usage

### Custom Webhook Format

Modify `SlmSDK.send_webhook()` in `slm.py` to customize payload format for your webhook provider (Feishu, Slack, Discord, etc.).

### Signal Handling

The following signals are automatically captured:
- `SIGTSTP` (Ctrl+Z or `scontrol suspend`)
- `SIGCONT` (`scontrol resume`)
- `SIGTERM` (`scancel` or timeout)
- `SIGINT` (Ctrl+C)

### Exit Codes

- `0`: Success → COMPLETED
- `143`: SIGTERM (128+15) → TERMINATING
- Other: FAILED with exit code

## 🤝 Integration with Existing Scripts

To integrate `slm` into your existing scripts with **minimal changes**:

### Before (Original Script)
```bash
#!/bin/bash
#SBATCH -J myjob

# Your complex logic
python script.py
./another_script.sh
```

### After (With SLM)
```bash
#!/bin/bash
#SBATCH -J myjob

# Just wrap it with slm run
uv run slm run -- bash <<'EOF'
# Your complex logic (unchanged)
python script.py
./another_script.sh
EOF
```

That's it! No need to modify your original logic.

## 📝 Benefits

1. **Zero Logic Pollution**: Your shell scripts remain unchanged
2. **Signal Awareness**: Detects suspend/resume/cancel events
3. **Low Coupling**: Easy to remove/replace
4. **High Reusability**: One tool for all your Slurm jobs
5. **Environment Isolation**: Configuration via environment variables
6. **Extensible**: Easy to customize webhook format

## 🐛 Troubleshooting

### Webhook not sending
- Check `SLM_WEBHOOK` environment variable
- Verify network connectivity
- Check `requests` module is installed: `uv add requests`

### Signal handling not working
- Ensure you're using `slm run` wrapper
- Check if signal is sent to correct process

### Job always shows FAILED
- Check your command's exit code
- Ensure `set -e` is used if you want to fail on errors

## 📄 License

MIT License - Feel free to use and modify for your needs.

## 🙏 Acknowledgments

Designed for low-coupling lifecycle monitoring in HPC environments with Slurm workload manager.
