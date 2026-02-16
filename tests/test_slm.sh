#!/bin/bash
# Test script for SLM - Run this locally (without Slurm) to verify setup

echo "========================================="
echo "Slurm Lifecycle Monitor - Test Suite"
echo "========================================="
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' not found. Please install uv first."
    echo "   Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv is installed"
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
if uv run python -c "import pymysql" 2>/dev/null; then
    echo "✅ pymysql module is installed"
else
    echo "⚠️  pymysql module not found. Run 'uv sync' to install."
fi
echo ""

# Test 1: Basic command execution
echo "Test 1: Basic command execution"
uv run slm run -- echo "Hello from SLM!"
echo ""

# Test 2: Python script
echo "Test 2: Python script execution"
uv run slm run -- python -c "
import sys
print('Python version:', sys.version_info.major)
print('Test passed!')
"
echo ""

# Test 3: Command with arguments
echo "Test 3: Command with multiple arguments"
uv run slm run -- bash -c "
echo 'Line 1'
echo 'Line 2'
echo 'Line 3'
"
echo ""

# Test 4: Error handling
echo "Test 4: Error handling (should show FAILED)"
uv run slm run -- python -c "import sys; sys.exit(1)"
echo ""

# Test 5: Long-running command (interrupt with Ctrl+C to test signal)
echo "Test 5: Signal handling test"
echo "Starting 30-second job... (Press Ctrl+C to test SIGINT handling)"
echo "Note: This test requires manual intervention"
echo ""
read -p "Press Enter to start, or Ctrl+C to skip..."
uv run slm run -- bash -c "
for i in {1..30}; do
    echo \"Progress: \$i/30\"
    sleep 1
done
echo 'Test completed!'
"
echo ""

echo "========================================="
echo "Test suite completed!"
echo "========================================="
echo ""
echo "If you configured a webhook URL, check your notifications."
echo "Otherwise, you should see [SLM] status messages above."
echo ""
echo "Next steps:"
echo "1. Configure webhook: export SLM_WEBHOOK='https://your-url.com'"
echo "2. Submit a test job: sbatch examples/simple_job.sh"
echo "3. Check QUICKSTART.md for more examples"
