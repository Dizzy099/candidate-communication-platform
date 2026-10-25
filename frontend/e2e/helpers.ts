import { expect, type APIRequestContext, type Page } from "@playwright/test";

const letters = "abcdefghijklmnopqrstuvwxyz";

/** A unique, letters-only tag (candidate names may not contain digits). */
export function uniqueTag(): string {
  return Array.from({ length: 8 }, () => letters[Math.floor(Math.random() * letters.length)]).join("");
}

/** Random valid Indian mobile number ending in ``suffix`` (drives simulator scenarios). */
export function phoneEndingIn(suffix = ""): string {
  const body = Array.from({ length: 9 - suffix.length }, () => Math.floor(Math.random() * 10)).join("");
  const phone = `9${body}${suffix}`;
  // Avoid accidentally hitting a scenario suffix when we want normal behaviour.
  return !suffix && /(000|111|222|333|444|555|666|777)$/.test(phone) ? phoneEndingIn(suffix) : phone;
}

export async function createCandidate(request: APIRequestContext, name: string, phone: string) {
  const response = await request.post("/api/candidates", {
    data: { full_name: name, phone, email: `${name.toLowerCase().replace(/\s+/g, ".")}@example.com` },
  });
  expect(response.status(), await response.text()).toBe(201);
  return response.json();
}

export async function searchFor(page: Page, term: string) {
  await page.getByRole("textbox", { name: /Search candidates/ }).fill(term);
}
