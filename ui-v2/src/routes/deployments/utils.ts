import type { components } from "@/api/prefect";
import type { DeploymentsPaginationFilter } from "@/api/deployments";

export type DeploymentsSearch = {
	page?: number;
	limit?: number;
	sort?: components["schemas"]["DeploymentSort"];
	flowOrDeploymentName?: string;
	tags?: Array<string>;
};

export const buildPaginationBody = (
	search?: DeploymentsSearch,
): DeploymentsPaginationFilter => ({
	page: search?.page ?? 1,
	limit: search?.limit ?? 10,
	sort: search?.sort ?? "NAME_ASC",
	deployments: {
		operator: "and_",
		flow_or_deployment_name: { like_: search?.flowOrDeploymentName ?? "" },
		tags: { operator: "and_", all_: search?.tags ?? [] },
	},
});

export const hasActiveDeploymentFilters = (search?: DeploymentsSearch) =>
	Boolean(search?.flowOrDeploymentName) || (search?.tags?.length ?? 0) > 0;
