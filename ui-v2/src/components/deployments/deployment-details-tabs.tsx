import { getRouteApi, Link } from "@tanstack/react-router";
import { type JSX, useMemo } from "react";
import type { Deployment } from "@/api/deployments";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DeploymentDetailsTabOptions } from "@/routes/deployments/deployment.$id";

import { DeploymentConfiguration } from "./deployment-configuration";
import { DeploymentDescription } from "./deployment-description";
import { DeploymentDetailsRunsTab } from "./deployment-details-runs-tab";
import { DeploymentDetailsUpcomingTab } from "./deployment-details-upcoming-tab";
import { DeploymentParametersTable } from "./deployment-parameters-table";

const routeApi = getRouteApi("/deployments/deployment/$id");

type TabOption = {
	value: DeploymentDetailsTabOptions;
	LinkComponent: () => JSX.Element;
	ViewComponent: () => JSX.Element;
};

type DeploymentDetailsTabsProps = {
	deployment: Deployment;
};
export const DeploymentDetailsTabs = ({
	deployment,
}: DeploymentDetailsTabsProps) => {
	const { tab } = routeApi.useSearch();

	const tabOptions = useBuildTabOptions(deployment);

	return (
		<Tabs defaultValue={tabOptions[0].value} value={tab}>
			<TabsList>
				{tabOptions.map(({ value, LinkComponent }) => (
					<LinkComponent key={value} />
				))}
			</TabsList>
			{tabOptions.map(({ value, ViewComponent }) => (
				<ViewComponent key={value} />
			))}
		</Tabs>
	);
};

function useBuildTabOptions(deployment: Deployment) {
	return useMemo(
		() =>
			[
				{
					value: "Runs",
					LinkComponent: () => (
						<Link to="." search={{ tab: "Runs" }}>
							<TabsTrigger value="Runs">Runs</TabsTrigger>
						</Link>
					),
					ViewComponent: () => (
						<TabsContent value="Runs">
							<DeploymentDetailsRunsTab deployment={deployment} />
						</TabsContent>
					),
				},
				{
					value: "Upcoming",
					LinkComponent: () => (
						<Link to="." search={{ tab: "Upcoming" }}>
							<TabsTrigger value="Upcoming">Upcoming</TabsTrigger>
						</Link>
					),
					ViewComponent: () => (
						<TabsContent value="Upcoming">
							<DeploymentDetailsUpcomingTab deployment={deployment} />
						</TabsContent>
					),
				},
				{
					value: "Parameters",
					LinkComponent: () => (
						<Link to="." search={{ tab: "Parameters" }}>
							<TabsTrigger value="Parameters">Parameters</TabsTrigger>
						</Link>
					),
					ViewComponent: () => (
						<TabsContent value="Parameters">
							<DeploymentParametersTable deployment={deployment} />
						</TabsContent>
					),
				},
				{
					value: "Configuration",
					LinkComponent: () => (
						<Link to="." search={{ tab: "Configuration" }}>
							<TabsTrigger value="Configuration">Configuration</TabsTrigger>
						</Link>
					),
					ViewComponent: () => (
						<TabsContent value="Configuration">
							<DeploymentConfiguration deployment={deployment} />
						</TabsContent>
					),
				},
				{
					value: "Description",
					LinkComponent: () => (
						<Link to="." search={{ tab: "Description" }}>
							<TabsTrigger value="Description">Description</TabsTrigger>
						</Link>
					),
					ViewComponent: () => (
						<TabsContent value="Description">
							<DeploymentDescription deployment={deployment} />
						</TabsContent>
					),
				},
			] as const satisfies Array<TabOption>,
		[deployment],
	);
}
