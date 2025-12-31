import type { Meta, StoryObj } from "@storybook/react";
import { type ComponentProps, useState } from "react";
import { fn } from "storybook/test";
import { EventsCombobox } from "./events-combobox";

export default {
	title: "Components/Automations/Wizard/EventsCombobox",
	component: EventsCombobox,
	args: {
		selectedEvents: [],
		onEventsChange: fn(),
		emptyMessage: "All events",
	},
	render: function Render(args: ComponentProps<typeof EventsCombobox>) {
		const [selectedEvents, setSelectedEvents] = useState<string[]>(
			args.selectedEvents,
		);

		return (
			<div className="w-96">
				<EventsCombobox
					{...args}
					selectedEvents={selectedEvents}
					onEventsChange={(events) => {
						setSelectedEvents(events);
						args.onEventsChange(events);
					}}
				/>
				<p className="mt-4 text-sm text-muted-foreground">
					Selected:{" "}
					{selectedEvents.length === 0 ? "None" : selectedEvents.join(", ")}
				</p>
			</div>
		);
	},
} satisfies Meta<typeof EventsCombobox>;

type Story = StoryObj<typeof EventsCombobox>;

export const Default: Story = {};

export const WithSelectedEvents: Story = {
	args: {
		selectedEvents: ["prefect.flow-run.Completed", "prefect.flow-run.Failed"],
	},
};

export const WithManySelectedEvents: Story = {
	args: {
		selectedEvents: [
			"prefect.flow-run.Completed",
			"prefect.flow-run.Failed",
			"prefect.flow-run.Running",
			"prefect.flow-run.Pending",
		],
	},
};

export const WithWildcardEvent: Story = {
	args: {
		selectedEvents: ["prefect.flow-run.*"],
	},
};

export const CustomEmptyMessage: Story = {
	args: {
		emptyMessage: "Select events to match...",
	},
};
