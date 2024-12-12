import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TabOptions } from "@/routes/concurrency-limits";
import { getRouteApi } from "@tanstack/react-router";
import type { JSX } from "react";

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

type Props = {
	globalView: React.ReactNode;
	taskRunView: React.ReactNode;
};

// TODO: Move Tabs for navigation to a generic styled component

export const ConcurrencyTabs = ({
	globalView,
	taskRunView,
}: Props): JSX.Element => {
	const { tab } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	return (
		<Tabs className="flex flex-col gap-4" defaultValue="Global" value={tab}>
			<TabsList className="grid w-full grid-cols-2">
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
