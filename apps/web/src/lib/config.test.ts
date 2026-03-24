import { describe, expect, test } from "vitest";

import { metricNumber, safeParseJson, setNestedValue } from "./config";

describe("config helpers", () => {
  test("updates nested config keys immutably", () => {
    const source = { risk_overlay: { enabled: false } };
    const next = setNestedValue(source, ["risk_overlay", "enabled"], true);
    expect(source.risk_overlay.enabled).toBe(false);
    expect((next.risk_overlay as { enabled: boolean }).enabled).toBe(true);
  });

  test("parses valid JSON objects only", () => {
    expect(safeParseJson('{"cash": 1000}')).toEqual({ cash: 1000 });
    expect(() => safeParseJson("[]")).toThrow();
  });

  test("extracts numeric metrics safely", () => {
    expect(metricNumber({ total_return: "1.23" }, "total_return")).toBe(1.23);
    expect(metricNumber(undefined, "total_return")).toBeNull();
  });
});
