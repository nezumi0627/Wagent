import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { homedir } from "node:os";

export interface RuntimeSession {
  id: string;
  providerId?: string;
  modelId?: string;
  providerState?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export class SessionStore {
  readonly #file: string;
  readonly #sessions = new Map<string, RuntimeSession>();

  constructor(home = process.env.WAGENT_HOME ?? join(homedir(), ".wagent")) {
    this.#file = join(home, "sessions.json");
  }

  async load(): Promise<void> {
    try {
      const rows = JSON.parse(await readFile(this.#file, "utf8")) as RuntimeSession[];
      for (const row of rows) this.#sessions.set(row.id, row);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    }
  }

  get(id: string): RuntimeSession | undefined { return this.#sessions.get(id); }
  list(): RuntimeSession[] { return [...this.#sessions.values()]; }

  async upsert(session: RuntimeSession): Promise<void> {
    this.#sessions.set(session.id, session);
    await mkdir(dirname(this.#file), { recursive: true });
    await writeFile(this.#file, JSON.stringify(this.list(), null, 2));
  }
}
