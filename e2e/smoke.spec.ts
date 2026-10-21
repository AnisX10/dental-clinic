import { expect, test } from "@playwright/test";

/** Offline-free smoke across the money and clinical paths:
 * dashboard → patient creation → odontogram condition → treatment →
 * payment ledger → documents/attachments → settings. Serial because later
 * tests build on the patient created first. */
test.describe.configure({ mode: "serial" });

let patientIdNumber = 0;

const APNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

test("dashboard loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1.page-title")).toContainText("Aujourd");
});

test("create patient via the real form", async ({ page }) => {
  await page.goto("/patients");
  await page.getByRole("button", { name: "Ajouter un patient" }).click();
  await page.fill("#np-nom", "E2e");
  await page.fill("#np-prenom", "Patient");
  await page.fill("#np-tel", "0550 21 21 21");
  await page.locator(".dialog-actions .btn-primary").click();
  await expect(page).toHaveURL(/\/patients\/\d+$/);

  const match = /\/patients\/(\d+)$/.exec(page.url());
  patientIdNumber = Number(match?.[1] ?? 0);
  await expect(page.locator("h1.patient-full-name")).toContainText("E2e Patient");
});

test("odontogram: apply a whole-tooth condition", async ({ page }) => {
  await page.goto(`/patients/${patientIdNumber}?tab=odontogramme`);
  await page.getByLabel("Dent 26").first().click();
  await page.getByRole("button", { name: "Couronne" }).click();
  await expect(page.locator(".cond-current")).toContainText("Couronne");
});

test("treatment linked to tooth 26", async ({ page }) => {
  await page.goto(`/patients/${patientIdNumber}?tab=odontogramme`);
  await page.getByLabel("Dent 26").first().click();
  await page.locator(".odonto-tooth-inspector").getByText("Ajouter").click();
  await page.selectOption("#trt-item", { index: 1 });
  const selectedName = (await page.locator("#trt-item option:checked").textContent()) ?? "";
  const itemName = selectedName.split("(")[0].trim();
  await page.fill("#trt-price", "7500");
  await page.locator(".dialog-actions .btn-primary").click();

  await page.goto(`/patients/${patientIdNumber}?tab=traitements`);
  const row = page.locator("table.table tbody tr").first();
  await expect(row).toContainText(itemName);
  await expect(row).toContainText("26");
});

test("payment lands in the patient ledger", async ({ page }) => {
  await page.goto(`/patients/${patientIdNumber}?tab=paiements`);
  await page.getByRole("button", { name: "Encaisser un paiement" }).first().click();
  await page.fill("#pay-amount", "1500");
  await page.locator(".dialog-actions .btn-primary").click();

  await expect(page.locator(".money-row").filter({ hasText: "Payé" }).locator(".money-value"))
    .toContainText(/1[\u202f\u00a0 ]?500\s+DA/);
});

test("documents tab shows attachments card and upload works", async ({ page }) => {
  await page.goto(`/patients/${patientIdNumber}?tab=documents`);
  await expect(page.getByText("Ajouter une pièce jointe")).toBeVisible();
  await page.setInputFiles(
    "#att-file",
    { name: "e2e-radio.png", mimeType: "image/png", buffer: APNG },
  );
  await expect(page.locator("table.table")).toContainText("e2e-radio.png");
});

test("settings exposes backup controls and version", async ({ page }) => {
  await page.goto("/parametres");
  await expect(page.getByRole("button", { name: "Sauvegarder maintenant" })).toBeVisible();
  await expect(page.locator(".money-row").filter({ hasText: "Version" })).toContainText(/\d+\.\d+/);
});
