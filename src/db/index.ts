import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import * as schema from "./schema";
import path from "path";

const dbPath = path.join(process.cwd(), "jobtracker.db");
const client = createClient({ url: `file:${dbPath}` });

// Enable WAL mode and foreign keys — resolves before first request
export const dbReady = (async () => {
  await client.execute("PRAGMA journal_mode = WAL");
  await client.execute("PRAGMA foreign_keys = ON");
})();

export const db = drizzle(client, { schema });
