import type { Capability, WagentProvider } from "../../provider-sdk/src/index.ts";
import { splitModelId } from "../../provider-sdk/src/index.ts";

export class ProviderRegistry {
  readonly #providers = new Map<string, WagentProvider>();

  register(provider: WagentProvider): this {
    if (this.#providers.has(provider.id)) throw new Error(`Provider already registered: ${provider.id}`);
    this.#providers.set(provider.id, provider);
    return this;
  }

  get(id: string): WagentProvider | undefined {
    return this.#providers.get(id);
  }

  list(): WagentProvider[] {
    return [...this.#providers.values()];
  }
}

export class Router {
  constructor(private readonly registry: ProviderRegistry, private readonly defaultProvider?: string) {}

  resolve(model: string, required: Capability[] = []): { provider: WagentProvider; modelId: string } {
    const parsed = splitModelId(model);
    if (parsed.providerId) {
      const provider = this.registry.get(parsed.providerId);
      if (!provider) throw new Error(`Unknown provider: ${parsed.providerId}`);
      this.assertCapabilities(provider, required);
      return { provider, modelId: parsed.modelId };
    }

    if (model !== "auto" && this.defaultProvider) {
      const provider = this.registry.get(this.defaultProvider);
      if (!provider) throw new Error(`Default provider is not registered: ${this.defaultProvider}`);
      this.assertCapabilities(provider, required);
      return { provider, modelId: model };
    }

    const provider = this.registry.list().find(item => required.every(capability => item.capabilities[capability]));
    if (!provider) throw new Error(`No provider satisfies required capabilities: ${required.join(", ") || "none"}`);
    return { provider, modelId: model === "auto" ? "default" : model };
  }

  private assertCapabilities(provider: WagentProvider, required: Capability[]): void {
    const missing = required.filter(capability => !provider.capabilities[capability]);
    if (missing.length) throw new Error(`${provider.id} does not support: ${missing.join(", ")}`);
  }
}
