import { describe, it, expect } from "vitest";
import { MockApiAdapter } from "./mockAdapter";
import { SessionResponseSchema, SimulateResponseSchema } from "../schemas";
import type { UploadFormValues } from "../schemas";

const mockForm: UploadFormValues = {
  image: new File([""], "test.jpg", { type: "image/jpeg" }),
  event_type: "business_meeting",
  event_type_is_custom: false,
  event_datetime: "2026-05-07T10:00",
  city_code: "KR-SEOUL",
  is_indoor: false,
  allow_live_research: true,
};

describe("MockApiAdapter", () => {
  const adapter = new MockApiAdapter();

  it("createSession returns a valid SessionResponse", async () => {
    const result = await adapter.createSession(mockForm);
    expect(() => SessionResponseSchema.parse(result)).not.toThrow();
  });

  it("createSession returns 17 checks", async () => {
    const result = await adapter.createSession(mockForm);
    expect(result.recommendation.checks).toHaveLength(17);
  });

  it("createSession score method is group_weighted_with_blocker_cap", async () => {
    const result = await adapter.createSession(mockForm);
    expect(result.recommendation.score.method).toBe("group_weighted_with_blocker_cap");
  });

  it("simulate returns a valid SimulateResponse", async () => {
    const result = await adapter.simulate("mock-session-001", ["sg_1"]);
    expect(() => SimulateResponseSchema.parse(result)).not.toThrow();
  });

  it("simulate with no suggestions returns original score", async () => {
    const result = await adapter.simulate("mock-session-001", []);
    expect(result.simulated_overall).toBe(result.original_overall);
    expect(result.delta).toBe(0);
  });

  it("simulate with suggestions increases score", async () => {
    const result = await adapter.simulate("mock-session-001", ["sg_1", "sg_2", "sg_3"]);
    expect(result.simulated_overall).toBeGreaterThan(result.original_overall);
    expect(result.delta).toBeGreaterThan(0);
  });

  it("simulate flips correct check IDs to pass", async () => {
    const result = await adapter.simulate("mock-session-001", ["sg_1"]);
    expect(result.checks_flipped.to_pass).toContain("A1");
    expect(result.checks_flipped.to_pass).toContain("B2");
  });
});
