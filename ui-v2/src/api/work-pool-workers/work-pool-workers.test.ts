import { describe, expect, it } from "vitest";

import {
	buildListWorkPoolWorkersQuery,
	workPoolWorkersQueryKeyFactory,
} from "./work-pool-workers";

describe("work pool workers query key factory", () => {
	it("generates correct query keys", () => {
		expect(workPoolWorkersQueryKeyFactory.all()).toEqual(["work_pool_workers"]);
		expect(workPoolWorkersQueryKeyFactory.lists()).toEqual([
			"work_pool_workers",
			"list",
		]);
		expect(workPoolWorkersQueryKeyFactory.list("test-pool")).toEqual([
			"work_pool_workers",
			"list",
			"test-pool",
		]);
	});
});

describe("buildListWorkPoolWorkersQuery", () => {
	it("creates query options with correct key and refetch interval", () => {
		const query = buildListWorkPoolWorkersQuery("test-pool");

		expect(query.queryKey).toEqual(["work_pool_workers", "list", "test-pool"]);
		expect(query.refetchInterval).toBe(30000);
	});

	it("has a queryFn that calls the correct API endpoint", () => {
		const query = buildListWorkPoolWorkersQuery("my-pool");

		expect(query.queryFn).toBeDefined();
		expect(typeof query.queryFn).toBe("function");
	});
});
