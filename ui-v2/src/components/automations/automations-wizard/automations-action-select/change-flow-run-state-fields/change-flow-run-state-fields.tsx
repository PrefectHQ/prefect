import { components } from "@/api/prefect";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const FLOW_STATES = {
	COMPLETED: "Completed",
	RUNNING: "Running",
	SCHEDULED: "Scheduled",
	PENDING: "Pending",
	FAILED: "Failed",
	CANCELLED: "Cancelled",
	CANCELLING: "Cancelling",
	CRASHED: "Crashed",
	PAUSED: "Paused",
} as const;
export type FlowStates = keyof typeof FLOW_STATES;

export type ChangeFlowRunStateFields = Partial<
	Omit<
		Extract<
			components["schemas"]["AutomationCreate"]["actions"][number],
			{ type: "change-flow-run-state" }
		>,
		"type"
	>
>;

type ChangeFlowRunStateFieldsProps = {
	values: ChangeFlowRunStateFields;
	onChange: (values: ChangeFlowRunStateFields) => void;
};

export const ChangeFlowRunStateFields = ({
	values,
	onChange,
}: ChangeFlowRunStateFieldsProps) => {
	return (
		<div className="row flex-col gap-4">
			<div>
				<Label htmlFor="change-flow-run-state-state-select">State</Label>
				<Select
					value={values.state}
					onValueChange={(state: FlowStates) => onChange({ ...values, state })}
				>
					<SelectTrigger id="change-flow-run-state-state-select">
						<SelectValue placeholder="Select action" />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							<SelectLabel>Actions</SelectLabel>
							{Object.keys(FLOW_STATES).map((key) => (
								<SelectItem key={key} value={key}>
									{FLOW_STATES[key as FlowStates]}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
			</div>
			<div>
				<Label htmlFor="change-flow-run-state-name-input">Name</Label>
				<Input
					id="change-flow-run-state-name-input"
					type="text"
					value={values.name ?? ""}
					onChange={(e) => onChange({ ...values, name: e.target.value })}
				/>
			</div>
			<div>
				<Label htmlFor="change-flow-run-state-message-input">Message</Label>
				<Textarea
					id="change-flow-run-state-message-input"
					placeholder="State changed by Automation <id>"
					value={values.message ?? ""}
					onChange={(e) => onChange({ ...values, message: e.target.value })}
				/>
			</div>
		</div>
	);
};
