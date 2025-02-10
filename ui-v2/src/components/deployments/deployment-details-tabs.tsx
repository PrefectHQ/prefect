import { Deployment } from "@/api/deployments";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DeploymentDetailsTabOptions } from "@/routes/deployments/deployment.$id";
import { Link, getRouteApi } from "@tanstack/react-router";
import { type JSX } from "react";

import { DeploymentConfiguration } from "./deployment-configuration";
import { DeploymentDescription } from "./deployment-description";
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
}: DeploymentDetailsTabsProps): JSX.Element => {
	const { tab } = routeApi.useSearch();

	const TAB_OPTIONS = [
		{
			value: "Runs",
			LinkComponent: () => (
				<Link to="." search={{ tab: "Runs" }}>
					<TabsTrigger value="Runs">Runs</TabsTrigger>
				</Link>
			),
			ViewComponent: () => (
				<TabsContent value="Runs">
					<div className="border border-red-400">{"<RunsView />"}</div>
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
					<div className="border border-red-400">{"<UpcomingView />"}</div>
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
	] as const satisfies Array<TabOption>;

	return (
		<Tabs defaultValue={TAB_OPTIONS[0].value} value={tab}>
			<TabsList>
				{TAB_OPTIONS.map(({ value, LinkComponent }) => (
					<LinkComponent key={value} />
				))}
			</TabsList>
			{TAB_OPTIONS.map(({ value, ViewComponent }) => (
				<ViewComponent key={value} />
			))}
		</Tabs>
	);
};
