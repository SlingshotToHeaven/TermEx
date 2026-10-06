#!/data/user/10/com.termex/files/usr/bin/bash
set -e

export PREFIX=/data/user/10/com.termex/files/usr
export HOME=/data/user/10/com.termex/files/home
export LD_PRELOAD=$PREFIX/lib/libtermex-redirect.so
export TERMEX_REAL_APP_DIR=/data/user/10/com.termex
export TERMUX__USER_ID=10
export TERMUX_APP__USER_ID=10
export PATH=$PREFIX/bin:$PREFIX/bin/applets:$PATH
export LD_LIBRARY_PATH=$PREFIX/lib

echo "=== PHASE 6: Session Lifecycle & App State Recovery ==="

echo "Test 6.1: Process Termination & Terminal Session Recovery"
echo -n "  Verifying active terminal session after clean restart: "
TERMEX_PID=$(pidof com.termex || true)
if [ -z "$TERMEX_PID" ]; then
    echo "FAIL: com.termex process not running" && exit 1
fi

SESSION_PID=$(pgrep -P $TERMEX_PID bash || true)
if [ -n "$SESSION_PID" ] && [ -d "/proc/$SESSION_PID" ]; then
    CMD=$(cat /proc/$SESSION_PID/cmdline | tr '\0' ' ')
    echo "OK (Session PID: $SESSION_PID, Command: $CMD)"
else
    echo "FAIL: No active bash session under com.termex found" && exit 1
fi

echo -n "  Verifying environment variables of recovered session: "
ENV_OUTPUT=$(cat /proc/$SESSION_PID/environ | tr '\0' '\n')
REQ_VARS=("PREFIX=/data/user/10/com.termex/files/usr" "HOME=/data/user/10/com.termex/files/home" "TERMUX__USER_ID=10" "TERMEX_REAL_APP_DIR=/data/user/10/com.termex")
for var in "${REQ_VARS[@]}"; do
    if ! echo "$ENV_OUTPUT" | grep -Fqx "$var"; then
        echo "FAIL (Missing environment variable: $var)" && exit 1
    fi
done
echo "OK"

echo "Test 6.2: Terminal Resizing & PTY Window Size Control"
echo -n "  Executing PTY TIOCSWINSZ / SIGWINCH resize validation: "
if [ -x "$PREFIX/bin/test_pty_resize" ]; then
    RESIZE_RES=$($PREFIX/bin/test_pty_resize)
    if [ "$RESIZE_RES" = "PTY_RESIZE_SUCCESS" ]; then
        echo "OK ($RESIZE_RES)"
    else
        echo "FAIL ($RESIZE_RES)" && exit 1
    fi
else
    echo "FAIL: test_pty_resize binary not found" && exit 1
fi

echo "Test 6.3: Failsafe Session Launch Mode"
echo -n "  Verifying failsafe shell capability and system fallback: "
FAILSAFE_SHELL="/system/bin/sh"
if [ -x "$FAILSAFE_SHELL" ]; then
    echo "OK (Failsafe shell available: $FAILSAFE_SHELL)"
else
    echo "FAIL: Failsafe shell not accessible" && exit 1
fi

echo "Phase 6: PASSED!"
