import { getRouteApi } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TabOptions } from "@/routes/concurrency-limits/concurrency-limit.$id";

const routeApi = getRouteApi("/concurrency-limits/concurrency-limit/$id");

type TabOptionValues = {
	/** Value of search value in url */
	tabSearchValue: TabOptions;
	/** Display value for the UI */
	displayValue: string;
};

/** Maps url tab option to visual name */
const TAB_OPTIONS: Record<TabOptions, TabOptionValues> = {
	"active-task-runs": {
		tabSearchValue: "active-task-runs",
		displayValue: "Active Task Runs",
	},
} as const;

type TaskRunConcurrencyLimitTabNavigationProps = {
	/** Should add ActiveTaskRun component */
	children: React.ReactNode;
};

// TODO: Move Tabs for navigation to a generic styled component
export const TaskRunConcurrencyLimitTabNavigation = ({
	children,
}: TaskRunConcurrencyLimitTabNavigationProps) => {
	const { tab } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	return (
		<Tabs defaultValue="Global" value={tab}>
			<TabsList>
				<TabsTrigger
					value={TAB_OPTIONS["active-task-runs"].tabSearchValue}
					onClick={() => {
						void navigate({
							to: "/concurrency-limits/concurrency-limit/$id",
							search: {
								tab: TAB_OPTIONS["active-task-runs"].tabSearchValue,
							},
						});
					}}
				>
					{TAB_OPTIONS["active-task-runs"].displayValue}
				</TabsTrigger>
			</TabsList>
			<TabsContent value={TAB_OPTIONS["active-task-runs"].tabSearchValue}>
				{children}
			</TabsContent>
		</Tabs>
	);
};
