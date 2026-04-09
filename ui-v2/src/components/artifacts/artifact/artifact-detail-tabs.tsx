import { getRouteApi, Link } from "@tanstack/react-router";
import { type JSX, type ReactNode, useMemo } from "react";
import type { ArtifactWithFlowRunAndTaskRun } from "@/api/artifacts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ArtifactDetailTabOptions } from "@/routes/artifacts/artifact.$id";
import { cn } from "@/utils";

import { ArtifactDataDisplay } from "./artifact-raw-data-display";

const routeApi = getRouteApi("/artifacts/artifact/$id");

type TabOption = {
	value: ArtifactDetailTabOptions;
	hiddenOnDesktop?: boolean;
	LinkComponent: (props: { className?: string }) => JSX.Element;
	ViewComponent: () => JSX.Element;
};

type ArtifactDetailTabsProps = {
	artifact: ArtifactWithFlowRunAndTaskRun;
	artifactContent: ReactNode;
	detailsContent: ReactNode;
};

export const ArtifactDetailTabs = ({
	artifact,
	artifactContent,
	detailsContent,
}: ArtifactDetailTabsProps) => {
	const { tab } = routeApi.useSearch();

	const tabOptions = useBuildTabOptions(
		artifact,
		artifactContent,
		detailsContent,
	);

	return (
		<Tabs defaultValue="Artifact" value={tab}>
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
	artifact: ArtifactWithFlowRunAndTaskRun,
	artifactContent: ReactNode,
	detailsContent: ReactNode,
): Array<TabOption> {
	return useMemo(() => {
		const tabs: Array<TabOption> = [];

		tabs.push({
			value: "Artifact",
			LinkComponent: ({ className }) => (
				<Link to="." search={{ tab: "Artifact" }}>
					<TabsTrigger value="Artifact" className={className}>
						Artifact
					</TabsTrigger>
				</Link>
			),
			ViewComponent: () => (
				<TabsContent value="Artifact">
					{artifactContent}
					<ArtifactDataDisplay artifact={artifact} />
				</TabsContent>
			),
		});

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

		tabs.push({
			value: "Raw",
			LinkComponent: ({ className }) => (
				<Link to="." search={{ tab: "Raw" }}>
					<TabsTrigger value="Raw" className={className}>
						Raw
					</TabsTrigger>
				</Link>
			),
			ViewComponent: () => (
				<TabsContent value="Raw">
					<ArtifactRawData artifact={artifact} />
				</TabsContent>
			),
		});

		return tabs;
	}, [artifact, artifactContent, detailsContent]);
}

function ArtifactRawData({
	artifact,
}: {
	artifact: ArtifactWithFlowRunAndTaskRun;
}) {
	return (
		<pre className="whitespace-pre-wrap break-words rounded-md border bg-muted p-4 text-sm">
			{typeof artifact.data === "string"
				? artifact.data
				: JSON.stringify(artifact.data, null, 2)}
		</pre>
	);
}
