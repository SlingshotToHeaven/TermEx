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

echo "=== PHASE 2: Native Interposition & Filesystem Edge Cases ==="

# 2.1 Absolute path redirection: /data/data/com.termux
echo -n "Test 2.1.1: Read file via /data/data/com.termux/files/usr/bin/sh: "
if [ -x "/data/data/com.termux/files/usr/bin/sh" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

echo -n "Test 2.1.2: Read file via /data/user/0/com.termux/files/usr/bin/sh: "
if [ -x "/data/user/0/com.termux/files/usr/bin/sh" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

echo -n "Test 2.1.3: Read file via /data/user/0/com.termex/files/usr/bin/sh: "
if [ -x "/data/user/0/com.termex/files/usr/bin/sh" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

# 2.2 Relative & dot variations
echo -n "Test 2.2.1: Relative path with dot prefix: "
cd /data/data/com.termux/files
if [ -d "./usr/bin" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

echo -n "Test 2.2.2: Redundant slashes (/data//data///com.termux): "
if [ -x "/data//data///com.termux/files/usr/bin/sh" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

# 2.3 Creation, Stat, Read, Rename, Unlink via redirected path
TEST_DIR="/data/data/com.termux/files/home/test_phase2_$$"
echo -n "Test 2.3.1: mkdir via redirected path ($TEST_DIR): "
mkdir -p "$TEST_DIR"
if [ -d "/data/user/10/com.termex/files/home/test_phase2_$$" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

echo -n "Test 2.3.2: create and write file via redirected path: "
echo "Resilience test payload" > "$TEST_DIR/sample.txt"
CONTENT=$(cat "/data/user/10/com.termex/files/home/test_phase2_$$/sample.txt")
if [ "$CONTENT" = "Resilience test payload" ]; then
    echo "OK"
else
    echo "FAIL: got $CONTENT" && exit 1
fi

echo -n "Test 2.3.3: rename via redirected path: "
mv "$TEST_DIR/sample.txt" "$TEST_DIR/renamed.txt"
if [ -f "$TEST_DIR/renamed.txt" ] && [ ! -f "$TEST_DIR/sample.txt" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

echo -n "Test 2.3.4: opendir and ls on redirected directory: "
LS_OUTPUT=$(ls "$TEST_DIR")
if [ "$LS_OUTPUT" = "renamed.txt" ]; then
    echo "OK"
else
    echo "FAIL: got $LS_OUTPUT" && exit 1
fi

echo -n "Test 2.3.5: rm and rmdir cleanup: "
rm -rf "$TEST_DIR"
if [ ! -e "$TEST_DIR" ] && [ ! -e "/data/user/10/com.termex/files/home/test_phase2_$$" ]; then
    echo "OK"
else
    echo "FAIL" && exit 1
fi

# 2.4 Inaccessible parent path resilience
echo -n "Test 2.4: Stat /data/data parent directly (should fail gracefully with EACCES or ENOENT, not crash): "
if ls /data/data >/dev/null 2>&1; then
    echo "OK (unexpectedly readable)"
else
    echo "OK (gracefully denied/non-fatal)"
fi

echo "Phase 2: PASSED!"
