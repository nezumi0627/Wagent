import { randomUUID } from "node:crypto";
import type { GenerateRequest, WagentEvent } from "../../provider-sdk/src/index.ts";
import { applySkills, loadSkills, selectSkills, type Skill } from "../../skills/src/index.ts";
import { Router, ProviderRegistry } from "./router.ts";
import { SessionStore } from "./session-store.ts";

export { ProviderRegistry, Router } from "./router.ts";
export { SessionStore, type RuntimeSession } from "./session-store.ts";

export class WagentRuntime {
  readonly router: Router;
  #skills: Skill[] = [];

  constructor(
    readonly providers: ProviderRegistry,
    readonly sessions = new SessionStore(),
    defaultProvider = process.env.WAGENT_DEFAULT_PROVIDER,
    readonly skillsRoot = process.env.WAGENT_SKILLS_DIR ?? "skills",
  ) {
    this.router = new Router(providers, defaultProvider);
  }

  async init(): Promise<this> {
    await Promise.all([this.sessions.load(), loadSkills(this.skillsRoot).then(skills => { this.#skills = skills; })]);
    return this;
  }

  listSkills(): Skill[] { return [...this.#skills]; }

  async *generate(request: GenerateRequest): AsyncIterable<WagentEvent> {
    const sessionId = request.sessionId ?? randomUUID();
    const previous = this.sessions.get(sessionId);
    const required = [...(request.requiredCapabilities ?? [])];
    if (request.tools?.length && !required.includes("tools")) required.push("tools");

    const explicitSkills = Array.isArray(request.metadata?.skills)
      ? request.metadata.skills.filter((value): value is string => typeof value === "string")
      : [];
    const prompt = [...request.messages].reverse().find(message => message.role === "user")?.content ?? "";
    const selected = request.metadata?.skills === false ? [] : selectSkills(prompt, this.#skills, explicitSkills);
    const messages = applySkills(request.messages, selected);

    const { provider, modelId } = this.router.resolve(request.model, required);
    let finalState = previous?.providerState;

    for await (const event of provider.generate({ ...request, messages, model: modelId, sessionId }, { providerState: previous?.providerState })) {
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
