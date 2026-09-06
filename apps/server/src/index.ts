import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { z } from "zod";
import { WagentRuntime, ProviderRegistry } from "../../../packages/runtime/src/index.ts";
import { ChatGPTWebProvider } from "../../../packages/providers/chatgpt-web/src/index.ts";
import { DeepSeekWebProvider } from "../../../packages/providers/deepseek-web/src/index.ts";
import { OpenAICompatibleProvider } from "../../../packages/providers/openai-compatible/src/index.ts";

const registry = new ProviderRegistry()
  .register(new ChatGPTWebProvider())
  .register(new DeepSeekWebProvider())
  .register(new OpenAICompatibleProvider());
const runtime = await new WagentRuntime(registry).init();
const app = new Hono();

const requestSchema = z.object({
  model: z.string().default("auto"),
  messages: z.array(z.object({ role: z.enum(["system", "user", "assistant", "tool"]), content: z.string(), name: z.string().optional() })),
  sessionId: z.string().optional(),
  stream: z.boolean().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

app.get("/health", c => c.json({ ok: true, runtime: "wagent", version: "0.2.0" }));
app.get("/v1/status", c => c.json({ ok: true, providers: registry.list().map(provider => provider.id), sessions: runtime.sessions.list().length }));
app.get("/v1/providers", c => c.json({ data: registry.list().map(provider => ({ id: provider.id, name: provider.name, capabilities: provider.capabilities })) }));
app.get("/v1/skills", c => c.json({ data: runtime.listSkills().map(skill => ({ name: skill.name, description: skill.description, tags: skill.tags })) }));
app.get("/v1/models", async c => {
  const data = (await Promise.all(registry.list().map(async provider => {
    try { return (await provider.listModels()).map(model => ({ id: `${provider.id}/${model.id}`, object: "model", owned_by: provider.id })); }
    catch { return []; }
  }))).flat();
  return c.json({ object: "list", data });
});

app.post("/v1/generate", async c => {
  const parsed = requestSchema.safeParse(await c.req.json());
  if (!parsed.success) return c.json({ error: parsed.error.flatten() }, 400);
  if (parsed.data.stream) return streamSSE(c, async stream => { for await (const event of runtime.generate(parsed.data)) await stream.writeSSE({ event: event.type, data: JSON.stringify(event) }); });
  return c.json(await runtime.text(parsed.data));
});

// Compatibility with the original Wagent /v1/chat shape.
app.post("/v1/chat", async c => {
  const body = await c.req.json<Record<string, unknown>>();
  if (typeof body.message !== "string" || !body.message.trim()) return c.json({ error: "message is required" }, 400);
  const result = await runtime.text({
    model: typeof body.model === "string" ? body.model : "chatgpt-web/default",
    sessionId: typeof body.session_id === "string" ? body.session_id : undefined,
    messages: [{ role: "user", content: body.message }],
    metadata: {
      attachments: Array.isArray(body.files) ? body.files : undefined,
      webSearch: body.web_search === true,
      newChat: body.new_conversation === true,
      profile: typeof body.profile === "string" ? body.profile : undefined,
    },
  });
  return c.json({ message: result.text, session_id: result.sessionId, reasoning: result.reasoning || undefined });
});

app.post("/v1/chat/completions", async c => {
  const body = await c.req.json<Record<string, unknown>>();
  const parsed = requestSchema.safeParse({ ...body, sessionId: body.session_id });
  if (!parsed.success) return c.json({ error: { message: parsed.error.message, type: "invalid_request_error" } }, 400);

  if (parsed.data.stream) {
    const id = `chatcmpl-${crypto.randomUUID()}`;
    return streamSSE(c, async stream => {
      for await (const event of runtime.generate(parsed.data)) {
        if (event.type !== "text.delta" && event.type !== "reasoning.delta") continue;
        const delta = event.type === "text.delta" ? { content: event.text } : { reasoning_content: event.text };
        await stream.writeSSE({ data: JSON.stringify({ id, object: "chat.completion.chunk", created: Math.floor(Date.now() / 1000), model: parsed.data.model, choices: [{ index: 0, delta, finish_reason: null }] }) });
      }
      await stream.writeSSE({ data: "[DONE]" });
    });
  }

  const result = await runtime.text(parsed.data);
  return c.json({ id: `chatcmpl-${crypto.randomUUID()}`, object: "chat.completion", created: Math.floor(Date.now() / 1000), model: parsed.data.model, choices: [{ index: 0, message: { role: "assistant", content: result.text }, finish_reason: "stop" }], wagent: { session_id: result.sessionId, reasoning: result.reasoning || undefined } });
});

const hostname = process.env.WAGENT_HOST ?? "127.0.0.1";
const port = Number(process.env.WAGENT_PORT ?? 8765);
console.log(`Wagent listening on http://${hostname}:${port}`);
Bun.serve({ hostname, port, fetch: app.fetch });
