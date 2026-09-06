import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
import { WagentRuntime, ProviderRegistry } from "../../../packages/runtime/src/index.ts";
import { DeepSeekWebProvider } from "../../../packages/providers/deepseek-web/src/index.ts";
import { OpenAICompatibleProvider } from "../../../packages/providers/openai-compatible/src/index.ts";

const registry = new ProviderRegistry().register(new DeepSeekWebProvider()).register(new OpenAICompatibleProvider());
const runtime = await new WagentRuntime(registry).init();
const rl = createInterface({ input: stdin, output: stdout });
let model = process.env.WAGENT_MODEL ?? "auto";
let sessionId: string | undefined;
console.log(`Wagent CLI — model=${model}. Commands: /model <id>, /new, /providers, /quit`);

while (true) {
  const line = (await rl.question("\nYou> ").catch(() => "")).trim();
  if (!line || line === "/quit") break;
  if (line.startsWith("/model ")) { model = line.slice(7).trim(); console.log(`model=${model}`); continue; }
  if (line === "/new") { sessionId = undefined; console.log("new session"); continue; }
  if (line === "/providers") { registry.list().forEach(provider => console.log(`${provider.id} — ${provider.name}`)); continue; }
  try {
    const result = await runtime.text({ model, sessionId, messages: [{ role: "user", content: line }] });
    sessionId = result.sessionId;
    if (result.reasoning) console.log(`\n[reasoning]\n${result.reasoning}\n[/reasoning]`);
    console.log(`\n${result.text}`);
  } catch (error) { console.error(error instanceof Error ? error.message : String(error)); }
}
rl.close();
