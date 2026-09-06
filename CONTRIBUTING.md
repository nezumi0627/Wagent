# Contributing to Wagent

Thank you for your interest in contributing to Wagent! 🎉

Wagent welcomes provider adapters, Skills, runtime improvements and compatibility fixes.

Read `AGENTS.md` and `docs/architecture.md` first. Install with `bun install`, then run `bun run check` before opening a PR.

Provider PRs should declare capabilities accurately, avoid leaking credentials, normalize all output into Wagent events, and include tests for request/event normalization where practical. UI automation changes should explain the manual verification performed because third-party web interfaces are not stable CI targets.

Keep commits focused. Provider-specific selectors, authentication and workarounds belong in that provider package; runtime changes should remain provider-neutral.
