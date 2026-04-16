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
    }
  }
})
