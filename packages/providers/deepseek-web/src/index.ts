import { capabilities, type GenerateRequest, type ProviderContext, type ProviderModel, type WagentEvent, type WagentProvider } from "../../../provider-sdk/src/index.ts";
import { askDeepSeekWeb } from "./browser.ts";

export class DeepSeekWebProvider implements WagentProvider {
  readonly id = "deepseek-web";
  readonly name = "DeepSeek Web";
  readonly capabilities = capabilities({ streaming: false, reasoning: true, vision: true, files: true, webSearch: true, conversations: true, tools: false });

  async listModels(): Promise<ProviderModel[]> {
    return [{ id: "default", name: "DeepSeek Web" }];
  }

  async *generate(request: GenerateRequest, context: ProviderContext): AsyncIterable<WagentEvent> {
    const prompt = request.messages.map(message => `${message.role.toUpperCase()}: ${message.content}`).join("\n\n");
    const metadata = request.metadata ?? {};
    try {
      const result = await askDeepSeekWeb(prompt, {
        conversationUrl: typeof context.providerState?.conversationUrl === "string" ? context.providerState.conversationUrl : undefined,
        newChat: metadata.newChat === true,
        deepThink: typeof metadata.deepThink === "boolean" ? metadata.deepThink : undefined,
        search: typeof metadata.webSearch === "boolean" ? metadata.webSearch : undefined,
        attachments: Array.isArray(metadata.attachments) ? metadata.attachments.filter((value): value is string => typeof value === "string") : undefined,
      });
      if (result.thinking) yield { type: "reasoning.delta", text: result.thinking };
      yield { type: "text.delta", text: result.text };
      yield { type: "done", providerState: { conversationUrl: result.conversationUrl } };
    } catch (error) {
      yield { type: "error", error: error instanceof Error ? error.message : String(error), retryable: true };
    }
  }
}
