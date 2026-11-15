import { describe, expect, it } from "vitest";
import { messages } from "./messages";

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(",");

describe("i18n messages", () => {
  const keys = Object.keys(messages.es) as (keyof typeof messages.es)[];

  it("has the same keys in both languages", () => {
    expect(Object.keys(messages.en).sort()).toEqual([...keys].sort());
  });

  it("fills no message with an empty string", () => {
    for (const key of keys) {
      expect(messages.es[key].trim(), `es.${key}`).not.toBe("");
      expect(messages.en[key].trim(), `en.${key}`).not.toBe("");
    }
  });

  it("uses the same {placeholders} in both languages", () => {
    for (const key of keys) expect(placeholders(messages.en[key]), key).toBe(placeholders(messages.es[key]));
  });
});
