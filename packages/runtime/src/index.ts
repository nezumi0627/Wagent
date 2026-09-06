import { randomUUID } from "node:crypto";
import type { GenerateRequest, WagentEvent } from "../../provider-sdk/src/index.ts";
import { Router, ProviderRegistry } from "./router.ts";
import { SessionStore } from "./session-store.ts";

export { ProviderRegistry, Router } from "./router.ts";
export { SessionStore, type RuntimeSession } from "./session-store.ts";

export class WagentRuntime {
  readonly router: Router;

  constructor(
    readonly providers: ProviderRegistry,
    readonly sessions = new SessionStore(),
    defaultProvider = process.env.WAGENT_DEFAULT_PROVIDER,
  ) {
    this.router = new Router(providers, defaultProvider);
  }

  async init(): Promise<this> {
    await this.sessions.load();
    return this;
  }

  async *generate(request: GenerateRequest): AsyncIterable<WagentEvent> {
    const sessionId = request.sessionId ?? randomUUID();
    const previous = this.sessions.get(sessionId);
    const required = [...(request.requiredCapabilities ?? [])];
    if (request.tools?.length && !required.includes("tools")) required.push("tools");

    const { provider, modelId } = this.router.resolve(request.model, required);
    let finalState = previous?.providerState;

    for await (const event of provider.generate({ ...request, model: modelId, sessionId }, { providerState: previous?.providerState })) {
      if (event.type === "done" && event.providerState) finalState = event.providerState;
      yield event;
    }

    const now = new Date().toISOString();
    await this.sessions.upsert({
      id: sessionId,
      providerId: provider.id,
      modelId,
      providerState: finalState,
      createdAt: previous?.createdAt ?? now,
      updatedAt: now,
    });
  }

  async text(request: GenerateRequest): Promise<{ text: string; reasoning: string; sessionId: string }> {
    const sessionId = request.sessionId ?? randomUUID();
    let text = "";
    let reasoning = "";
    for await (const event of this.generate({ ...request, sessionId })) {
      if (event.type === "text.delta") text += event.text;
      if (event.type === "reasoning.delta") reasoning += event.text;
      if (event.type === "error") throw new Error(event.error);
    }
    return { text, reasoning, sessionId };
  }
}
