import { getRouteApi } from "@tanstack/react-router";
import type { JSX } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TabOptions } from "@/routes/concurrency-limits";

const routeApi = getRouteApi("/concurrency-limits/");

type TabOptionValues = {
	/** Value of search value in url */
	tabSearchValue: TabOptions;
	/** Display value for the UI */
	displayValue: string;
};

/** Maps url tab option to visual name */
const TAB_OPTIONS: Record<TabOptions, TabOptionValues> = {
	global: {
		tabSearchValue: "global",
		displayValue: "Global",
	},
	"task-run": {
		tabSearchValue: "task-run",
		displayValue: "Task Run",
	},
} as const;

type ConcurrencyLimitsTabsProps = {
	globalView: React.ReactNode;
	taskRunView: React.ReactNode;
};

// TODO: Move Tabs for navigation to a generic styled component

export const ConcurrencyLimitsTabs = ({
	globalView,
	taskRunView,
}: ConcurrencyLimitsTabsProps): JSX.Element => {
	const { tab } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	return (
		<Tabs defaultValue="Global" value={tab}>
			<TabsList>
				<TabsTrigger
					value={TAB_OPTIONS.global.tabSearchValue}
					onClick={() => {
						void navigate({
							to: "/concurrency-limits",
							search: {
								tab: TAB_OPTIONS.global.tabSearchValue,
							},
						});
					}}
				>
					{TAB_OPTIONS.global.displayValue}
				</TabsTrigger>
				<TabsTrigger
					value={TAB_OPTIONS["task-run"].tabSearchValue}
					onClick={() => {
						void navigate({
							to: "/concurrency-limits",
							search: {
								tab: TAB_OPTIONS["task-run"].tabSearchValue,
							},
						});
					}}
				>
					{TAB_OPTIONS["task-run"].displayValue}
				</TabsTrigger>
			</TabsList>
			<TabsContent value={TAB_OPTIONS.global.tabSearchValue}>
				{globalView}
			</TabsContent>
			<TabsContent value={TAB_OPTIONS["task-run"].tabSearchValue}>
				{taskRunView}
			</TabsContent>
		</Tabs>
	);
};
