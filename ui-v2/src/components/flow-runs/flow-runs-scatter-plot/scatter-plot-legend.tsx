import { type MouseEvent, useRef } from "react";
import { RUN_STATES, type StateType } from "@/api/flow-runs/constants";
import { STATE_TYPES } from "@/components/flow-runs/flow-runs-list/flow-runs-filters/state-filter-utils";
import { cn } from "@/utils";
import { NOT_STARTED_STATES, type StateCount } from "./scatter-plot-utils";

type ScatterPlotLegendProps = {
	/** States to show, with their run counts, in legend order. */
	counts: readonly StateCount[];
	/** The page's state type filter; empty means every type. */
	selectedStateTypes?: ReadonlySet<StateType>;
	/** Omit to show the legend as a key without filtering. */
	onSelectedStateTypesChange?: (types: Set<StateType>) => void;
};

const StateKey = ({ state, count }: StateCount) => {
	const color = `var(--state-${state.toLowerCase()}-500)`;
	return (
		<>
			<span
				aria-hidden
				className="size-2.5 shrink-0 rounded-full"
				style={
					NOT_STARTED_STATES.has(state)
						? { boxShadow: `inset 0 0 0 1.5px ${color}` }
						: { backgroundColor: color }
				}
			/>
			{RUN_STATES[state]}
			<span className="text-muted-foreground tabular-nums">
				{count.toLocaleString()}
			</span>
		</>
	);
};

export const ScatterPlotLegend = ({
	counts,
	selectedStateTypes = new Set(),
	onSelectedStateTypesChange,
}: ScatterPlotLegendProps) => {
	const restoreTo = useRef<Set<StateType> | undefined>(undefined);

	if (!onSelectedStateTypesChange) {
		return (
			<ul
				className="flex flex-wrap gap-x-3 gap-y-1.5"
				aria-label="Runs by state"
			>
				{counts.map(({ state, count }) => (
					<li key={state} className="inline-flex items-center gap-1.5 text-xs">
						<StateKey state={state} count={count} />
					</li>
				))}
			</ul>
		);
	}

	const [only] = selectedStateTypes;
	const isolated = selectedStateTypes.size === 1 ? only : undefined;
	const onChipClick = (state: StateType, event: MouseEvent) => {
		if (event.shiftKey) {
			const remaining = new Set(
				(selectedStateTypes.size > 0
					? [...selectedStateTypes]
					: STATE_TYPES
				).filter((type) => type !== state),
			);
			if (remaining.size > 0) onSelectedStateTypesChange(remaining);
			return;
		}
		if (state === isolated) {
			onSelectedStateTypesChange(restoreTo.current ?? new Set());
			restoreTo.current = undefined;
			return;
		}
		if (isolated === undefined) restoreTo.current = new Set(selectedStateTypes);
		onSelectedStateTypesChange(new Set([state]));
	};

	return (
		<ul className="flex flex-wrap gap-1.5" aria-label="Filter runs by state">
			{counts.map(({ state, count }) => {
				const pressed = state === isolated;
				return (
					<li key={state}>
						<button
							type="button"
							aria-pressed={pressed}
							title={
								pressed
									? "Show the other states again"
									: `Show only ${RUN_STATES[state].toLowerCase()} runs. Shift-click to hide them.`
							}
							onClick={(event) => onChipClick(state, event)}
							className={cn(
								"inline-flex h-11 items-center gap-1.5 rounded-md border px-2.5 text-xs transition-colors md:h-8",
								pressed
									? "border-foreground/40 bg-accent"
									: "border-transparent hover:bg-muted",
							)}
						>
							<StateKey state={state} count={count} />
						</button>
					</li>
				);
			})}
		</ul>
	);
};
