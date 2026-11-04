import { describe, expect, it, vi } from "vitest";
import { createFakeFlowRun } from "./create-fake-flow-run";

vi.mock("@ngneat/falso", async (importOriginal) => ({
	...(await importOriginal<typeof import("@ngneat/falso")>()),
	randProductAdjective: () => "Ergonomic",
	randAnimal: () => "Gulper Catfish ",
}));

describe("createFakeFlowRun", () => {
	it("trims trailing whitespace from generated names", () => {
		expect(createFakeFlowRun().name).toBe("Ergonomic-Gulper Catfish");
	});
});
