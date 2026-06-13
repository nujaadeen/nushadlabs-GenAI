import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Load .env so VITE_PROXY_TARGET is available at config time.
  // Falls back to localhost:8000 if the file doesn't exist yet.
  const env = loadEnv(mode, process.cwd(), '');
  const target = env.VITE_PROXY_TARGET || 'http://localhost:8000';

  return {
    server: {
      proxy: {
        // Proxy /chat and /health to the FastAPI backend.
        // Because the browser calls relative paths ("/chat") everything is
        // same-origin — no CORS pre-flight, no Authorization header stripping.
        //
        // SSE note: http-proxy (used internally by Vite) forwards chunked
        // Transfer-Encoding responses immediately as long as the backend sets
        //   Content-Type: text/event-stream
        //   Cache-Control: no-cache
        // FastAPI's StreamingResponse already sets both headers, so no extra
        // configuration is needed to avoid proxy-level buffering.
        '/chat': {
          target,
          changeOrigin: true,
        },
        '/health': {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
