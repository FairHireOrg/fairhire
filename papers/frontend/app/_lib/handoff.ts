/**
 * Hands a file chosen on the landing page to the editor.
 *
 * Files can't travel through a URL, and the editor never persists uploads, so the landing page
 * parks the File here and navigates client-side; the editor takes it once on mount.
 */
let pending: File | null = null;

export const parkFile = (f: File) => { pending = f; };

export function takeFile(): File | null {
  const f = pending;
  pending = null;
  return f;
}
