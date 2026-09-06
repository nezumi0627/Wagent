import { WagentRuntime, ProviderRegistry } from "../packages/runtime/src/index.ts";
import { OpenAICompatibleProvider } from "../packages/providers/openai-compatible/src/index.ts";

const runtime = await new WagentRuntime(new ProviderRegistry().register(new OpenAICompatibleProvider())).init();
const result = await runtime.text({ model: "openai-compatible/gpt-5", messages: [{ role: "user", content: "Hello from Wagent" }] });
console.log(result.text);
