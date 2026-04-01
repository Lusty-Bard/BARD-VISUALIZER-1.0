import { defineConfig } from 'vite';

const visualizerStateStore = new Map();

const createVisualizerRelayPlugin = () => ({
  name: 'visualizer-relay',
  configureServer(server) {
    server.middlewares.use('/api/visualizer-state', (req, res) => {
      const url = new URL(req.url, 'http://127.0.0.1');
      const channel = url.searchParams.get('channel') || 'bard-visualizer-default';

      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

      if (req.method === 'OPTIONS') {
        res.statusCode = 204;
        res.end();
        return;
      }

      if (req.method === 'GET') {
        const payload = visualizerStateStore.get(channel) ?? {
          settings: null,
          frame: null,
          updatedAt: 0,
        };

        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(payload));
        return;
      }

      if (req.method === 'POST') {
        let body = '';

        req.on('data', (chunk) => {
          body += chunk;
        });

        req.on('end', () => {
          try {
            const payload = JSON.parse(body || '{}');
            visualizerStateStore.set(channel, {
              settings: payload.settings ?? null,
              frame: payload.frame ?? null,
              updatedAt: Date.now(),
            });
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: true }));
          } catch {
            res.statusCode = 400;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ ok: false }));
          }
        });

        return;
      }

      res.statusCode = 405;
      res.end();
    });
  },
});

export default defineConfig({
  plugins: [createVisualizerRelayPlugin()],
});
