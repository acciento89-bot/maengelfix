#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
qa_tmp=$(mktemp -d "${TMPDIR:-/tmp}/maengelfix-provider-qa.XXXXXX")
trap 'rm -rf "$qa_tmp"' EXIT
xcrun swiftc -emit-module -emit-library -module-name StoreKit Tests/provider-isolation/StoreKitStub.swift -o "$qa_tmp/libStoreKit.dylib" -emit-module-path "$qa_tmp/StoreKit.swiftmodule"
xcrun swiftc -DDEBUG -I "$qa_tmp" -L "$qa_tmp" -lStoreKit -parse-as-library Sources/Core/StoreKitManager.swift Tests/provider-isolation/Smoke.swift -o "$qa_tmp/debug"
DYLD_LIBRARY_PATH="$qa_tmp" "$qa_tmp/debug" --maengelfixProviderDisabledQA
EXPECT_PROVIDER_CALLS=1 DYLD_LIBRARY_PATH="$qa_tmp" "$qa_tmp/debug"
xcrun swiftc -I "$qa_tmp" -L "$qa_tmp" -lStoreKit -parse-as-library Sources/Core/StoreKitManager.swift Tests/provider-isolation/Smoke.swift -o "$qa_tmp/release"
EXPECT_PROVIDER_CALLS=1 DYLD_LIBRARY_PATH="$qa_tmp" "$qa_tmp/release" --maengelfixProviderDisabledQA
