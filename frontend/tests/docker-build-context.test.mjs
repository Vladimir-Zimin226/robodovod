import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const frontend = path.join(root, 'frontend');

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map(async (entry) => {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(filename);
    return /\.(?:js|jsx|mjs|ts|tsx)$/.test(entry.name) ? [filename] : [];
  }));
  return nested.flat();
}

test('frontend Docker build stage includes every imported file outside frontend', async () => {
  const dockerfile = await readFile(path.join(frontend, 'Dockerfile'), 'utf8');
  const buildStage = dockerfile.split(/^FROM /m).slice(1, 2)[0];
  const copies = [...buildStage.matchAll(/^COPY (?!--)(.+)$/gm)].map((match) => {
    const parts = match[1].trim().split(/\s+/);
    return { sources: parts.slice(0, -1), destination: parts.at(-1) };
  });

  for (const filename of await sourceFiles(path.join(frontend, 'src'))) {
    const source = await readFile(filename, 'utf8');
    for (const match of source.matchAll(/\bfrom\s*['"](\.\.\/[^'"]+)['"]/g)) {
      const dependency = path.resolve(path.dirname(filename), match[1]);
      if (path.relative(frontend, dependency).startsWith('..')) {
        const relative = path.relative(root, dependency).replaceAll('\\', '/');
        const expected = `/${relative}`;
        const included = copies.some(({ sources, destination }) => sources.some((copied) => {
          const sourcePath = copied.replaceAll('\\', '/');
          const suffix = sourcePath.endsWith('/') && relative.startsWith(sourcePath)
            ? relative.slice(sourcePath.length) : relative === sourcePath ? path.posix.basename(relative) : null;
          if (suffix === null) return false;
          const target = destination.endsWith('/') ? `${destination}${suffix}` : destination;
          return path.posix.normalize(target) === expected;
        }));
        assert.ok(included, `${relative} is imported by ${path.relative(root, filename)} but missing from the Docker build stage`);
      }
    }
  }
});
