import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { chromium, type Page } from "playwright-core";

const URL = "https://chat.deepseek.com/";

export interface DeepSeekWebOptions {
  conversationUrl?: string;
  newChat?: boolean;
  mode?: "instant" | "expert" | "imageRecognition";
  deepThink?: boolean;
  search?: boolean;
  attachments?: string[];
  timeoutMs?: number;
}

export interface DeepSeekReply { text: string; thinking?: string | null; conversationUrl: string; }

const home = () => process.env.WAGENT_HOME ?? join(homedir(), ".wagent");

function candidates(): string[] {
  if (process.platform === "win32") return ["C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"];
  if (process.platform === "darwin") return ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"];
  return ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/microsoft-edge"];
}

function findBrowser(): string | undefined {
  const override = process.env.WAGENT_BROWSER;
  if (override && existsSync(override)) return override;
  const known = candidates().find(existsSync);
  if (known) return known;
  const command = process.platform === "win32" ? "where.exe" : "which";
  for (const name of process.platform === "win32" ? ["chrome.exe", "msedge.exe"] : ["google-chrome", "chromium", "microsoft-edge"]) {
    const result = spawnSync(command, [name], { encoding: "utf8", windowsHide: true });
    const path = result.status === 0 ? String(result.stdout).split(/\r?\n/).find(Boolean)?.trim() : undefined;
    if (path && existsSync(path)) return path;
  }
}

const composer = (page: Page) => page.locator('textarea#chat-input, textarea[placeholder], [contenteditable="true"][role="textbox"], div[contenteditable="true"]').filter({ visible: true }).last();

async function waitComposer(page: Page, timeoutMs = 20_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const input = composer(page);
    if (await input.isVisible().catch(() => false)) return input;
    await page.waitForTimeout(350);
  }
  throw new Error(`DeepSeek composer not found at ${page.url()}; sign in to the opened browser profile and retry.`);
}

async function clickControl(page: Page, names: string[], wanted: boolean | undefined): Promise<boolean> {
  if (wanted === undefined) return false;
  for (const name of names) {
    const pattern = new RegExp(name, "i");
    for (const candidate of [page.getByRole("button", { name: pattern }), page.getByText(pattern, { exact: false })]) {
      const item = candidate.filter({ visible: true }).last();
      if (!await item.isVisible().catch(() => false)) continue;
      const pressed = await item.getAttribute("aria-pressed").catch(() => null);
      const selected = pressed === "true";
      if (pressed === null ? wanted : wanted !== selected) await item.click();
      return true;
    }
  }
  return false;
}

async function replies(page: Page): Promise<Array<{ text: string; thinking?: string | null }>> {
  return page.evaluate(() => {
    const text = (node: Element | null | undefined) => ((node as HTMLElement | null)?.innerText || node?.textContent || "").trim();
    const nodes = [...document.querySelectorAll(".ds-assistant-message-main-content")];
    return nodes.map(node => ({ text: text(node), thinking: text(node.closest(".ds-message")?.querySelector(".ds-think-content")) || null })).filter(item => item.text);
  });
}

async function launch(): Promise<{ chrome: ChildProcess; port: number }> {
  const executable = findBrowser();
  if (!executable) throw new Error("Chrome/Edge not found; set WAGENT_BROWSER.");
  const profile = join(home(), "providers", "deepseek-web", "chrome-profile");
  mkdirSync(profile, { recursive: true });
  const devTools = join(profile, "DevToolsActivePort");
  rmSync(devTools, { force: true });
  const args = [`--user-data-dir=${profile}`, "--remote-debugging-port=0", ...(process.env.WAGENT_HEADLESS === "1" ? ["--headless=new", "--window-size=1440,1200"] : ["--start-maximized"]), URL];
  const chrome = spawn(executable, args, { stdio: "ignore" });
  for (let i = 0; i < 100; i++) {
    if (existsSync(devTools)) {
      const port = Number(readFileSync(devTools, "utf8").split(/\r?\n/)[0]);
      if (port) return { chrome, port };
    }
    await Bun.sleep(150);
  }
  chrome.kill();
  throw new Error("Browser debugging endpoint did not become ready.");
}

export async function askDeepSeekWeb(prompt: string, options: DeepSeekWebOptions = {}): Promise<DeepSeekReply> {
  const { chrome, port } = await launch();
  const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  try {
    const context = browser.contexts()[0];
    if (!context) throw new Error("No browser context available.");
    const page = context.pages().find(page => page.url().includes("deepseek.com")) ?? context.pages()[0] ?? await context.newPage();
    const target = options.conversationUrl ?? URL;
    if (page.url() !== target) await page.goto(target, { waitUntil: "domcontentloaded", timeout: 60_000 });
    const input = await waitComposer(page);
    if (options.newChat) await clickControl(page, ["new chat", "new conversation", "新しいチャット"], true);
    if (options.deepThink !== undefined && !await clickControl(page, ["deepthink", "deep think", "r1", "深く考える"], options.deepThink)) throw new Error("DeepThink control not found.");
    if (options.search !== undefined && !await clickControl(page, ["search", "web search", "検索"], options.search)) throw new Error("Search control not found.");
    if (options.attachments?.length) {
      const files = options.attachments.map(resolve);
      for (const file of files) if (!existsSync(file)) throw new Error(`Attachment not found: ${file}`);
      const fileInput = page.locator('input[type="file"]').last();
      if (!await fileInput.count()) throw new Error("File upload control not found.");
      await fileInput.setInputFiles(files);
    }
    const before = (await replies(page)).length;
    if (await input.evaluate(element => element.tagName.toLowerCase()) === "textarea") await input.fill(prompt); else { await input.click(); await page.keyboard.insertText(prompt); }
    const send = page.locator('button[aria-label*="send" i], button[aria-label*="送信" i]').filter({ visible: true }).last();
    if (await send.count()) await send.click(); else await input.press("Enter");

    const timeout = options.timeoutMs ?? 180_000;
    const start = Date.now();
    let previous = "";
    let stableAt = 0;
    while (Date.now() - start < timeout) {
      const current = (await replies(page)).at(-1);
      if ((await replies(page)).length > before && current?.text) {
        if (current.text === previous) { if (!stableAt) stableAt = Date.now(); if (Date.now() - stableAt > 1200) return { ...current, conversationUrl: page.url() }; }
        else { previous = current.text; stableAt = 0; }
      }
      await page.waitForTimeout(350);
    }
    throw new Error("Timed out waiting for DeepSeek response.");
  } finally {
    await browser.close().catch(() => undefined);
    chrome.kill();
  }
}
