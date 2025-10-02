#!/bin/bash

echo "🔧 Fixing final build issues..."

# Fix CLI errors
echo "Fixing CLI build errors..."
sed -i '43s/let stealth_manager = StealthManager::new(config.stealth.clone());/let stealth_manager = StealthManager::new(config.stealth.clone())?;    pb.inc(1);/' crates/cli/src/commands/start.rs
sed -i '80s/stealth_manager.deactivate().await?;/stealth_manager.deactivate().await?;/' crates/cli/src/commands/start.rs

echo "✅ Build issues fixed!"

# Test build
cargo build --workspace --release
if [ $? -eq 0 ]; then
    echo "🎉 Build successful!"
else
    echo "❌ Build still has issues"
fi