import { describe, expect, it } from "vitest";
import { candidatesPath } from "./api/endpoints";
import { firstName, formatDate, formatTime, localInputToIso, plural, toLocalInputValue } from "./format";

describe("format helpers", () => {
  it("formats dates and times like the design (DD-MM-YYYY, 9:47 AM)", () => {
    const morning = new Date(2026, 9, 8, 9, 47).toISOString();
    const evening = new Date(2026, 9, 25, 22, 5).toISOString();
    expect(formatDate(morning)).toBe("08-10-2026");
    expect(formatTime(morning)).toBe("9:47 AM");
    expect(formatTime(evening)).toBe("10:05 PM");
    expect(formatTime(new Date(2026, 0, 1, 0, 3).toISOString())).toBe("12:03 AM");
  });

  it("pluralises counts", () => {
    expect(plural(1, "candidate")).toBe("1 candidate");
    expect(plural(5, "candidate")).toBe("5 candidates");
    expect(plural(2, "Recipient")).toBe("2 Recipients");
  });

  it("round-trips datetime-local values through ISO", () => {
    const date = new Date(2026, 10, 2, 15, 30);
    const value = toLocalInputValue(date);
    expect(value).toBe("2026-11-02T15:30");
    expect(localInputToIso(value)).toBe(date.toISOString());
    expect(localInputToIso("")).toBeNull();
    expect(localInputToIso("not-a-date")).toBeNull();
  });

  it("extracts a first name", () => {
    expect(firstName("Krishna Khandelwal")).toBe("Krishna");
  });
});

describe("candidatesPath", () => {
  it("only includes meaningful query params", () => {
    expect(candidatesPath({ page: 1, pageSize: 10 })).toBe("/candidates?page_size=10");
    expect(candidatesPath({ search: "  priya ", page: 3, pageSize: 25, ordering: "-last_message_at", status: ["failed", "none"] })).toBe(
      "/candidates?search=priya&page=3&page_size=25&ordering=-last_message_at&status=failed%2Cnone",
    );
  });
});
