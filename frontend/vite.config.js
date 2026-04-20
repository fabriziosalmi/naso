import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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
    proxy: {
      '/auth': 'http://localhost:8000',
      '/tenants': 'http://localhost:8000',
      '/keywords': 'http://localhost:8000',
      '/leaks': 'http://localhost:8000',
      '/identities': 'http://localhost:8000',
      '/yara': 'http://localhost:8000',
      '/system': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/ai': 'http://localhost:8000',
    }
  }
})
