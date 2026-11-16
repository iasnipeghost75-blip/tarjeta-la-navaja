// Guarda el estado compartido de la tarjeta (clientes, sellos, avisos, ajustes) en Vercel Blob.
// Sin la variable BLOB_READ_WRITE_TOKEN usa memoria, solo para pruebas locales.
const PATH = 'navaja/state.json';
let mem = null;

async function readStore() {
  if (!process.env.BLOB_READ_WRITE_TOKEN) return mem;
  const { get } = await import('@vercel/blob');
  try {
    const r = await get(PATH, { access: 'private', useCache: false });
    if (!r || r.statusCode === 404 || !r.stream) return null;
    return JSON.parse(await new Response(r.stream).text());
  } catch (e) {
    if (e && e.name === 'BlobNotFoundError') return null;
    throw e;
  }
}

async function writeStore(state) {
  if (!process.env.BLOB_READ_WRITE_TOKEN) { mem = state; return; }
  const { put } = await import('@vercel/blob');
  await put(PATH, JSON.stringify(state), {
    access: 'private',
    allowOverwrite: true,
    addRandomSuffix: false,
    contentType: 'application/json',
    cacheControlMaxAge: 0,
  });
}

const stamp = (o) => (o && o.u) || 0;

function mergeById(a = [], b = []) {
  const m = new Map();
  for (const x of a) m.set(x.id, x);
  for (const x of b) {
    const y = m.get(x.id);
    if (!y || stamp(x) >= stamp(y)) m.set(x.id, x);
  }
  return [...m.values()];
}

function union(a = [], b = []) {
  const m = new Map();
  for (const x of a) m.set(x.id, x);
  for (const x of b) if (!m.has(x.id)) m.set(x.id, x);
  return [...m.values()];
}

export function merge(cur, inc) {
  const out = { ...cur };
  out.at = { ...(cur.at || {}) };
  const iat = inc.at || {};
  for (const k of ['cfg', 'tpl', 'team', 'props']) {
    if ((iat[k] || 0) > (out.at[k] || 0)) { out[k] = inc[k]; out.at[k] = iat[k]; }
  }
  if ((iat.m || 0) > (out.at.m || 0)) { out.lastPcid = inc.lastPcid; out.at.m = iat.m; }
  out.seq = Math.max(cur.seq || 0, inc.seq || 0);
  const del = { ...(cur.del || {}) };
  for (const [id, t] of Object.entries(inc.del || {})) del[id] = Math.max(del[id] || 0, t);
  out.del = del;
  let customers = mergeById(cur.customers, inc.customers).filter((c) => !(del[c.id] && del[c.id] >= stamp(c)));
  const ids = new Set(customers.map((c) => c.id));
  out.customers = customers;
  out.events = union(cur.events, inc.events).filter((e) => ids.has(e.cid));
  out.notifs = union(cur.notifs, inc.notifs).filter((n) => ids.has(n.cid));
  return out;
}

function send(res, code, body) {
  res.statusCode = code;
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.setHeader('cache-control', 'no-store');
  res.end(JSON.stringify(body));
}

export default async function handler(req, res) {
  try {
    if (req.method === 'GET') {
      const cur = await readStore();
      if (!cur) return send(res, 200, { ver: 0, state: null });
      const q = new URL(req.url, 'http://x').searchParams;
      if (q.get('v') && Number(q.get('v')) === cur.ver) return send(res, 200, { ver: cur.ver, same: true });
      return send(res, 200, { ver: cur.ver, state: cur });
    }
    if (req.method === 'POST') {
      let body = req.body;
      if (typeof body === 'string') body = JSON.parse(body);
      if (!body || !body.state || !Array.isArray(body.state.customers)) return send(res, 400, { error: 'estado no valido' });
      const cur = await readStore();
      if (!cur || body.replace) {
        const st = { ...body.state, ver: ((cur && cur.ver) || 0) + 1 };
        await writeStore(st);
        return send(res, 200, { ver: st.ver, state: st });
      }
      if (body.state.epoch !== cur.epoch) return send(res, 200, { ver: cur.ver, state: cur, stale: true });
      const merged = merge(cur, body.state);
      merged.ver = (cur.ver || 0) + 1;
      await writeStore(merged);
      return send(res, 200, { ver: merged.ver, state: merged });
    }
    return send(res, 405, { error: 'metodo no permitido' });
  } catch (e) {
    return send(res, 500, { error: 'error del servidor' });
  }
}
