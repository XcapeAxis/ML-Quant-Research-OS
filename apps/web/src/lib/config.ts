export function setNestedValue(
  source: Record<string, unknown>,
  path: string[],
  value: unknown,
): Record<string, unknown> {
  const next = structuredClone(source);
  let cursor: Record<string, unknown> = next;
  path.slice(0, -1).forEach((key) => {
    if (typeof cursor[key] !== "object" || cursor[key] === null || Array.isArray(cursor[key])) {
      cursor[key] = {};
    }
    cursor = cursor[key] as Record<string, unknown>;
  });
  cursor[path[path.length - 1]] = value;
  return next;
}

export function safeParseJson(text: string): Record<string, unknown> {
  const parsed = JSON.parse(text) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Config JSON must be an object.");
  }
  return parsed as Record<string, unknown>;
}

export function metricNumber(row: Record<string, unknown> | undefined, key: string): number | null {
  if (!row) {
    return null;
  }
  const value = row[key];
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}
