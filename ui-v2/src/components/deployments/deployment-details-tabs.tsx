import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { DeploymentDetailsTabOptions } from "@/routes/deployments/deployment.$id";
import { Link, getRouteApi } from "@tanstack/react-router";
import { type JSX } from "react";

const routeApi = getRouteApi("/deployments/deployment/$id");

type TabOption = {
	value: DeploymentDetailsTabOptions;
	LinkComponent: () => JSX.Element;
	ViewComponent: () => JSX.Element;
};

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
				<div className="border border-red-400">{"<ParametersView />"}</div>
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
				<div className="border border-red-400">{"<ConfigurationView />"}</div>
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
				<div className="border border-red-400">{"<DescriptionView />"}</div>
			</TabsContent>
		),
	},
] as const satisfies Array<TabOption>;

export const DeploymentDetailsTabs = (): JSX.Element => {
	const { tab } = routeApi.useSearch();

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
