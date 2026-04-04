import { describe, expect, it } from "vitest";
import {
	buildPaginationBody,
	hasActiveDeploymentFilters,
} from "@/routes/deployments/utils";

describe("buildPaginationBody", () => {
	it("builds the default deployments pagination payload", () => {
		expect(buildPaginationBody()).toEqual({
			page: 1,
			limit: 10,
			sort: "NAME_ASC",
			deployments: {
				operator: "and_",
				flow_or_deployment_name: { like_: "" },
				tags: { operator: "and_", all_: [] },
			},
		});
	});

	it("builds a payload using search filters", () => {
		expect(
			buildPaginationBody({
				page: 3,
				limit: 25,
				sort: "UPDATED_DESC",
				flowOrDeploymentName: "worker",
				tags: ["prod"],
			}),
		).toEqual({
			page: 3,
			limit: 25,
			sort: "UPDATED_DESC",
			deployments: {
				operator: "and_",
				flow_or_deployment_name: { like_: "worker" },
				tags: { operator: "and_", all_: ["prod"] },
			},
		});
	});
});

describe("hasActiveDeploymentFilters", () => {
	it("returns false when no filters are set", () => {
		expect(hasActiveDeploymentFilters()).toBe(false);
		expect(hasActiveDeploymentFilters({})).toBe(false);
		expect(hasActiveDeploymentFilters({ flowOrDeploymentName: "", tags: [] })).toBe(
			false,
		);
	});

	it("returns true when name or tags filter is set", () => {
		expect(hasActiveDeploymentFilters({ flowOrDeploymentName: "etl" })).toBe(true);
		expect(hasActiveDeploymentFilters({ tags: ["critical"] })).toBe(true);
	});
});
