import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import type { EventsCount } from "@/api/events";
import { reactQueryDecorator } from "@/storybook/utils";
import { EventsCombobox } from "./events-combobox";

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

const meta = {
	title: "Components/Automations/EventsCombobox",
	component: EventsComboboxStory,
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
} satisfies Meta<typeof EventsCombobox>;

export default meta;

export const Default: StoryObj = {
	name: "Default",
};

export const WithSelectedEvents: StoryObj = {
	name: "With Selected Events",
	render: () => <EventsComboboxWithSelectionsStory />,
};

export const WithOverflow: StoryObj = {
	name: "With Overflow Indicator",
	render: () => <EventsComboboxWithOverflowStory />,
};

export const WithCustomEmptyMessage: StoryObj = {
	name: "With Custom Empty Message",
	render: () => <EventsComboboxWithCustomEmptyMessageStory />,
};

function EventsComboboxStory() {
	const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

	const handleToggleEvent = (event: string) => {
		setSelectedEvents((prev) =>
			prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
		);
	};

	return (
		<div className="w-80">
			<EventsCombobox
				selectedEvents={selectedEvents}
				onToggleEvent={handleToggleEvent}
			/>
		</div>
	);
}

function EventsComboboxWithSelectionsStory() {
	const [selectedEvents, setSelectedEvents] = useState<string[]>([
		"prefect.flow-run.*",
		"prefect.task-run.Completed",
	]);

	const handleToggleEvent = (event: string) => {
		setSelectedEvents((prev) =>
			prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
		);
	};

	return (
		<div className="w-80">
			<EventsCombobox
				selectedEvents={selectedEvents}
				onToggleEvent={handleToggleEvent}
			/>
		</div>
	);
}

function EventsComboboxWithOverflowStory() {
	const [selectedEvents, setSelectedEvents] = useState<string[]>([
		"prefect.flow-run.Completed",
		"prefect.flow-run.Failed",
		"prefect.task-run.Completed",
		"prefect.task-run.Failed",
	]);

	const handleToggleEvent = (event: string) => {
		setSelectedEvents((prev) =>
			prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
		);
	};

	return (
		<div className="w-80">
			<EventsCombobox
				selectedEvents={selectedEvents}
				onToggleEvent={handleToggleEvent}
			/>
		</div>
	);
}

function EventsComboboxWithCustomEmptyMessageStory() {
	const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

	const handleToggleEvent = (event: string) => {
		setSelectedEvents((prev) =>
			prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
		);
	};

	return (
		<div className="w-80">
			<EventsCombobox
				selectedEvents={selectedEvents}
				onToggleEvent={handleToggleEvent}
				emptyMessage="Select events to trigger on"
			/>
		</div>
	);
}
