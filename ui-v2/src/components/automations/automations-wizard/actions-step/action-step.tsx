import { useWatch } from "react-hook-form";
import type { AutomationWizardSchema } from "@/components/automations/automations-wizard/automation-schema";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
import { Typography } from "@/components/ui/typography";
import { ActionTypeSelect } from "./action-type-select";
import { ChangeFlowRunStateFields } from "./change-flow-run-fields";
import { SelectAutomationsFields } from "./select-automations-fields";
import { SelectDeploymentsFields } from "./select-deployments-fields";
import { SelectWorkPoolsFields } from "./select-work-pools-fields";
import { SelectWorkQueuesFields } from "./select-work-queues-fields";

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
					<Icon id="Trash2" className="size-4" />
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
			return <SelectDeploymentsFields action="Run" index={index} />;
		case "pause-deployment":
			return <SelectDeploymentsFields action="Pause" index={index} />;
		case "resume-deployment":
			return <SelectDeploymentsFields action="Resume" index={index} />;
		case "pause-work-queue":
			return <SelectWorkQueuesFields action="Pause" index={index} />;
		case "resume-work-queue":
			return <SelectWorkQueuesFields action="Resume" index={index} />;
		case "pause-work-pool":
			return <SelectWorkPoolsFields action="Pause" index={index} />;
		case "resume-work-pool":
			return <SelectWorkPoolsFields action="Resume" index={index} />;
		case "pause-automation":
			return <SelectAutomationsFields action="Pause" index={index} />;
		case "resume-automation":
			return <SelectAutomationsFields action="Resume" index={index} />;
		case "send-notification":
			return <div>TODO send notification</div>;
		case "cancel-flow-run":
			return <div>TODO cancel flow run</div>;
		case "suspend-flow-run":
			return <div>TODO suspend flow run</div>;
		case "resume-flow-run":
			return <div>TODO resume flow run</div>;
		default:
			return null;
	}
};
