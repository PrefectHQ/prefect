import { type AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { useWatch } from "react-hook-form";
import { ActionTypeSelect } from "./action-type-select";
import { AutomationsSelectStateFields } from "./automations-select-state-fields";
import { ChangeFlowRunStateFields } from "./change-flow-run-fields";

type ActionStepProps = {
	index: number;
	onRemove: () => void;
};

export const ActionStep = ({ index, onRemove }: ActionStepProps) => {
	return (
		<div key={index} className="flex flex-col gap-2">
			<div className="flex justify-between items-center">
				<Typography variant="body" className="font-semibold">
					Action {index + 1}
				</Typography>
				<Button
					size="icon"
					aria-label={`remove action ${index + 1}`}
					onClick={onRemove}
					variant="outline"
				>
					<Icon id="Trash2" className="h-4 w-4" />
				</Button>
			</div>
			<ActionTypeSelect index={index} />
			<ActionTypeAdditionalFields index={index} />
			<hr className="my-10" />
		</div>
	);
};

type ActionTypeAdditionalFieldsProps = {
	index: number;
};

const ActionTypeAdditionalFields = ({
	index,
}: ActionTypeAdditionalFieldsProps) => {
	const actionType = useWatch<AutomationWizardSchema>({
		name: `actions.${index}.type`,
	});
	switch (actionType) {
		case "change-flow-run-state":
			return <ChangeFlowRunStateFields index={index} />;
		case "run-deployment":
		case "pause-deployment":
		case "resume-deployment":
			return <div>TODO Deployment</div>;
		case "pause-work-queue":
		case "resume-work-queue":
			return <div>TODO Work Queue</div>;
		case "pause-work-pool":
		case "resume-work-pool":
			return <div>TODO Work pool</div>;
		case "pause-automation":
			return <AutomationsSelectStateFields action="Pause" index={index} />;
		case "resume-automation":
			return <AutomationsSelectStateFields action="Resume" index={index} />;
		case "send-notification":
			return <div>TODO send notification</div>;
		case "cancel-flow-run":
		case "suspend-flow-run":
		case "resume-flow-run":
		default:
			return null;
	}
};
