import { describe, it, expect } from "vitest";
import {
  JOB_STATUSES,
  JOB_TYPES,
  WORK_MODES,
  SOURCES,
  GOAL_TYPES,
  STATUS_LABELS,
  TYPE_LABELS,
  MODE_LABELS,
  SOURCE_LABELS,
} from "@/lib/types";

describe("type constants", () => {
  it("has 9 job statuses", () => {
    expect(JOB_STATUSES).toHaveLength(9);
  });

  it("has 4 job types", () => {
    expect(JOB_TYPES).toHaveLength(4);
  });

  it("has 3 work modes", () => {
    expect(WORK_MODES).toHaveLength(3);
  });

  it("has 5 sources", () => {
    expect(SOURCES).toHaveLength(5);
  });

  it("has 2 goal types", () => {
    expect(GOAL_TYPES).toHaveLength(2);
    expect(GOAL_TYPES).toContain("weekly");
    expect(GOAL_TYPES).toContain("monthly");
  });
});

describe("label maps", () => {
  it("has a label for every status", () => {
    for (const status of JOB_STATUSES) {
      expect(STATUS_LABELS[status]).toBeTruthy();
    }
  });

  it("has a label for every job type", () => {
    for (const type of JOB_TYPES) {
      expect(TYPE_LABELS[type]).toBeTruthy();
    }
  });

  it("has a label for every work mode", () => {
    for (const mode of WORK_MODES) {
      expect(MODE_LABELS[mode]).toBeTruthy();
    }
  });

  it("has a label for every source", () => {
    for (const source of SOURCES) {
      expect(SOURCE_LABELS[source]).toBeTruthy();
    }
  });

  it("labels are human readable (not raw enum values)", () => {
    expect(STATUS_LABELS.phone_screen).toBe("Phone Screen");
    expect(TYPE_LABELS.full_time).toBe("Full Time");
    expect(MODE_LABELS.onsite).toBe("On-site");
    expect(SOURCE_LABELS.company_site).toBe("Company Site");
  });
});
