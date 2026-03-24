import { describe, expect, test } from "vitest";

import { formatDateTime, formatFileSize, formatLatency, translateExecutionMode, translatePipeline, translateStatus } from "./display";

describe("display helpers", () => {
  test("translate status and pipeline values", () => {
    expect(translateStatus("running")).toBe("运行中");
    expect(translatePipeline("full_analysis_pack")).toBe("完整分析包");
    expect(translateExecutionMode("serial")).toBe("串行");
  });

  test("format date time for zh-CN output", () => {
    const value = formatDateTime("2026-03-17T02:21:55.415666");
    expect(value).toContain("2026");
    expect(value).toContain("3/17");
    expect(value).toContain("02:21");
  });

  test("format file size and latency", () => {
    expect(formatFileSize(1536)).toBe("1.5 KB");
    expect(formatLatency(18.4)).toBe("18 ms");
  });
});
