import type { ErrorComponentProps } from "@tanstack/react-router";
import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { categorizeError } from "@/api/error-utils";
import { buildListGlobalConcurrencyLimitsQuery } from "@/api/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";
import { PrefectLoading } from "@/components/ui/loading";
import { RouteErrorState } from "@/components/ui/route-error-state";

/**
 * Schema for validating URL search parameters for the Concurrency Limits page.
 * @property {string} search used to filter data table
 * @property {'global' | 'task-run'} tab used designate which tab view to display
 */
const searchParams = z.object({
	search: z.string().optional(),
	tab: z.enum(["global", "task-run"]).default("global"),
});

export type TabOptions = z.infer<typeof searchParams>["tab"];

export const Route = createFileRoute("/concurrency-limits/")({
	validateSearch: zodValidator(searchParams),
	component: ConcurrencyLimitsPage,
	wrapInSuspense: true,
	pendingComponent: PrefectLoading,
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(
				buildListGlobalConcurrencyLimitsQuery(),
			),
			context.queryClient.ensureQueryData(
				buildListTaskRunConcurrencyLimitsQuery(),
			),
		]),
	errorComponent: function ConcurrencyLimitsErrorComponent({
		error,
		reset,
	}: ErrorComponentProps) {
		const serverError = categorizeError(
			error,
			"Failed to load concurrency limits",
		);
		if (
			serverError.type !== "server-error" &&
			serverError.type !== "client-error"
		) {
			throw error;
		}
		return (
			<div className="flex flex-col gap-4">
				<div>
					<h1 className="text-2xl font-semibold">Concurrency Limits</h1>
				</div>
				<RouteErrorState error={serverError} onRetry={reset} />
			</div>
		);
	},
});
