# Using AI coding agents with Wagent

Wagent is structured so an agent can understand the repository without loading every file. Give the agent the task, then direct it to `AGENTS.md`. That file defines the reading order and invariants.

For provider work, the minimum useful context is the provider SDK plus that provider package. For routing/session work, use provider SDK + runtime. For prompt behavior, prefer a Skill rather than hard-coding instructions into a provider.

A good agent task states the owner layer, desired externally visible behavior, compatibility requirements, and validation command. Example: “Add an Anthropic provider implementing `WagentProvider`; do not change runtime provider-name logic; add normalization tests; run `bun run check`.”

Secrets and browser profile material are never valid context to commit. When debugging Web providers, redact cookies, tokens, account identifiers and local paths before sharing logs with an agent.
