import { cpSync, existsSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(process.cwd());
const src = resolve(root, 'node_modules/tinymce');
const dest = resolve(root, 'public/tinymce');

if (!existsSync(src)) {
  console.warn('[copy-tinymce] node_modules/tinymce not found, skip.');
  process.exit(0);
}

if (existsSync(dest)) {
  rmSync(dest, { recursive: true });
}
cpSync(src, dest, { recursive: true });
console.log('[copy-tinymce] Copied tinymce -> public/tinymce');
