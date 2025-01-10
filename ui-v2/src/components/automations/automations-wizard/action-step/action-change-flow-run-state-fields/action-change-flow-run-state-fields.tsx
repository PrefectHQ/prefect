import { ActionChangeFlowRunStateMessageField } from "./action-change-flow-run-state-message-field";
import { ActionChangeFlowRunStateNameField } from "./action-change-flow-run-state-name-field";
import { ActionChangeFlowRunStateStateField } from "./action-change-flow-run-state-state-field";

export const ActionChangeFlowRunStateFields = () => (
	<>
		<ActionChangeFlowRunStateStateField />
		<ActionChangeFlowRunStateNameField />
		<ActionChangeFlowRunStateMessageField />
	</>
);
