import { Hono } from "hono";
import { z } from "zod";
import { WagentRuntime, ProviderRegistry } from "../../../packages/runtime/src/index.ts";
import { DeepSeekWebProvider } from "../../../packages/providers/deepseek-web/src/index.ts";
import { OpenAICompatibleProvider } from "../../../packages/providers/openai-compatible/src/index.ts";

const registry = new ProviderRegistry().register(new DeepSeekWebProvider()).register(new OpenAICompatibleProvider());
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
app.get("/v1/providers", c => c.json({ data: registry.list().map(provider => ({ id: provider.id, name: provider.name, capabilities: provider.capabilities })) }));
app.get("/v1/models", async c => {
  const data = (await Promise.all(registry.list().map(async provider => (await provider.listModels()).map(model => ({ id: `${provider.id}/${model.id}`, object: "model", owned_by: provider.id }))))).flat();
  return c.json({ object: "list", data });
});

app.post("/v1/generate", async c => {
  const parsed = requestSchema.safeParse(await c.req.json());
  if (!parsed.success) return c.json({ error: parsed.error.flatten() }, 400);
  const result = await runtime.text(parsed.data);
  return c.json(result);
});

app.post("/v1/chat/completions", async c => {
  const body = await c.req.json();
  const parsed = requestSchema.safeParse({ ...body, sessionId: body.session_id });
  if (!parsed.success) return c.json({ error: { message: parsed.error.message, type: "invalid_request_error" } }, 400);
  const result = await runtime.text(parsed.data);
  return c.json({
    id: `chatcmpl-${crypto.randomUUID()}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: parsed.data.model,
    choices: [{ index: 0, message: { role: "assistant", content: result.text }, finish_reason: "stop" }],
    wagent: { session_id: result.sessionId, reasoning: result.reasoning || undefined },
  });
});

const hostname = process.env.WAGENT_HOST ?? "127.0.0.1";
const port = Number(process.env.WAGENT_PORT ?? 8765);
console.log(`Wagent listening on http://${hostname}:${port}`);
Bun.serve({ hostname, port, fetch: app.fetch });
