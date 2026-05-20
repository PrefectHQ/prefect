import { describe, expect, it } from "vitest";
import type { StateType } from "@/graphs";
import { getStateTypeShade, stateTypeShades } from "./consts";

const ALL_STATE_TYPES: StateType[] = [
	"COMPLETED",
	"RUNNING",
	"SCHEDULED",
	"PENDING",
	"FAILED",
	"CANCELLED",
	"CANCELLING",
	"CRASHED",
	"PAUSED",
];

describe("getStateTypeShade", () => {
	it("returns the light-mode shade for each state type", () => {
		for (const state of ALL_STATE_TYPES) {
			const shade = getStateTypeShade(state, "light");
			expect(shade).toBeGreaterThanOrEqual(600);
			expect(shade).toBeLessThanOrEqual(800);
		}
	});

	it("returns darker (lower-numbered) shades in dark mode", () => {
		for (const state of ALL_STATE_TYPES) {
			const darkShade = getStateTypeShade(state, "dark");
			const lightShade = getStateTypeShade(state, "light");
			expect(darkShade).toBeLessThan(lightShade);
		}
	});

	it("returns shade 300 for all state types in dark mode", () => {
		for (const state of ALL_STATE_TYPES) {
			expect(getStateTypeShade(state, "dark")).toBe(300);
		}
	});

	it("matches the deprecated stateTypeShades map for light mode", () => {
		for (const state of ALL_STATE_TYPES) {
			expect(getStateTypeShade(state, "light")).toBe(stateTypeShades[state]);
		}
	});

	it("preserves existing light-mode shade assignments", () => {
		expect(getStateTypeShade("COMPLETED", "light")).toBe(600);
		expect(getStateTypeShade("RUNNING", "light")).toBe(700);
		expect(getStateTypeShade("SCHEDULED", "light")).toBe(700);
		expect(getStateTypeShade("PENDING", "light")).toBe(800);
		expect(getStateTypeShade("FAILED", "light")).toBe(700);
		expect(getStateTypeShade("CANCELLED", "light")).toBe(600);
		expect(getStateTypeShade("CANCELLING", "light")).toBe(600);
		expect(getStateTypeShade("CRASHED", "light")).toBe(600);
		expect(getStateTypeShade("PAUSED", "light")).toBe(800);
	});
});
