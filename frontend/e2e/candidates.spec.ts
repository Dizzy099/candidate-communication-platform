import { expect, test } from "@playwright/test";
import { createCandidate, phoneEndingIn, searchFor, uniqueTag } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Candidate communication" })).toBeVisible();
});

test("add a candidate with validation, then find them by search", async ({ page }) => {
  const name = `Asha ${uniqueTag()}`;
  const phone = phoneEndingIn();

  await page.getByRole("button", { name: "Add candidate" }).click();
  const dialog = page.getByRole("dialog", { name: "Add Candidate" });
  const submit = dialog.getByRole("button", { name: "Add candidate" });
  await expect(submit).toBeDisabled();

  await dialog.getByLabel("Candidate Name *").fill(name);
  await dialog.getByLabel("Mobile Number *").fill("12345");
  await dialog.getByLabel("Email *").fill("asha@example");
  await submit.click();
  await expect(dialog.getByText(/10-digit Indian mobile number/)).toBeVisible();
  await expect(dialog.getByText(/valid email address/)).toBeVisible();

  await dialog.getByLabel("Mobile Number *").fill(`+91 ${phone.slice(0, 5)} ${phone.slice(5)}`);
  await dialog.getByLabel("Email *").fill(`${name.replace(" ", ".").toLowerCase()}@example.com`);
  await submit.click();

  await expect(page.getByText(`${name} added successfully`)).toBeVisible();
  await expect(dialog).toBeHidden();
  await searchFor(page, name);
  const row = page.getByRole("row", { name: new RegExp(name) });
  await expect(row).toContainText(`+91 ${phone}`);
  await expect(row).toContainText("NA");
});

test("duplicate mobile numbers are rejected with the existing candidate's name", async ({ page, request }) => {
  const existing = `Bina ${uniqueTag()}`;
  const phone = phoneEndingIn();
  await createCandidate(request, existing, phone);

  await page.getByRole("button", { name: "Add candidate" }).click();
  const dialog = page.getByRole("dialog", { name: "Add Candidate" });
  await dialog.getByLabel("Candidate Name *").fill(`Other ${uniqueTag()}`);
  await dialog.getByLabel("Mobile Number *").fill(`0${phone}`);
  await dialog.getByLabel("Email *").fill(`${uniqueTag()}@example.com`);
  await dialog.getByRole("button", { name: "Add candidate" }).click();
  await expect(dialog.getByText(new RegExp(`already exists: ${existing}`))).toBeVisible();
});

test("search narrows the list and shows an empty state with no matches", async ({ page, request }) => {
  const tag = uniqueTag();
  await createCandidate(request, `Chetan ${tag}`, phoneEndingIn());
  await createCandidate(request, `Divya ${tag}`, phoneEndingIn());

  await searchFor(page, tag);
  await expect(page.getByRole("button", { name: `Chetan ${tag}` })).toBeVisible();
  await expect(page.getByRole("button", { name: `Divya ${tag}` })).toBeVisible();
  await expect(page.getByText("1–2 of 2")).toBeVisible();

  await searchFor(page, `${tag}zzz`);
  await expect(page.getByText("No matching candidates")).toBeVisible();
  await page.getByRole("button", { name: "Clear search and filters" }).click();
  await expect(page.getByRole("textbox", { name: /Search candidates/ })).toHaveValue("");
});

test("delete several candidates after confirmation", async ({ page, request }) => {
  const tag = uniqueTag();
  for (const first of ["Esha", "Farhan", "Gauri"]) await createCandidate(request, `${first} ${tag}`, phoneEndingIn());

  await searchFor(page, tag);
  await expect(page.getByText("1–3 of 3")).toBeVisible();
  await page.getByRole("checkbox", { name: "Select all candidates on this page" }).check();
  await page.getByRole("button", { name: "Delete candidate" }).click();

  const dialog = page.getByRole("dialog", { name: "Delete Candidates" });
  await expect(dialog).toContainText("Are you sure you want to delete 3 Candidates?");
  await dialog.getByRole("button", { name: "Delete 3 candidates" }).click();
  await expect(page.getByText("3 Candidates deleted successfully")).toBeVisible();
  await expect(page.getByText("No matching candidates")).toBeVisible();
});
