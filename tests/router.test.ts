import { describe, expect, test } from "bun:test";
import { ProviderRegistry, Router } from "../packages/runtime/src/router.ts";
import { capabilities, type WagentProvider } from "../packages/provider-sdk/src/index.ts";

const provider = (id: string, reasoning = false): WagentProvider => ({
  id,
  name: id,
  capabilities: capabilities({ reasoning }),
  async listModels() { return [{ id: "default" }]; },
  async *generate() { yield { type: "done" as const }; },
});

describe("Router", () => {
  test("resolves explicit provider/model ids", () => {
    const registry = new ProviderRegistry().register(provider("alpha"));
    const result = new Router(registry).resolve("alpha/model-x");
    expect(result.provider.id).toBe("alpha");
    expect(result.modelId).toBe("model-x");
  });

  test("auto routing respects capabilities", () => {
    const registry = new ProviderRegistry().register(provider("basic")).register(provider("thinker", true));
    expect(new Router(registry).resolve("auto", ["reasoning"]).provider.id).toBe("thinker");
  });
});
