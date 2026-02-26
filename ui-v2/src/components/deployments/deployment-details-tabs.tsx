import { getRouteApi, Link } from "@tanstack/react-router";
import { type JSX, type ReactNode, useMemo } from "react";
import type { Deployment } from "@/api/deployments";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DeploymentDetailsTabOptions } from "@/routes/deployments/deployment.$id";
import { cn } from "@/utils";

import { DeploymentConfiguration } from "./deployment-configuration";
import { DeploymentDescription } from "./deployment-description";
import { DeploymentDetailsRunsTab } from "./deployment-details-runs-tab";
import { DeploymentDetailsUpcomingTab } from "./deployment-details-upcoming-tab";
import { DeploymentParametersTable } from "./deployment-parameters-table";

const routeApi = getRouteApi("/deployments/deployment/$id");

type TabOption = {
	value: DeploymentDetailsTabOptions;
	hiddenOnDesktop?: boolean;
	LinkComponent: (props: { className?: string }) => JSX.Element;
	ViewComponent: () => JSX.Element;
};

type DeploymentDetailsTabsProps = {
	deployment: Deployment;
	detailsContent?: ReactNode;
};
export const DeploymentDetailsTabs = ({
	deployment,
	detailsContent,
}: DeploymentDetailsTabsProps) => {
	const { tab } = routeApi.useSearch();

	const tabOptions = useBuildTabOptions(deployment, detailsContent);

	return (
		<Tabs defaultValue="Runs" value={tab}>
			<TabsList>
				{tabOptions.map(({ value, hiddenOnDesktop, LinkComponent }) => (
					<LinkComponent
						key={value}
						className={cn(hiddenOnDesktop && "lg:hidden")}
					/>
				))}
			</TabsList>
			{tabOptions.map(({ value, ViewComponent }) => (
				<ViewComponent key={value} />
			))}
		</Tabs>
	);
};

function useBuildTabOptions(
	deployment: Deployment,
	detailsContent?: ReactNode,
): Array<TabOption> {
	return useMemo(() => {
		const tabs: Array<TabOption> = [];

		if (detailsContent) {
			tabs.push({
				value: "Details",
				hiddenOnDesktop: true,
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Details" }}>
						<TabsTrigger value="Details" className={className}>
							Details
						</TabsTrigger>
					</Link>
				),
				ViewComponent: () => (
					<TabsContent value="Details">{detailsContent}</TabsContent>
				),
			});
		}

		tabs.push(
			{
				value: "Runs",
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Runs" }}>
						<TabsTrigger value="Runs" className={className}>
							Runs
						</TabsTrigger>
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
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Upcoming" }}>
						<TabsTrigger value="Upcoming" className={className}>
							Upcoming
						</TabsTrigger>
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
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Parameters" }}>
						<TabsTrigger value="Parameters" className={className}>
							Parameters
						</TabsTrigger>
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
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Configuration" }}>
						<TabsTrigger value="Configuration" className={className}>
							Configuration
						</TabsTrigger>
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
				LinkComponent: ({ className }) => (
					<Link to="." search={{ tab: "Description" }}>
						<TabsTrigger value="Description" className={className}>
							Description
						</TabsTrigger>
					</Link>
				),
				ViewComponent: () => (
					<TabsContent value="Description">
						<DeploymentDescription deployment={deployment} />
					</TabsContent>
				),
			},
		);

		return tabs;
	}, [deployment, detailsContent]);
}
