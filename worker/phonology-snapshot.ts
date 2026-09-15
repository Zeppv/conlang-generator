async function hash(text: string) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)))].map(b => b.toString(16).padStart(2, '0')).join('');
}

// Pin one immutable snapshot for the entire request. Activation during a request
// cannot combine evidence from two versions. Old snapshots remain readable.
export class Snapshot {
  db: D1Database;
  id: string;
  hashes: Record<string, string> = {};
  constructor(db: D1Database, id: string) { this.db = db; this.id = id; }
  async readMany(keys: string[], sealed = true): Promise<Map<string, any>> {
    const output = new Map<string, any>();
    for (let start = 0; start < keys.length; start += 80) {
      const group = keys.slice(start, start + 80);
      const rows = await this.db.prepare(`SELECT key,position,payload,checksum FROM phonology_web_chunk WHERE snapshot=? AND key IN (${group.map(() => '?').join(',')}) ORDER BY key,position`).bind(this.id, ...group).all<{key: string; position: number; payload: string; checksum: string}>();
      for (const key of group) {
        const chunks = rows.results.filter(row => row.key === key);
        if (!chunks.length || chunks.some((row, index) => row.position !== index)) throw new Error('Missing snapshot chunks');
        for (const chunk of chunks) if (await hash(chunk.payload) !== chunk.checksum) throw new Error('Corrupt snapshot chunk');
        const text = chunks.map(row => row.payload).join('');
        if (await hash(text) !== (sealed ? this.hashes[key] : this.id)) throw new Error('Snapshot checksum mismatch');
        output.set(key, JSON.parse(text));
      }
    }
    return output;
  }
  async read(key: string) { return (await this.readMany([key])).get(key); }
  static async open(db: D1Database, requested?: string) {
    if (requested !== undefined && !/^[a-f0-9]{64}$/.test(requested)) throw new Error('Invalid snapshot identity');
    const active = requested ? {snapshot: requested} : await db.prepare('SELECT snapshot FROM phonology_web_active WHERE id=1').first<{snapshot: string}>();
    if (!active) throw new Error('No active snapshot');
    const snapshot = new Snapshot(db, active.snapshot);
    const manifest = (await snapshot.readMany(['manifest'], false)).get('manifest');
    if (manifest.format_version !== 1) throw new Error('Unsupported snapshot format');
    snapshot.hashes = manifest.records;
    return snapshot;
  }
}
