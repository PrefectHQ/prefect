import { type Automation } from "@/api/automations";
import { useGetAutomationActionResources } from "@/api/automations/use-get-automation-action-resources";
import { ActionDetails } from "@/components/automations/action-details";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";

type AutomationDetailsProps = {
	data: Automation;
};

export const AutomationDescription = ({ data }: AutomationDetailsProps) => {
	return (
		<div className="flex flex-col gap-1">
			<Typography className="text-muted-foreground" variant="bodySmall">
				Description
			</Typography>
			<Typography className="text-muted-foreground">
				{data.description || "None"}
			</Typography>
		</div>
	);
};

export const AutomationTrigger = ({ data }: AutomationDetailsProps) => {
	const { trigger } = data;
	return (
		<div className="flex flex-col gap-1">
			<Typography>Trigger</Typography>
			<Typography variant="bodySmall">
				TODO: {JSON.stringify(trigger)}
			</Typography>
		</div>
	);
};

export const AutomationActions = ({ data }: AutomationDetailsProps) => {
	const { data: resources, loading } = useGetAutomationActionResources(data);

	const {
		automationsMap,
		blockDocumentsMap,
		deploymentsMap,
		workPoolsMap,
		workQueuesMap,
	} = resources;

	return (
		<div className="flex flex-col gap-1">
			<Typography>{pluralize(data.actions.length, "Action")}</Typography>
			<ul className="flex flex-col gap-2">
				{loading
					? Array.from({ length: data.actions.length }, (_, i) => (
							<Card className="p-4" key={i}>
								<Skeleton className="p-2 h-2 w-full" />
							</Card>
						))
					: data.actions.map((action, i) => (
							<li key={i}>
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
