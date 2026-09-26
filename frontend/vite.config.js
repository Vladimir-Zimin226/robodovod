import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { cp, mkdir, readFile, stat } from 'node:fs/promises'
import { extname, join, normalize, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))
const robcraftRoot = resolve(frontendRoot, '../robcraft')
const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
}

function robcraftAssets() {
  return {
    name: 'robcraft-same-origin-assets',
    configureServer(server) {
      server.middlewares.use('/robcraft', async (request, response, next) => {
        try {
          const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname)
          const relative = normalize(pathname).replace(/^(\.\.(\/|\\|$))+/, '').replace(/^[/\\]+/, '')
          let target = join(robcraftRoot, relative || 'index.html')
          if (!target.startsWith(robcraftRoot) || !(await stat(target)).isFile()) return next()
          response.setHeader('Content-Type', contentTypes[extname(target)] || 'application/octet-stream')
          response.setHeader('Cache-Control', 'no-store')
          response.end(await readFile(target))
        } catch {
          next()
        }
      })
    },
    async writeBundle(options) {
      const outputRoot = resolve(options.dir || join(frontendRoot, 'dist'), 'robcraft')
      await mkdir(outputRoot, { recursive: true })
      await Promise.all([
        cp(join(robcraftRoot, 'index.html'), join(outputRoot, 'index.html')),
        cp(join(robcraftRoot, 'styles.css'), join(outputRoot, 'styles.css')),
        cp(join(robcraftRoot, 'src'), join(outputRoot, 'src'), { recursive: true }),
      ])
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), robcraftAssets()],
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY || 'http://localhost:8000',
    },
  },
})
