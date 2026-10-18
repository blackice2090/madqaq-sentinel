import { describe, expect, it } from "vitest";

import { analysisSize, containRect, mapBox } from "@/lib/overlay";

describe("overlay geometry", () => {
  it("letterboxes a 16:9 video in a 4:3 box", () => {
    expect(containRect(800, 600, 1280, 720)).toEqual({ x: 0, y: 75, w: 800, h: 450 });
  });
  it("pillarboxes a 4:3 video in a 16:9 box", () => {
    const r = containRect(1600, 900, 640, 480);
    expect(r.h).toBe(900);
    expect(r.w).toBe(1200);
    expect(r.x).toBe(200);
  });
  it("maps normalized boxes onto the drawn video rectangle", () => {
    const rect = containRect(800, 600, 1280, 720);
    expect(mapBox([0.5, 0, 1, 1], rect)).toEqual({ x: 400, y: 75, w: 400, h: 450 });
  });
  it("rescales correctly after a container resize", () => {
    const a = mapBox([0.27, 0.1, 0.49, 1], containRect(960, 540, 1280, 720));
    const b = mapBox([0.27, 0.1, 0.49, 1], containRect(1920, 1080, 1280, 720));
    expect(b.x).toBeCloseTo(a.x * 2);
    expect(b.w).toBeCloseTo(a.w * 2);
  });
  it("degenerate sizes produce an empty rect", () => {
    expect(containRect(0, 600, 1280, 720)).toEqual({ x: 0, y: 0, w: 0, h: 0 });
  });
  it("analysis frames are downscaled to the max width, keeping aspect", () => {
    expect(analysisSize(1280, 720, 960)).toEqual({ width: 960, height: 540 });
    expect(analysisSize(640, 480, 960)).toEqual({ width: 640, height: 480 });
  });
});
