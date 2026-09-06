import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

export interface Skill {
  name: string;
  description: string;
  tags: string[];
  instructions: string;
  path: string;
}

function parseFrontmatter(source: string): { meta: Record<string, string>; body: string } {
  if (!source.startsWith("---\n")) return { meta: {}, body: source.trim() };
  const end = source.indexOf("\n---\n", 4);
  if (end < 0) return { meta: {}, body: source.trim() };
  const meta = Object.fromEntries(source.slice(4, end).split("\n").map(line => {
    const at = line.indexOf(":");
    return at < 0 ? [line.trim(), ""] : [line.slice(0, at).trim(), line.slice(at + 1).trim()];
  }));
  return { meta, body: source.slice(end + 5).trim() };
}

export async function loadSkills(root = "skills"): Promise<Skill[]> {
  const entries = await readdir(root, { withFileTypes: true }).catch(() => []);
  const skills: Skill[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const path = join(root, entry.name, "SKILL.md");
    const source = await readFile(path, "utf8").catch(() => null);
    if (!source) continue;
    const { meta, body } = parseFrontmatter(source);
    skills.push({
      name: meta.name || entry.name,
      description: meta.description || "",
      tags: (meta.tags || "").split(",").map(value => value.trim()).filter(Boolean),
      instructions: body,
      path,
    });
  }
  return skills;
}

export function selectSkills(prompt: string, skills: Skill[], explicit: string[] = []): Skill[] {
  if (explicit.length) return skills.filter(skill => explicit.includes(skill.name));
  const haystack = prompt.toLowerCase();
  return skills.filter(skill => [skill.name, skill.description, ...skill.tags].some(term => term && haystack.includes(term.toLowerCase())));
}

export function applySkills(messages: { role: string; content: string }[], skills: Skill[]): { role: string; content: string }[] {
  if (!skills.length) return messages;
  const instructions = skills.map(skill => `# Skill: ${skill.name}\n${skill.instructions}`).join("\n\n");
  return [{ role: "system", content: `Wagent Skills:\n\n${instructions}` }, ...messages];
}
