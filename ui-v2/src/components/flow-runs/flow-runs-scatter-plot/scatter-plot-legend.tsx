import { RUN_STATES } from "@/api/flow-runs/constants";
import { NOT_STARTED_STATES, type StateCount } from "./scatter-plot-utils";

type ScatterPlotLegendProps = {
	/** States to show, with their run counts, in legend order. */
	counts: readonly StateCount[];
};

export const ScatterPlotLegend = ({ counts }: ScatterPlotLegendProps) => (
	<ul className="flex flex-wrap gap-x-3 gap-y-1.5" aria-label="Runs by state">
		{counts.map(({ state, count }) => {
			const color = `var(--state-${state.toLowerCase()}-500)`;
			return (
				<li key={state} className="inline-flex items-center gap-1.5 text-xs">
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
				</li>
			);
		})}
	</ul>
);
