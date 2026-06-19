import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest-only config (kept out of tsconfig.node so the project's Vite 8 types
// and Vitest's vendored Vite types don't clash under `tsc -b`). esbuild's
// automatic JSX runtime lets test files render components without importing React.
export default defineConfig({
  plugins: [react()],
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: './src/test/setup.ts',
  },
})
