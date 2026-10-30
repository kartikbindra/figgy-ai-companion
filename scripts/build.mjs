import { build } from 'esbuild';
import { mkdir, copyFile } from 'node:fs/promises';
await mkdir('apps/web/dist', { recursive: true });
await build({ entryPoints: ['apps/web/src/main.tsx'], outdir: 'apps/web/dist', bundle: true,
  minify: true, sourcemap: true, format: 'esm', target: ['es2022'],
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'linked' });
await copyFile('apps/web/index.html', 'apps/web/dist/index.html');
console.log('Built local UI → apps/web/dist');
