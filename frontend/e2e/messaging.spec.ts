import { expect, test } from "@playwright/test";
import { createCandidate, phoneEndingIn, searchFor, uniqueTag } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Candidate communication" })).toBeVisible();
});

test("message one candidate and watch provider status updates arrive", async ({ page, request }) => {
  const name = `Harsh ${uniqueTag()}`;
  await createCandidate(request, name, phoneEndingIn());

  await searchFor(page, name);
  await page.getByRole("button", { name }).click();
  const history = page.getByRole("dialog", { name: "Communication history" });
  await expect(history.getByText("No communication history")).toBeVisible();

  await history.getByRole("button", { name: "Send message" }).click();
  const drawer = page.getByRole("dialog", { name: "Send Message" });
  await expect(drawer.getByText("1 Recipient")).toBeVisible();
  await drawer.getByRole("textbox", { name: /Message/ }).fill("Hi {{first_name}}, your interview is tomorrow at 11 AM.");
  await drawer.getByRole("button", { name: "Send message" }).click();

  await expect(page.getByText(`Message sent to ${name}`)).toBeVisible();
  const row = page.getByRole("row", { name: new RegExp(name) });
  // Sent -> Delivered -> Read are confirmed by the (simulated) provider via webhooks.
  await expect(row.getByText("Read")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name }).click();
  await expect(history.getByText(`Hi ${name.split(" ")[0]}, your interview is tomorrow at 11 AM.`)).toBeVisible();
  await history.getByRole("button", { name: "Details" }).click();
  await expect(history.getByText(/Provider: Provider reported 'delivered'/)).toBeVisible();
  await expect(history.getByText(/Provider: Provider reported 'read'/)).toBeVisible();
});

test("bulk send reports each recipient independently and allows eligible retries", async ({ page, request }) => {
  const tag = uniqueTag();
  const ok = `Isha ${tag}`;
  const invalid = `Jatin ${tag}`;
  const flaky = `Kiran ${tag}`;
  await createCandidate(request, ok, phoneEndingIn());
  await createCandidate(request, invalid, phoneEndingIn("000")); // invalid recipient
  await createCandidate(request, flaky, phoneEndingIn("666")); // fails 3 automatic attempts

  await searchFor(page, tag);
  await expect(page.getByText("1–3 of 3")).toBeVisible();
  await page.getByRole("checkbox", { name: "Select all candidates on this page" }).check();
  await page.getByRole("button", { name: "Send message" }).click();

  const drawer = page.getByRole("dialog", { name: "Send Message" });
  await expect(drawer.getByText("3 Recipients")).toBeVisible();
  await drawer.getByRole("textbox", { name: /Message/ }).fill("Interview update for {{full_name}}");
  await drawer.getByRole("button", { name: "Send to 3 candidates" }).click();
  await page.getByRole("dialog", { name: "Send message?" }).getByRole("button", { name: "Send to 3 candidates" }).click();

  await expect(page.getByText(/Sending to 3 candidates/)).toBeVisible();
  await expect(page.getByText("Message sent to 1 of 3 candidates. 2 failed.")).toBeVisible({ timeout: 45_000 });
  await page.getByRole("button", { name: "View details" }).click();

  const results = page.getByRole("dialog", { name: "Delivery results" });
  await expect(results.getByText("Invalid mobile number:")).toBeVisible();
  await expect(results.getByRole("button", { name: `Retry message to ${invalid}` })).toHaveCount(0);
  await results.getByRole("button", { name: `Retry message to ${flaky}` }).click();
  await expect(results.getByRole("button", { name: `Retry message to ${flaky}` })).toHaveCount(0, { timeout: 30_000 });
  const flakyRow = results.getByRole("listitem").filter({ hasText: flaky });
  await expect(flakyRow.getByText(/Sent|Delivered|Read/)).toBeVisible({ timeout: 30_000 });
});
