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

echo "=== PHASE 4: Inter-Process Communication, Signals & Background Execution ==="

# 4.1 Activity & Service broadcasts via termux-* scripts
echo -n "Test 4.1.1: termux-wake-lock broadcast dispatch: "
$PREFIX/bin/termux-wake-lock
echo "OK"

echo -n "Test 4.1.2: termux-wake-unlock broadcast dispatch: "
$PREFIX/bin/termux-wake-unlock
echo "OK"

echo -n "Test 4.1.3: termux-reload-settings broadcast dispatch: "
$PREFIX/bin/termux-reload-settings
echo "OK"

# 4.2 Signal dispatch and background jobs
echo -n "Test 4.2.1: Background process spawning & SIGTERM handling: "
sleep 100 &
SLEEP_PID=$!
kill -15 "$SLEEP_PID"
wait "$SLEEP_PID" 2>/dev/null || true
if ! kill -0 "$SLEEP_PID" 2>/dev/null; then
    echo "OK (terminated cleanly)"
else
    echo "FAIL: process $SLEEP_PID still alive" && exit 1
fi

echo -n "Test 4.2.2: SIGINT handling: "
sleep 100 &
SLEEP_PID=$!
kill -2 "$SLEEP_PID"
wait "$SLEEP_PID" 2>/dev/null || true
if ! kill -0 "$SLEEP_PID" 2>/dev/null; then
    echo "OK (interrupted cleanly)"
else
    echo "FAIL: process $SLEEP_PID still alive" && exit 1
fi

# 4.3 Named pipes (FIFO) & stream pipelines
FIFO_PATH="$PREFIX/tmp/test_fifo_$$"
echo -n "Test 4.3.1: FIFO named pipe creation and communication: "
rm -f "$FIFO_PATH"
mkfifo "$FIFO_PATH"
(echo "FIFO_RESILIENCE_PAYLOAD" > "$FIFO_PATH") &
READ_VAL=$(cat "$FIFO_PATH")
rm -f "$FIFO_PATH"
if [ "$READ_VAL" = "FIFO_RESILIENCE_PAYLOAD" ]; then
    echo "OK"
else
    echo "FAIL: got $READ_VAL" && exit 1
fi

echo -n "Test 4.3.2: Heavy pipeline streaming (10MB urandom sha256sum): "
HASH_1=$(head -c 10485760 /dev/urandom | sha256sum | awk '{print $1}')
if [ ${#HASH_1} -eq 64 ]; then
    echo "OK ($HASH_1)"
else
    echo "FAIL (invalid hash length)" && exit 1
fi

echo "Phase 4: PASSED!"
