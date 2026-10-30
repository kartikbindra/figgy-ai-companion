import { build } from 'esbuild';
import { mkdir, copyFile, readFile, writeFile } from 'node:fs/promises';
await mkdir('apps/web/dist', { recursive: true });
await build({ entryPoints: ['apps/web/src/main.tsx'], outdir: 'apps/web/dist', bundle: true,
  minify: true, sourcemap: true, format: 'esm', target: ['es2022'],
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'linked' });
await copyFile('apps/web/index.html', 'apps/web/dist/index.html');
// A file-only preview remains usable when a restricted shell cannot bind localhost.
const preview = await build({ entryPoints: ['apps/web/src/main.tsx'], bundle: true,
  write: false, minify: true, format: 'iife', target: ['es2022'], outdir: 'preview',
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'inline' });
const js = preview.outputFiles.find(file => file.path.endsWith('.js')).text.replaceAll('</script', '<\\/script');
const css = preview.outputFiles.find(file => file.path.endsWith('.css')).text;
const html = (await readFile('apps/web/index.html', 'utf8'))
  .replace('<link rel="stylesheet" href="/main.css"/>', `<style>${css}</style>`)
  .replace('<script type="module" src="/main.js"></script>', `<script>${js}</script>`);
await writeFile('apps/web/dist/preview.html', html);
console.log('Built local UI → apps/web/dist');
