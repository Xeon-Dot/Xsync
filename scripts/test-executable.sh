#!/bin/bash

set -e

xync="./dist/xync"

echo "Testing xync executable..."

# Test 1: Version check
echo "Test 1: Version check"
$xync --version

# Test 2: Help command
echo "Test 2: Help command"
$xync --help

# Test 3: Init command
echo "Test 3: Init command"
TEST_DIR=$(mktemp -d)
$xync init --config-dir "$TEST_DIR"
if [ ! -f "$TEST_DIR/config.toml" ]; then
    echo "ERROR: config.toml not created"
    exit 1
fi

# Test 4: Config show
echo "Test 4: Config show"
$xync config show --config-dir "$TEST_DIR"

# Test 5: Mirror list (should be empty)
echo "Test 5: Mirror list"
$xync mirror list --config-dir "$TEST_DIR"

# Cleanup
rm -rf "$TEST_DIR"

echo "All tests passed!"
