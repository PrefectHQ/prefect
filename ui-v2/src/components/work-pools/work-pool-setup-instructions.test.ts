import { describe, expect, it } from "vitest";
import {
	categorizeWorkPoolType,
	getWorkPoolDocsUrl,
	getWorkPoolSetupInstructions,
} from "./work-pool-setup-instructions";

describe("categorizeWorkPoolType", () => {
	it("returns 'push' for types ending with :push", () => {
		expect(categorizeWorkPoolType("ecs:push")).toBe("push");
		expect(categorizeWorkPoolType("cloud-run:push")).toBe("push");
		expect(categorizeWorkPoolType("azure-container-instance:push")).toBe(
			"push",
		);
	});

	it("returns 'managed' for types ending with :managed", () => {
		expect(categorizeWorkPoolType("prefect:managed")).toBe("managed");
	});

	it("returns 'kubernetes' for the kubernetes type", () => {
		expect(categorizeWorkPoolType("kubernetes")).toBe("kubernetes");
	});

	it("returns 'worker' for standard worker types", () => {
		expect(categorizeWorkPoolType("process")).toBe("worker");
		expect(categorizeWorkPoolType("docker")).toBe("worker");
		expect(categorizeWorkPoolType("ecs")).toBe("worker");
	});
});

describe("getWorkPoolDocsUrl", () => {
	it("returns kubernetes docs for kubernetes type", () => {
		expect(getWorkPoolDocsUrl("kubernetes")).toContain("kubernetes");
	});

	it("returns serverless docs for push pool types", () => {
		expect(getWorkPoolDocsUrl("ecs:push")).toContain("serverless");
		expect(getWorkPoolDocsUrl("cloud-run:push")).toContain("serverless");
	});

	it("returns default docs url for unknown types", () => {
		expect(getWorkPoolDocsUrl("unknown-type")).toContain("work-pools");
	});
});

describe("getWorkPoolSetupInstructions", () => {
	it("returns managed pool instructions with no command", () => {
		const result = getWorkPoolSetupInstructions("my-pool", "prefect:managed");
		expect(result.title).toBe("Your work pool is ready!");
		expect(result.command).toBeUndefined();
	});

	it("returns push pool instructions with no command", () => {
		const result = getWorkPoolSetupInstructions("my-pool", "ecs:push");
		expect(result.title).toBe("Your work pool is almost ready!");
		expect(result.command).toBeUndefined();
		expect(result.description).toContain("push");
	});

	it("returns kubernetes instructions with helm command", () => {
		const result = getWorkPoolSetupInstructions("my-pool", "kubernetes");
		expect(result.command).toContain("helm install");
		expect(result.command).toContain("my-pool");
	});

	it("returns worker start command for standard types", () => {
		const result = getWorkPoolSetupInstructions("my-pool", "process");
		expect(result.command).toBe('prefect worker start --pool "my-pool"');
	});

	it("includes pool name in worker command", () => {
		const result = getWorkPoolSetupInstructions("my special pool", "docker");
		expect(result.command).toContain("my special pool");
	});
});
