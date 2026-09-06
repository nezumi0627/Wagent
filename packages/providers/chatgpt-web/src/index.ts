import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { chromium, type Page } from "playwright-core";
import { capabilities, type GenerateRequest, type ProviderContext, type ProviderModel, type WagentEvent, type WagentProvider } from "../../../provider-sdk/src/index.ts";

const CHATGPT_URL = "https://chatgpt.com/";

function browserCandidates(): string[] {
  if (process.platform === "win32") return ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"];
  if (process.platform === "darwin") return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"];
  return ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/microsoft-edge"];
}

function findBrowser(): string | undefined {
  const override = process.env.WAGENT_BROWSER;
  if (override && existsSync(override)) return override;
  const known = browserCandidates().find(existsSync);
  if (known) return known;
  const command = process.platform === "win32" ? "where.exe" : "which";
  const names = process.platform === "win32" ? ["chrome.exe", "msedge.exe"] : ["google-chrome", "chromium", "microsoft-edge"];
  for (const name of names) {
    const result = spawnSync(command, [name], { encoding: "utf8", windowsHide: true });
    const path = result.status === 0 ? String(result.stdout).split(/\r?\n/).find(Boolean)?.trim() : undefined;
    if (path && existsSync(path)) return path;
  }
}

async function assistantMessages(page: Page): Promise<string[]> {
  return page.locator('[data-message-author-role="assistant"]').allInnerTexts().then(items => items.map(item => item.trim()).filter(Boolean));
}

async function waitStableAssistant(page: Page, before: number, timeoutMs: number): Promise<string> {
  const started = Date.now();
  let previous = "";
  let stableAt = 0;
  while (Date.now() - started < timeoutMs) {
    const items = await assistantMessages(page);
    const current = items.at(-1) ?? "";
    if (items.length > before && current) {
      if (current === previous) {
        if (!stableAt) stableAt = Date.now();
        if (Date.now() - stableAt >= 1200) return current;
      } else {
        previous = current;
        stableAt = 0;
      }
    }
    await page.waitForTimeout(350);
  }
  throw new Error("Timed out waiting for ChatGPT Web response.");
}

async function toggleSearch(page: Page): Promise<void> {
  const controls = [page.getByRole("button", { name: /search|検索/i }), page.getByText(/search|検索/i, { exact: true })];
  for (const control of controls) {
    const item = control.filter({ visible: true }).last();
    if (await item.isVisible().catch(() => false)) { await item.click(); return; }
  }
  throw new Error("ChatGPT Web search control was not found.");
}

export class ChatGPTWebProvider implements WagentProvider {
  readonly id = "chatgpt-web";
  readonly name = "ChatGPT Web";
  readonly capabilities = capabilities({ streaming: false, tools: false, reasoning: false, vision: true, files: true, webSearch: true, conversations: true });

  async listModels(): Promise<ProviderModel[]> { return [{ id: "default", name: "ChatGPT Web current model" }]; }

  async *generate(request: GenerateRequest, context: ProviderContext): AsyncIterable<WagentEvent> {
    const executablePath = findBrowser();
    if (!executablePath) { yield { type: "error", error: "Chrome/Edge not found; set WAGENT_BROWSER." }; return; }

    const profileName = typeof request.metadata?.profile === "string" ? request.metadata.profile.replace(/[^a-zA-Z0-9_-]/g, "_") : "default";
    const home = process.env.WAGENT_HOME ?? join(homedir(), ".wagent");
    const userDataDir = join(home, "providers", "chatgpt-web", profileName);
    mkdirSync(userDataDir, { recursive: true });

    const browser = await chromium.launchPersistentContext(userDataDir, {
      executablePath,
      headless: process.env.WAGENT_HEADLESS === "1",
      viewport: null,
    });

    try {
      const page = browser.pages()[0] ?? await browser.newPage();
      const stateUrl = typeof context.providerState?.conversationUrl === "string" ? context.providerState.conversationUrl : undefined;
      const target = request.metadata?.newChat === true ? CHATGPT_URL : stateUrl ?? CHATGPT_URL;
      if (page.url() !== target) await page.goto(target, { waitUntil: "domcontentloaded", timeout: 60_000 });

      const composer = page.locator('textarea#prompt-textarea, #prompt-textarea[contenteditable="true"], div[contenteditable="true"][data-virtualkeyboard="true"]').filter({ visible: true }).last();
      await composer.waitFor({ state: "visible", timeout: 30_000 }).catch(() => { throw new Error(`ChatGPT composer not found at ${page.url()}; sign in to the opened browser and retry.`); });

      if (request.metadata?.webSearch === true) await toggleSearch(page);
      const attachments = Array.isArray(request.metadata?.attachments) ? request.metadata.attachments.filter((value): value is string => typeof value === "string") : [];
      if (attachments.length) {
        const files = attachments.map(file => resolve(file));
        for (const file of files) if (!existsSync(file)) throw new Error(`Attachment not found: ${file}`);
        const input = page.locator('input[type="file"]').last();
        if (!await input.count()) throw new Error("ChatGPT file input was not found.");
        await input.setInputFiles(files);
        await page.waitForTimeout(700);
      }

      const prompt = request.messages.map(message => `${message.role.toUpperCase()}: ${message.content}`).join("\n\n");
      const before = (await assistantMessages(page)).length;
      const tag = await composer.evaluate(element => element.tagName.toLowerCase());
      if (tag === "textarea" || tag === "input") await composer.fill(prompt); else { await composer.click(); await page.keyboard.insertText(prompt); }
      const send = page.locator('button[data-testid="send-button"], button[aria-label*="send" i], button[aria-label*="送信" i]').filter({ visible: true }).last();
      if (await send.isVisible().catch(() => false)) await send.click(); else await composer.press("Enter");

      const text = await waitStableAssistant(page, before, Number(request.metadata?.timeoutMs ?? 180_000));
      yield { type: "text.delta", text };
      yield { type: "done", providerState: { conversationUrl: page.url(), profile: profileName } };
    } catch (error) {
      yield { type: "error", error: error instanceof Error ? error.message : String(error), retryable: true };
    } finally {
      await browser.close().catch(() => undefined);
    }
  }
}
