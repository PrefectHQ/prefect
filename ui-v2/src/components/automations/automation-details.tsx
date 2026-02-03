import type { Automation } from "@/api/automations";
import { useGetAutomationActionResources } from "@/api/automations/use-get-automation-action-resources";
import { ActionDetails } from "@/components/automations/action-details";
import { TriggerDetails } from "@/components/automations/trigger-details";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { pluralize } from "@/utils";

type AutomationDetailsProps = {
	automation: Automation;
};

export const AutomationDescription = ({
	automation,
}: AutomationDetailsProps) => {
	return (
		<div className="flex flex-col gap-1">
			<p className="text-sm text-muted-foreground">Description</p>
			<p className="text-base text-muted-foreground">
				{automation.description || "None"}
			</p>
		</div>
	);
};

export const AutomationTrigger = ({ automation }: AutomationDetailsProps) => {
	const { trigger } = automation;
	return (
		<div className="flex flex-col gap-1">
			<p className="text-base">Trigger</p>
			<TriggerDetails trigger={trigger} />
		</div>
	);
};

export const AutomationActions = ({ automation }: AutomationDetailsProps) => {
	const { data: resources, loading } =
		useGetAutomationActionResources(automation);

	const {
		automationsMap,
		blockDocumentsMap,
		deploymentsMap,
		workPoolsMap,
		workQueuesMap,
	} = resources;

	return (
		<div className="flex flex-col gap-1">
			<p className="text-base">
				{pluralize(automation.actions.length, "Action")}
			</p>
			<ul className="flex flex-col gap-2">
				{loading
					? Array.from({ length: automation.actions.length }, (_, i) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: ok for loading skeletons
							<Card className="p-4" key={i}>
								<Skeleton className="p-2 h-2 w-full" />
							</Card>
						))
					: automation.actions.map((action) => (
							<li key={action.type}>
								<ActionDetails
									action={action}
									automationsMap={automationsMap}
									blockDocumentsMap={blockDocumentsMap}
									deploymentsMap={deploymentsMap}
									workPoolsMap={workPoolsMap}
									workQueuesMap={workQueuesMap}
								/>
							</li>
						))}
			</ul>
		</div>
	);
};
