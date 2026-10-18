import { describe, expect, it } from "vitest";

import { detectionsFresh, nextBackoff, statusView } from "@/lib/connection";

import { sampleState } from "./fixtures";

describe("connection / stale handling", () => {
  it("connected with state is live", () => {
    expect(statusView("connected", "active", sampleState())).toMatchObject({
      backendLabel: "BACKEND CONNECTED", cameraLabel: "CAMERA ACTIVE", stale: false, staleReason: null,
    });
  });
  it("a disconnect marks the last state stale and unavailable", () => {
    const v = statusView("disconnected", "active", sampleState());
    expect(v.backendLabel).toBe("DISCONNECTED");
    expect(v.stale).toBe(true);
    expect(v.staleReason).toMatch(/stale/i);
  });
  it("connecting is not live either", () => {
    expect(statusView("connecting", "off", null)).toMatchObject({ backendLabel: "CONNECTING", cameraLabel: "CAMERA OFF", stale: true });
  });
  it("camera labels", () => {
    expect(statusView("connected", "error", sampleState()).cameraLabel).toBe("CAMERA OFF");
    expect(statusView("connected", "starting", sampleState()).cameraLabel).toBe("CAMERA OFF");
  });
  it("detections are only drawn while live and recent", () => {
    expect(detectionsFresh("connected", "active", 1000, 1500, 1500)).toBe(true);
    expect(detectionsFresh("connected", "active", 1000, 3000, 1500)).toBe(false);
    expect(detectionsFresh("disconnected", "active", 1000, 1001, 1500)).toBe(false);
    expect(detectionsFresh("connected", "off", 1000, 1001, 1500)).toBe(false);
    expect(detectionsFresh("connected", "active", null, 1001, 1500)).toBe(false);
  });
  it("reconnect backoff doubles up to a cap", () => {
    expect(nextBackoff(1000, 8000)).toBe(2000);
    expect(nextBackoff(8000, 8000)).toBe(8000);
  });
});
