import { Suspense } from "react";
import Editor from "../_editor/Editor";
import "../_editor/editor.css";

export const metadata = { title: "Editor — FairHire" };

export default function Page() {
  // Editor reads the query string, so it renders on the client below this boundary.
  return (
    <Suspense fallback={<div className="boot" aria-busy="true" />}>
      <Editor />
    </Suspense>
  );
}
