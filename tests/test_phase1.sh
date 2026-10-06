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

echo "=== PHASE 1: Shell Environment & Multi-User Process Hierarchy ==="
echo "1.1 Canonical Variables:"
echo "  PREFIX: $PREFIX"
echo "  HOME: $HOME"
echo "  TERMUX__USER_ID: $TERMUX__USER_ID"
echo "  TERMEX_REAL_APP_DIR: $TERMEX_REAL_APP_DIR"
echo "  LD_PRELOAD: $LD_PRELOAD"

echo "1.2 Spawning subshells:"
sh -c 'echo "  [sh] PID: $$, UID: $(id -u), LD_PRELOAD: $LD_PRELOAD"'
zsh -c 'echo "  [zsh] PID: $$, UID: $(id -u), LD_PRELOAD: $LD_PRELOAD"'

echo "1.3 Deep nested chaining (bash -> sh -> zsh):"
bash -c 'sh -c "zsh -c \"echo \\\"  [nested] Success across 3 levels!\\\"\""'

echo "Phase 1: PASSED!"
