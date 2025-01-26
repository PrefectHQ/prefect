import { type Automation } from "@/api/automations";
import { ActionDetails } from "@/components/automations/action-details";
import { Typography } from "@/components/ui/typography";
import { pluralize } from "@/utils";

type AutomationDetailsProps = {
	data: Automation;
};

export const AutomationDetails = ({ data }: AutomationDetailsProps) => (
	<div className="flex flex-col gap-4">
		<AutomationDescription data={data} />
		<AutomationTrigger data={data} />
		<AutomationActions data={data} />
	</div>
);

const AutomationDescription = ({ data }: AutomationDetailsProps) => {
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

const AutomationTrigger = ({ data }: AutomationDetailsProps) => {
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

const AutomationActions = ({ data }: AutomationDetailsProps) => {
	const { actions } = data;
	return (
		<div className="flex flex-col gap-1">
			<Typography>{pluralize(actions.length, "Action")}</Typography>
			<ul className="flex flex-col gap-2">
				{actions.map((action, i) => (
					<li key={i}>
						<ActionDetails action={action} />
					</li>
				))}
			</ul>
		</div>
	);
};
