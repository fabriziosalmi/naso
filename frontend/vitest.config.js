import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/vitest-setup.js'],
    include: ['src/**/*.test.{js,jsx,ts,tsx}'],
    exclude: ['src/**/e2e/**', 'tests/e2e/**', 'e2e/**'],
  },
});
