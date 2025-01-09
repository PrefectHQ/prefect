import { ActionChangeFlowRunStateMessageField } from "./action-change-flow-run-state-message-field";
import { ActionChangeFlowRunStateNameField } from "./action-change-flow-run-state-name-field";
import { ActionChangeFlowRunStateStateField } from "./action-change-flow-run-state-state-field";

type ActionChangeFlowRunStateFieldsProps = {
	index: number;
};

export const ActionChangeFlowRunStateFields = ({
	index,
}: ActionChangeFlowRunStateFieldsProps) => (
	<div>
		<ActionChangeFlowRunStateStateField index={index} />
		<ActionChangeFlowRunStateNameField index={index} />
		<ActionChangeFlowRunStateMessageField index={index} />
	</div>
);
