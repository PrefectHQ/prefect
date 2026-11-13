import { RUN_STATES, type StateType } from "@/api/flow-runs/constants";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Icon } from "@/components/ui/icons";
import { NON_SCHEDULED_STATE_TYPES, STATE_TYPES } from "./state-filter-utils";

export function StateTypeFilter({
	selectedFilters,
	onSelectFilter,
}: {
	selectedFilters: Set<StateType>;
	onSelectFilter: (types: Set<StateType>) => void;
}) {
	const label =
		selectedFilters.size === NON_SCHEDULED_STATE_TYPES.length &&
		NON_SCHEDULED_STATE_TYPES.every((type) => selectedFilters.has(type))
			? "All except scheduled"
			: selectedFilters.size > 2
				? `${selectedFilters.size} state types`
				: [...selectedFilters].map((type) => RUN_STATES[type]).join(", ");
	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					variant="outline"
					aria-label="State types"
					className="w-full justify-between"
				>
					<span className="truncate">{label || "All state types"}</span>
					<Icon id="ChevronDown" className="ml-2 size-4 shrink-0" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent>
				<DropdownMenuItem
					onSelect={(event) => {
						event.preventDefault();
						onSelectFilter(new Set());
					}}
				>
					All state types
				</DropdownMenuItem>
				<DropdownMenuItem
					onSelect={(event) => {
						event.preventDefault();
						onSelectFilter(new Set(NON_SCHEDULED_STATE_TYPES));
					}}
				>
					All except scheduled
				</DropdownMenuItem>
				{STATE_TYPES.map((type) => (
					<DropdownMenuItem
						key={type}
						onSelect={(event) => {
							event.preventDefault();
							const next = new Set(selectedFilters);
							if (next.has(type)) next.delete(type);
							else next.add(type);
							onSelectFilter(next);
						}}
					>
						<Checkbox checked={selectedFilters.has(type)} className="mr-2" />
						{RUN_STATES[type]}
					</DropdownMenuItem>
				))}
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
