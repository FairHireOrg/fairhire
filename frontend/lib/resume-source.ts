export type PdfEdits = Record<string, string>;
export type ResumeSource = { id: string; name: string; type: string; bytes: ArrayBuffer; edits: PdfEdits };
const DB_NAME = "fairhire:resume-sources";
const STORE = "sources";

async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE, { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("Could not store the resume in this browser."));
  });
}

export async function readResumeSource(id: string): Promise<ResumeSource | undefined> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction(STORE).objectStore(STORE).get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error("Could not restore the uploaded resume."));
    });
  } finally { db.close(); }
}

export async function writeResumeSource(source: ResumeSource): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).put(source);
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(new Error("Could not save the resume edits."));
      transaction.onabort = () => reject(new Error("Could not save the resume edits."));
    });
  } finally { db.close(); }
}

export async function storeResumeSource(file: File): Promise<string> {
  const id = crypto.randomUUID();
  await writeResumeSource({ id, name: file.name, type: file.type, bytes: await file.arrayBuffer(), edits: {} });
  return id;
}
