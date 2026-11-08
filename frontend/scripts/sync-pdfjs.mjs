import { cp, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const pdfjs = dirname(require.resolve("pdfjs-dist/package.json"));
const target = new URL("../public/pdfjs/", import.meta.url);
await mkdir(target, { recursive: true });
await cp(join(pdfjs, "build/pdf.worker.min.mjs"), new URL("pdf.worker.min.mjs", target));
for (const folder of ["standard_fonts", "cmaps", "wasm"]) {
  await cp(join(pdfjs, folder), new URL(folder + "/", target), { recursive: true });
}
