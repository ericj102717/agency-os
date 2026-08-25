import type { Express } from "express";
import { createServer } from 'node:http';
import type { Server } from 'node:http';
import http from 'node:http';

// Proxy /api/* requests to the FastAPI backend on port 8088
const FASTAPI_PORT = 8088;

// Headers that must NEVER be forwarded from the client to the backend.
// Express is the only layer that should set these on the outbound request.
const STRIP_HEADERS = [
  'content-length',
  'transfer-encoding',
  'connection',
  'host',
  'x_api_key',
  'authorization',
  'x-command-center-write-key',
];

// Methods that require the client to supply a write key.
const MUTATION_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function proxyToFastAPI(req: any, res: any) {
  const apiKey = process.env.AGENCY_API_KEY || '';
  const writeKey = process.env.AGENCY_WRITE_KEY || '';

  // --- Auth gate for mutations ---
  if (MUTATION_METHODS.has(req.method.toUpperCase())) {
    const clientKey = req.headers['x-command-center-write-key'] || '';
    if (!writeKey) {
      // No write key configured — block all mutations for safety
      res.status(403).json({ error: 'Write access disabled', detail: 'No write key configured on server' });
      return;
    }
    if (clientKey !== writeKey) {
      res.status(401).json({ error: 'Unauthorized', detail: 'Valid write key required for mutations' });
      return;
    }
  }

  // --- Build outbound path with backend API key ---
  // Strip any inbound x_api_key from the query string before appending our own
  let path = req.originalUrl;
  path = path.replace(/([?&])x_api_key=[^&]*&?/g, '$1');
  path = path.replace(/[?&]$/, '');
  if (apiKey) {
    const sep = path.includes('?') ? '&' : '?';
    path = `${path}${sep}x_api_key=${encodeURIComponent(apiKey)}`;
  }

  // --- Build clean headers (strip dangerous forwarded headers) ---
  const headers: Record<string, string> = {};
  for (const [key, value] of Object.entries(req.headers)) {
    if (!STRIP_HEADERS.includes(key.toLowerCase())) {
      headers[key] = value as string;
    }
  }
  headers['host'] = `127.0.0.1:${FASTAPI_PORT}`;

  const options = {
    hostname: '127.0.0.1',
    port: FASTAPI_PORT,
    path,
    method: req.method,
    headers,
  };

  const proxyReq = http.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode || 200, proxyRes.headers);
    proxyRes.pipe(res);
  });

  // --- Timeout so backend hangs can't hold Express open ---
  proxyReq.setTimeout(60000, () => {
    proxyReq.destroy(new Error('Backend timeout'));
  });

  proxyReq.on('error', (err) => {
    console.error(`[proxy] Error forwarding to FastAPI: ${err.message}`);
    if (!res.headersSent) {
      res.status(502).json({ error: 'Backend unavailable', detail: err.message });
    }
  });

  // --- Body handling: always compute Content-Length from actual bytes written ---
  if (req.body !== undefined && req.body !== null) {
    const bodyData = JSON.stringify(req.body);
    const bodyBytes = Buffer.byteLength(bodyData);
    proxyReq.setHeader('Content-Length', String(bodyBytes));
    proxyReq.write(bodyData);
  } else {
    // No body — ensure Content-Length is 0 or absent
    proxyReq.setHeader('Content-Length', '0');
  }
  proxyReq.end();
}

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  // Proxy all /api/* requests to the FastAPI backend
  app.use('/api', (req, res, next) => {
    proxyToFastAPI(req, res);
  });

  return httpServer;
}
