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

echo "=== PHASE 5: Storage Access & Media Concurrency ==="

echo "Test 5.1: Verify ~/storage directory symlinks"
for dir in shared downloads dcim documents pictures movies music; do
    echo -n "  Verifying link ~/storage/$dir: "
    if [ -L "$HOME/storage/$dir" ]; then
        TARGET=$(readlink "$HOME/storage/$dir")
        echo "OK ($TARGET)"
    else
        echo "FAIL (missing link)" && exit 1
    fi
done

echo "Test 5.2: Concurrent Read/Write Integrity on Shared Storage"
TEST_FILE="$HOME/storage/shared/resilience_phase5_$$.dat"
echo -n "  Writing 2MB test payload to $TEST_FILE: "
dd if=/dev/urandom of="$TEST_FILE" bs=1M count=2 status=none
ORIG_SHA=$(sha256sum "$TEST_FILE" | awk '{print $1}')
echo "OK (SHA: $ORIG_SHA)"

echo -n "  Concurrent readers verifying payload: "
(sha256sum "$TEST_FILE" | awk '{print $1}') > "$PREFIX/tmp/read1.sha" &
PID1=$!
(sha256sum "$TEST_FILE" | awk '{print $1}') > "$PREFIX/tmp/read2.sha" &
PID2=$!
wait $PID1 $PID2

SHA1=$(cat "$PREFIX/tmp/read1.sha")
SHA2=$(cat "$PREFIX/tmp/read2.sha")
rm -f "$PREFIX/tmp/read1.sha" "$PREFIX/tmp/read2.sha" "$TEST_FILE"

if [ "$SHA1" = "$ORIG_SHA" ] && [ "$SHA2" = "$ORIG_SHA" ]; then
    echo "OK (both readers verified match)"
else
    echo "FAIL: hash mismatch (R1: $SHA1, R2: $SHA2)" && exit 1
fi

echo -n "Test 5.3: Run termux-setup-storage idempotency check: "
$PREFIX/bin/termux-setup-storage
if [ -d "$HOME/storage" ] && [ -L "$HOME/storage/shared" ]; then
    echo "OK"
else
    echo "FAIL (storage setup broken)" && exit 1
fi

echo "Phase 5: PASSED!"
