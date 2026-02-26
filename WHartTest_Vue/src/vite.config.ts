// vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue()
  ],
  // 可选：提升性能，预加载 Monaco 样式
  optimizeDeps: {
    exclude: ['monaco-editor']
  }
})