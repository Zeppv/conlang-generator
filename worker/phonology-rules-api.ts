import { MAX_BYTES, parseJson, realizeBundle, RuleError } from '../shared/phonology-rules.ts';

// This route deliberately needs no D1 binding or serving snapshot.
export async function phonologyRulesApi(request: Request): Promise<Response> {
  if (request.method !== 'POST') return Response.json({error: 'Method not allowed.'}, {status: 405, headers: {Allow: 'POST'}});
  if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) return Response.json({error: 'Content-Type must be application/json.'}, {status: 415});
  const reader = request.body?.getReader();
  if (!reader) return Response.json({error: 'A saved run is required.'}, {status: 400});
  try {
    const chunks: Uint8Array[] = []; let size = 0;
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BYTES) { await reader.cancel(); return Response.json({error: 'Saved run exceeds 8 MiB.'}, {status: 413}); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    let source: string;
    try { source = new TextDecoder('utf-8', {fatal: true, ignoreBOM: false}).decode(bytes); }
    catch { throw new RuleError('Saved run must be UTF-8 JSON.'); }
    return Response.json(await realizeBundle(parseJson(source)));
  } catch (error) {
    if (error instanceof RuleError) return Response.json({error: error.message}, {status: 400});
    console.error('Phonology realization failed:', error);
    return Response.json({error: 'Unable to realize this saved run.'}, {status: 500});
  }
}
