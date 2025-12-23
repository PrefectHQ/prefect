type FlowRunDetailsTabOptions =
	| "Logs"
	| "TaskRuns"
	| "SubflowRuns"
	| "Artifacts"
	| "Details"
	| "Parameters"
	| "JobVariables";

type FlowRunDetailsPageProps = {
	id: string;
	tab: FlowRunDetailsTabOptions;
	onTabChange: (tab: FlowRunDetailsTabOptions) => void;
};

export const FlowRunDetailsPage = ({
	id,
	tab,
	onTabChange,
}: FlowRunDetailsPageProps) => {
	void onTabChange;
	return (
		<div>
			Flow Run Details Page - ID: {id}, Tab: {tab}
		</div>
	);
};
