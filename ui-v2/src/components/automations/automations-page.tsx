import { buildListAutomationsQuery } from "@/api/automations";
import { useSuspenseQuery } from "@tanstack/react-query";
import { AutomationDetails } from "./automation-details";
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
				<ul className="flex flex-col gap-2">
					{data.map((automation) => (
						<li
							key={automation.id}
							aria-label={`automation item ${automation.name}`}
						>
							<AutomationDetails data={automation} displayType="item" />
						</li>
					))}
				</ul>
			)}
		</div>
	);
};
