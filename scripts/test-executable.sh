#!/bin/bash

set -e

XSYNC="./dist/xsync"

echo "Testing xsync executable..."

# Test 1: Version check
echo "Test 1: Version check"
$XSYNC --version

# Test 2: Help command
echo "Test 2: Help command"
$XSYNC --help

# Test 3: Init command
echo "Test 3: Init command"
TEST_DIR=$(mktemp -d)
$XSYNC init --config-dir "$TEST_DIR"
if [ ! -f "$TEST_DIR/config.toml" ]; then
    echo "ERROR: config.toml not created"
    exit 1
fi

# Test 4: Config show
echo "Test 4: Config show"
$XSYNC config show --config-dir "$TEST_DIR"

# Test 5: Mirror list (should be empty)
echo "Test 5: Mirror list"
$XSYNC mirror list --config-dir "$TEST_DIR"

# Cleanup
rm -rf "$TEST_DIR"

echo "All tests passed!"
