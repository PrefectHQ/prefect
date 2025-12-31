import { useQuery } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { zodValidator } from "@tanstack/zod-adapter";
import { toast } from "sonner";
import { z } from "zod";
import { useCreateAutomation } from "@/api/automations";
import { buildGetEventQuery } from "@/api/events";
import type { components } from "@/api/prefect";
import { AutomationsCreateHeader } from "@/components/automations/automations-create-header";
import {
	AutomationWizard,
	type AutomationWizardSchemaType,
	transformEventToTrigger,
} from "@/components/automations/automations-wizard";

type AutomationCreate = components["schemas"]["AutomationCreate"];

/**
 * Search params schema for the create automation route.
 * Supports pre-populating the wizard from an event.
 */
const searchParams = z.object({
	actions: z.record(z.unknown()).optional(),
	/** Event ID to pre-populate the trigger from */
	eventId: z.string().optional(),
	/** Event date in YYYY-MM-DD format for fetching the event */
	eventDate: z.string().optional(),
});

/**
 * Parses a YYYY-MM-DD date string into a Date object.
 */
function parseRouteDate(dateStr: string): Date {
	const [year, month, day] = dateStr.split("-").map(Number);
	return new Date(year, month - 1, day);
}

export const Route = createFileRoute("/automations/create")({
	component: RouteComponent,
	validateSearch: zodValidator(searchParams),
	loaderDeps: ({ search }) => ({
		eventId: search.eventId,
		eventDate: search.eventDate,
	}),
	loader: ({ deps, context: { queryClient } }) => {
		// Prefetch event data if eventId and eventDate are provided
		if (deps.eventId && deps.eventDate) {
			const eventDate = parseRouteDate(deps.eventDate);
			void queryClient.prefetchQuery(
				buildGetEventQuery(deps.eventId, eventDate),
			);
		}
	},
	wrapInSuspense: true,
});

/**
 * Hook to get default values for the automation wizard when pre-populating from an event.
 * Returns undefined if no event params are provided.
 */
function useEventDefaultValues() {
	const { eventId, eventDate } = Route.useSearch();

	// Only fetch if both params are provided
	const shouldFetch = Boolean(eventId && eventDate);

	// Use useQuery (not useSuspenseQuery) because useSuspenseQuery doesn't support enabled option
	const { data: event } = useQuery({
		...buildGetEventQuery(
			eventId ?? "",
			eventDate ? parseRouteDate(eventDate) : new Date(),
		),
		enabled: shouldFetch,
	});

	if (!shouldFetch || !event) {
		return undefined;
	}

	const { trigger, triggerTemplate } = transformEventToTrigger(event);
	return {
		trigger,
		triggerTemplate,
	};
}

function RouteComponent() {
	const { createAutomation, isPending } = useCreateAutomation();
	const navigate = useNavigate();
	const eventDefaultValues = useEventDefaultValues();

	const handleSubmit = (values: AutomationWizardSchemaType) => {
		const automationData: AutomationCreate = {
			name: values.name,
			description: values.description ?? "",
			enabled: true,
			trigger: values.trigger,
			actions: values.actions,
		};

		createAutomation(automationData, {
			onSuccess: () => {
				toast.success("Automation created successfully");
				void navigate({ to: "/automations" });
			},
			onError: (error) => {
				toast.error(`Failed to create automation: ${error.message}`);
			},
		});
	};

	return (
		<div className="flex flex-col gap-4">
			<AutomationsCreateHeader />
			<AutomationWizard
				defaultValues={eventDefaultValues}
				onSubmit={handleSubmit}
				isSubmitting={isPending}
			/>
		</div>
	);
}
