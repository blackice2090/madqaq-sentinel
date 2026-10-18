import { describe, expect, it } from "vitest";

import { cameraErrorMessage } from "@/lib/camera";

describe("camera permission failures", () => {
  it("explains denied permission", () => {
    expect(cameraErrorMessage({ name: "NotAllowedError" })).toMatch(/permission was denied/i);
  });
  it("explains a missing or busy camera", () => {
    expect(cameraErrorMessage({ name: "NotFoundError" })).toMatch(/no suitable camera/i);
    expect(cameraErrorMessage({ name: "NotReadableError" })).toMatch(/in use/i);
  });
  it("falls back safely", () => {
    expect(cameraErrorMessage(new Error("weird"))).toBe("The camera could not be started.");
    expect(cameraErrorMessage(undefined)).toBe("The camera could not be started.");
  });
});
