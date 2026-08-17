import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Shared by `server` (vite dev) and `preview` (the built bundle). The E2E
// suite runs against `preview`, so without mirroring these the API calls the
// app makes on mount would 404 there while working in dev — a difference that
// only shows up as a confusing test failure.
// Anchored on a trailing slash, and that slash is load-bearing.
//
// These keys used to be bare prefixes, and Vite matches a bare prefix against
// any path that starts with it — including the application's own client-side
// routes. `/ai` swallowed `/ai-analyst`, and `/identities` collided with the
// route of the same name exactly. Reloading either page, or opening a bookmark
// or a shared link to one, left the application entirely and rendered the API's
// reply in the browser:
//
//     {"detail":"Not Found"}
//
// Every call the app makes under these prefixes has a slash after it —
// `/ai/health`, `/identities/`, `/identities/graph` — so requiring the slash
// separates the API from the routes without touching either. The regex form is
// what tells Vite to match rather than prefix-test.
const API_PREFIXES = ['auth', 'tenants', 'keywords', 'leaks', 'identities', 'yara', 'system', 'users', 'ai']

const apiProxy = Object.fromEntries(
  API_PREFIXES.map((prefix) => [`^/${prefix}/`, 'http://localhost:8000'])
)

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks: {
          // Keep React + router in one stable chunk.
          react: ['react', 'react-dom', 'react-router-dom'],
          // Heavy viz libs — loaded with their respective routes.
          graph: ['react-force-graph-2d'],
          charts: ['recharts'],
          // Radix primitives cluster.
          radix: [
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-tooltip',
            '@radix-ui/react-tabs',
            '@radix-ui/react-scroll-area',
            '@radix-ui/react-separator',
            '@radix-ui/react-avatar',
            '@radix-ui/react-slot',
          ],
          markdown: ['react-markdown'],
          // react-syntax-highlighter pulls in Prism + grammars; keep it isolated
          // so it only ships when the AI Co-Analyst renders a fenced code block.
          syntax: ['react-syntax-highlighter'],
          tour: ['react-joyride'],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{js,jsx}"],
    exclude: ["tests/**", "e2e/**", "node_modules/**"],
    clearMocks: true,
  },
  server: {
    proxy: apiProxy,
  },
  preview: {
    proxy: apiProxy,
  },
})
