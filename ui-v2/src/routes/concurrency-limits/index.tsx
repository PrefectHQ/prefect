import { ConcurrencyPage } from "@/components/concurrency/concurrency-page";
import { buildListGlobalConcurrencyLimitsQuery } from "@/hooks/global-concurrency-limits";
import { buildListTaskRunConcurrencyLimitsQuery } from "@/hooks/task-run-concurrency-limits";
import { createFileRoute } from "@tanstack/react-router";
import { zodSearchValidator } from "@tanstack/router-zod-adapter";
import { z } from "zod";

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
	validateSearch: zodSearchValidator(searchParams),
	component: ConcurrencyPage,
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
