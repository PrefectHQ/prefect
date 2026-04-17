import { getRouteApi } from "@tanstack/react-router";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { TabOptions } from "@/routes/concurrency-limits/concurrency-limit.$id";
import { cn } from "@/utils";

const routeApi = getRouteApi("/concurrency-limits/concurrency-limit/$id");

type TabOptionValues = {
	/** Value of search value in url */
	tabSearchValue: TabOptions;
	/** Display value for the UI */
	displayValue: string;
	/**
	 * When `true`, hide this tab on `xl` screens and above. Used to mirror the
	 * V1 responsive well layout where the details are shown inline on smaller
	 * screens and in a sidebar well on larger screens.
	 */
	hiddenOnDesktop?: boolean;
};

/** Maps url tab option to visual name */
const TAB_OPTIONS: Record<TabOptions, TabOptionValues> = {
	details: {
		tabSearchValue: "details",
		displayValue: "Details",
		hiddenOnDesktop: true,
	},
	"active-task-runs": {
		tabSearchValue: "active-task-runs",
		displayValue: "Active Task Runs",
	},
} as const;

type TaskRunConcurrencyLimitTabNavigationProps = {
	/** Rendered inside the `active-task-runs` tab */
	children: React.ReactNode;
	/** Rendered inside the `details` tab (visible only below `xl`) */
	detailsContent: React.ReactNode;
};

// TODO: Move Tabs for navigation to a generic styled component
export const TaskRunConcurrencyLimitTabNavigation = ({
	children,
	detailsContent,
}: TaskRunConcurrencyLimitTabNavigationProps) => {
	const { tab } = routeApi.useSearch();
	const navigate = routeApi.useNavigate();

	const handleTabChange = (value: string) => {
		void navigate({
			to: "/concurrency-limits/concurrency-limit/$id",
			search: { tab: value as TabOptions },
		});
	};

	return (
		<Tabs value={tab} onValueChange={handleTabChange}>
			<TabsList>
				{Object.values(TAB_OPTIONS).map((option) => (
					<TabsTrigger
						key={option.tabSearchValue}
						value={option.tabSearchValue}
						className={cn(option.hiddenOnDesktop && "xl:hidden")}
					>
						{option.displayValue}
					</TabsTrigger>
				))}
			</TabsList>
			<TabsContent value={TAB_OPTIONS.details.tabSearchValue}>
				{detailsContent}
			</TabsContent>
			<TabsContent value={TAB_OPTIONS["active-task-runs"].tabSearchValue}>
				{children}
			</TabsContent>
		</Tabs>
	);
};
