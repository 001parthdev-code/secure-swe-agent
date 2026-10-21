# E2 implementation record — logical identity protocol foundation

Decision: approved logical target identity + version-checked atomic replacement under OS-enforced workspace concurrency.

Hypothesis: a trusted Enforcer-only writable workspace, with version-bound authorization and atomic staged commit, can reject target substitution and publish complete file versions.

Changed: added `modify_file_versioned` protocol variant with mandatory `expected_version`; policy explicitly denies it until isolation and version verification are implemented. Added the detailed threat model and transaction design. Legacy `modify_file` remains denied.

Verification: archive integrity only. No Rust toolchain verification performed here. Existing read and create paths intentionally unchanged.

Outstanding: implement and validate OS-enforced workspace isolation launcher, version token issuance, transactional commit/recovery, adversarial tests, and cross-platform CI. Do not connect untrusted agent write capability before acceptance.
