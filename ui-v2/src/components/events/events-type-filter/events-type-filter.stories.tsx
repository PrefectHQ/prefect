import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import type { EventsCount, EventsCountFilter } from "@/api/events";
import { reactQueryDecorator } from "@/storybook/utils";
import { EventsTypeFilter } from "./events-type-filter";

const MOCK_EVENT_COUNTS: EventsCount[] = [
	{
		value: "prefect.flow-run.Completed",
		label: "prefect.flow-run.Completed",
		count: 150,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
	{
		value: "prefect.flow-run.Failed",
		label: "prefect.flow-run.Failed",
		count: 25,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
	{
		value: "prefect.flow-run.Running",
		label: "prefect.flow-run.Running",
		count: 10,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
	{
		value: "prefect.task-run.Completed",
		label: "prefect.task-run.Completed",
		count: 500,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
	{
		value: "prefect.task-run.Failed",
		label: "prefect.task-run.Failed",
		count: 50,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
	{
		value: "prefect.deployment.created",
		label: "prefect.deployment.created",
		count: 5,
		start_time: "2024-01-01T00:00:00Z",
		end_time: "2024-01-31T23:59:59Z",
	},
];

const DEFAULT_FILTER: EventsCountFilter = {
	filter: {
		occurred: {
			since: "2024-01-01T00:00:00Z",
			until: "2024-01-31T23:59:59Z",
		},
		order: "ASC",
	},
	time_unit: "day",
	time_interval: 1,
};

const meta = {
	title: "Components/Events/EventsTypeFilter",
	component: EventsTypeFilterStory,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/count-by/:countable"), () => {
					return HttpResponse.json(MOCK_EVENT_COUNTS);
				}),
			],
		},
	},
} satisfies Meta<typeof EventsTypeFilter>;

export default meta;

export const Default: StoryObj = {
	name: "Default",
};

export const WithSelectedTypes: StoryObj = {
	name: "With Selected Types",
	render: () => <EventsTypeFilterWithSelectionsStory />,
};

function EventsTypeFilterStory() {
	const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);

	return (
		<div className="w-80">
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={selectedEventTypes}
				onEventTypesChange={setSelectedEventTypes}
			/>
		</div>
	);
}

function EventsTypeFilterWithSelectionsStory() {
	const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([
		"prefect.flow-run.*",
		"prefect.task-run.Completed",
	]);

	return (
		<div className="w-80">
			<EventsTypeFilter
				filter={DEFAULT_FILTER}
				selectedEventTypes={selectedEventTypes}
				onEventTypesChange={setSelectedEventTypes}
			/>
		</div>
	);
}
