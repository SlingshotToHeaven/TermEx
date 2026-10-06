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

echo "=== PHASE 3: Package Management Stress & Dependency Chains ==="

echo "Test 3.1: Package database query (dpkg -l)"
dpkg -l | grep -E "apt|dpkg|bash|coreutils"

echo "Test 3.2: Installing lightweight tool 'bc' via apt"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bc

echo -n "Test 3.3: Verify installed binary 'bc': "
CALC_RES=$(echo "123 + 456" | bc)
if [ "$CALC_RES" = "579" ]; then
    echo "OK ($CALC_RES)"
else
    echo "FAIL: got $CALC_RES" && exit 1
fi

echo "Test 3.4: Reinstall cycle (apt-get --reinstall install bc)"
DEBIAN_FRONTEND=noninteractive apt-get --reinstall install -y bc

echo "Test 3.5: Remove cycle (apt-get remove -y bc)"
DEBIAN_FRONTEND=noninteractive apt-get remove -y bc

echo -n "Test 3.6: Verify 'bc' removal: "
if [ ! -f "$PREFIX/bin/bc" ]; then
    echo "OK (removed from $PREFIX/bin)"
else
    echo "FAIL (bc still present in $PREFIX/bin)" && exit 1
fi

echo "Test 3.7: Purge cycle (dpkg -P bc)"
dpkg -P bc || true

echo "Phase 3: PASSED!"
