import { createFileRoute } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { z } from "zod";
import { buildListGlobalConcurrencyLimitsQuery } from "@/api/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/api/task-run-concurrency-limits";
import { ConcurrencyLimitsPage } from "@/components/concurrency/concurrency-limits-page";

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
	loader: ({ context }) =>
		Promise.all([
			context.queryClient.ensureQueryData(
				buildListGlobalConcurrencyLimitsQuery(),
			),
			context.queryClient.ensureQueryData(
				buildListTaskRunConcurrencyLimitsQuery(),
			),
		]),
});
