import { expect, test } from "@playwright/test";

/** Independent PDFs: different page sizes, fonts, columns, background colors and rotation. */
function layoutFixture(): Buffer {
  const objects: string[] = [];
  const object = (value: string) => { objects.push(value); return objects.length; };
  object("<< /Type /Catalog /Pages 2 0 R >>"); object("");
  const fonts = ["Helvetica", "Times-Bold", "Courier"].map(font => object(`<< /Type /Font /Subtype /Type1 /BaseFont /${font} >>`));
  const resources = `<< /Font << ${fonts.map((id, i) => `/F${i + 1} ${id} 0 R`).join(" ")} >> >>`;
  const definitions = [
    { size: "612 792", rotation: 0, content: "BT /F1 25 Tf 50 730 Td (Generic Single Column) Tj /F1 12 Tf 0 -40 Td (Experience) Tj 0 -30 Td (Engineer - Organization) Tj ET 50 670 m 560 670 l S" },
    { size: "842 595", rotation: 0, content: "0.9 0.95 1 rg 35 35 230 525 re f 0 0 0 rg BT /F2 24 Tf 50 535 Td (Two Columns) Tj /F3 13 Tf 0 -45 Td (Python, SQL, Rust) Tj ET BT /F1 20 Tf 315 530 Td (Work History) Tj /F1 12 Tf 0 -40 Td (Different company) Tj ET 0.2 0.3 0.7 rg 315 90 200 100 re f 1 1 1 rg BT /F2 16 Tf 330 150 Td (White text on blue) Tj ET" },
    { size: "400 600", rotation: 90, content: "0.95 0.9 0.85 rg 0 0 400 600 re f 0 0 0 rg BT /F2 22 Tf 40 530 Td (Rotated Page) Tj /F1 12 Tf 0 -40 Td (Different size and rotation) Tj ET BT /F3 18 Tf 0 1 -1 0 330 100 Tm (Vertical text) Tj ET" },
  ];
  const pages = definitions.map(({ size, rotation, content }) => {
    const stream = object(`<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`);
    return object(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${size}] /Rotate ${rotation} /Resources ${resources} /Contents ${stream} 0 R >>`);
  });
  objects[1] = `<< /Type /Pages /Kids [${pages.map(id => `${id} 0 R`).join(" ")}] /Count ${pages.length} >>`;
  let data = "%PDF-1.7\n";
  const offsets = objects.map((value, i) => { const offset = Buffer.byteLength(data); data += `${i + 1} 0 obj\n${value}\nendobj\n`; return offset; });
  const xref = Buffer.byteLength(data);
  data += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.map(offset => `${offset.toString().padStart(10, "0")} 00000 n \n`).join("")}`;
  data += `trailer << /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(data);
}

test("PDF overlays preserve all original pages and edits survive scoring, reload and zoom", async ({ page }) => {
  const errors: string[] = [];
  const analyses: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem("fairhire:onboarding:v1", "complete"));
  const fixtureDocument = { contact: { name: "Fixture", email: "", phone: "", location: "", linkedin: "", github: "" }, summary: "", experience: [], education: [], skills: [], certifications: [], projects: [] };
  const response = { document: fixtureDocument, resume_text: "Fixture", job_description: "", ats_score: 75, ats_grade: "Good", scorable: true, dimensions: [], recommendations: [], sections_found: {}, resume_fields: {}, skills: [], keyword_groups: [], keyword_coverage: { matched: 0, total: 0 } };
  await page.route("**/api/analyze", async route => { analyses.push(route.request().postData() ?? ""); await route.fulfill({ json: response }); });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(process.env.TEST_BASE_URL ?? "http://localhost:3000");
  await page.getByLabel("Upload resume", { exact: true }).setInputFiles({ name: "generic-layouts.pdf", mimeType: "application/pdf", buffer: layoutFixture() });
  await page.waitForURL("**/report");
  await page.locator('[data-page-number="3"] .pdf-text-box').last().waitFor();
  await expect(page.locator(".pdf-original-page")).toHaveCount(3);
  await page.mouse.move(0, 0);
  for (let index = 0; index < 3; index++) {
    const originalPage = page.locator(".pdf-original-page").nth(index);
    const original = await originalPage.locator("canvas").screenshot();
    const editable = await originalPage.screenshot();
    expect(editable.equals(original), `Unchanged page ${index + 1} must be pixel-identical to its native rendering`).toBe(true);
  }
  const heading = page.locator(".pdf-text-box").first();
  await heading.fill("Edited generic heading");
  await page.getByRole("heading", { name: "Overview", exact: true }).click();
  await page.getByRole("button", { name: "Update report", exact: true }).click();
  await expect(page.getByText("Resume edited. Update the report to refresh scores.")).toHaveCount(0);
  expect(analyses[1]).toContain("Edited generic heading");
  expect(analyses[1]).toContain("Rotated Page");
  await page.reload();
  await expect(page.locator(".pdf-text-box").first()).toHaveValue("Edited generic heading");
  await page.getByRole("slider", { name: "Zoom" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator(".pdf-text-box").first()).toHaveValue("Edited generic heading");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.locator(".pdf-original-page")).toHaveCount(3);
  expect(errors).toEqual([]);
});
