# Provider authoring

Implement `WagentProvider` from `packages/provider-sdk`. Pick a stable lowercase ID, report capabilities truthfully, keep native service types private, and yield normalized Wagent events.

A provider may use HTTP, SDKs, local processes or browser automation. Runtime must not care which transport it uses. Persistent service state should be returned through the `done.providerState` object and accepted again through `ProviderContext.providerState`.

For API providers, prefer real streaming. For Web providers that cannot reliably expose partial output, set `streaming: false` rather than simulating token streaming. Capability honesty lets the Router make correct choices.

Third-party provider packages can follow the same interface and be registered in an app bootstrap layer. This is the intended plugin seam; no provider-name switch should be added to runtime.
