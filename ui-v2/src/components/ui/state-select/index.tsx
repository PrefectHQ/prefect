import { RUN_STATES } from "@/api/flow-runs/constants";
import type { components } from "@/api/prefect";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { StateBadge } from "@/components/ui/state-badge";

type StateType = components["schemas"]["StateType"];

const TERMINAL_STATES: StateType[] = [
	"COMPLETED",
	"FAILED",
	"CANCELLED",
	"CRASHED",
];

export type StateSelectProps = {
	value?: StateType;
	onValueChange: (value: StateType) => void;
	placeholder?: string;
	terminalOnly?: boolean;
	excludeState?: StateType;
};

export const StateSelect = ({
	value,
	onValueChange,
	placeholder = "Select state",
	terminalOnly = false,
	excludeState,
}: StateSelectProps) => {
	const stateEntries = Object.entries(RUN_STATES) as [StateType, string][];

	const filteredStates = stateEntries.filter(([key]) => {
		if (terminalOnly && !TERMINAL_STATES.includes(key)) {
			return false;
		}
		if (excludeState && key === excludeState) {
			return false;
		}
		return true;
	});

	return (
		<Select value={value} onValueChange={onValueChange}>
			<SelectTrigger aria-label="select state" className="w-full">
				<SelectValue placeholder={placeholder}>
					{value && <StateBadge type={value} name={RUN_STATES[value]} />}
				</SelectValue>
			</SelectTrigger>
			<SelectContent className="w-full min-w-[300px]">
				{filteredStates.map(([key, displayName]) => (
					<SelectItem key={key} value={key} className="flex items-center">
						<StateBadge type={key} name={displayName} />
					</SelectItem>
				))}
			</SelectContent>
		</Select>
	);
};
