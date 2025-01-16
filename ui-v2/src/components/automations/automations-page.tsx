import { buildListAutomationsQuery } from "@/api/automations";
import { useSuspenseQuery } from "@tanstack/react-query";
import { AutomationsEmptyState } from "./automations-empty-state";
import { AutomationsHeader } from "./automations-header";

export const AutomationsPage = () => {
	const { data } = useSuspenseQuery(buildListAutomationsQuery());

	return (
		<div className="flex flex-col gap-4">
			<AutomationsHeader />
			{data.length === 0 ? (
				<AutomationsEmptyState />
			) : (
				<div>TODO: AUTOMATIONS_LIST</div>
			)}
		</div>
	);
};
