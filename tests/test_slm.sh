#!/bin/bash
# Test script for SLM - Run this locally (without Slurm) to verify setup

echo "========================================="
echo "Slurm Lifecycle Monitor - Test Suite"
echo "========================================="
echo ""

# Check if Python is available
python_bin="/public/home/jwli/python3/bin/python3"
if [ ! -f "$python_bin" ]; then
    echo "❌ Error: Python not found at $python_bin"
    exit 1
fi

echo "✅ Python found at $python_bin"
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
if $python_bin -c "import pymysql" 2>/dev/null; then
    echo "✅ pymysql module is installed"
else
    echo "⚠️  pymysql module not found. Install: $python_bin -m pip install pymysql"
fi
echo ""

# Test 1: Basic command execution
echo "Test 1: Basic command execution"
./slm run -- echo "Hello from SLM!"
echo ""

# Test 2: Python script
echo "Test 2: Python script execution"
./slm run -- $python_bin -c "
import sys
print('Python version:', sys.version_info.major)
print('Test passed!')
"
echo ""

# Test 3: Command with arguments
echo "Test 3: Command with multiple arguments"
./slm run -- bash -c "
echo 'Line 1'
echo 'Line 2'
echo 'Line 3'
"
echo ""

# Test 4: Error handling
echo "Test 4: Error handling (should show FAILED)"
./slm run -- $python_bin -c "import sys; sys.exit(1)"
echo ""

# Test 5: Long-running command (interrupt with Ctrl+C to test signal)
echo "Test 5: Signal handling test"
echo "Starting 30-second job... (Press Ctrl+C to test SIGINT handling)"
echo "Note: This test requires manual intervention"
echo ""
read -p "Press Enter to start, or Ctrl+C to skip..."
./slm run -- bash -c "
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
