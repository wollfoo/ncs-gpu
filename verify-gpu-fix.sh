#!/bin/bash
# verify-gpu-fix.sh - Script kiểm tra GPU clocks và hashrate sau khi fix

echo "========================================="
echo "GPU Mining Hashrate Fix Verification"
echo "========================================="
echo ""

# 1. Check environment variables
echo "📋 Environment Variables:"
echo "------------------------"
env | grep -E "MIN_SM_CLOCK|MIN_POWER|MIN_MEM|ALLOW_CLOCK_LOCK|GPU_CLOSED_LOOP" | sort
echo ""

# 2. Check current GPU status
echo "🎮 Current GPU Status:"
echo "----------------------"
nvidia-smi --query-gpu=index,name,clocks.current.sm,clocks.current.memory,power.draw,utilization.gpu,temperature.gpu --format=csv
echo ""

# 3. Check GPU clocks in detail
echo "⏰ GPU Clock Details:"
echo "--------------------"
nvidia-smi -q -d CLOCK | grep -E "Graphics|SM|Memory|Video" | head -20
echo ""

# 4. Check power limits
echo "⚡ Power Limits:"
echo "---------------"
nvidia-smi -q -d POWER | grep -E "Power Limit|Default Power|Max Power" | head -10
echo ""

# 5. Check recent logs for hashrate
echo "📊 Recent Hashrate (last 20 entries):"
echo "------------------------------------"
if [ -f /home/azureuser/opus-gpu/mining_debug.log ]; then
    grep -E "MH/s|hashrate" /home/azureuser/opus-gpu/mining_debug.log | tail -20
else
    echo "Log file not found at /home/azureuser/opus-gpu/mining_debug.log"
fi
echo ""

# 6. Check for clock adjustment errors
echo "⚠️ Clock Adjustment Issues (last 10):"
echo "-------------------------------------"
if [ -f /home/azureuser/opus-gpu/mining_debug.log ]; then
    grep -E "Clock adjustment limited|util too low|Skipping clock lock" /home/azureuser/opus-gpu/mining_debug.log | tail -10
else
    echo "No issues found or log file missing"
fi
echo ""

# 7. Force baseline clocks manually (optional)
echo "🔧 Manual Baseline Enforcement Commands:"
echo "----------------------------------------"
echo "To manually set baseline clocks, run:"
echo "  nvidia-smi -pm 1                    # Enable persistence mode"
echo "  nvidia-smi -pl 120                  # Set power limit to 120W"
echo "  nvidia-smi -lgc 1200,1200           # Lock SM clock to 1200MHz"
echo ""

# 8. Summary
echo "📈 Expected After Fix:"
echo "---------------------"
echo "  SM Clock: 1200+ MHz (stable)"
echo "  Memory Clock: 877+ MHz"
echo "  Power: 120-150W"
echo "  Hashrate: 35-40 MH/s"
echo ""
echo "📉 Before Fix (problematic):"
echo "---------------------------"
echo "  SM Clock: 435-480 MHz"
echo "  Power: 36-72W"
echo "  Hashrate: 10-12 MH/s"
echo ""

# 9. Quick health check
echo "✅ Quick Health Check:"
echo "---------------------"
current_sm=$(nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits | head -1)
if [ "$current_sm" -ge 1200 ]; then
    echo "✓ SM Clock OK: ${current_sm} MHz (>= 1200)"
else
    echo "✗ SM Clock LOW: ${current_sm} MHz (< 1200) - NEEDS FIX!"
fi

current_power=$(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits | head -1 | cut -d'.' -f1)
if [ "$current_power" -ge 100 ]; then
    echo "✓ Power OK: ${current_power}W (>= 100)"
else
    echo "✗ Power LOW: ${current_power}W (< 100) - NEEDS FIX!"
fi
echo ""

echo "========================================="
echo "Verification Complete"
echo "========================================="
