import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { createFakeEvent } from "@/mocks";
import {
	reactQueryDecorator,
	routerDecorator,
	toastDecorator,
} from "@/storybook/utils";
import { EventDetailsPage } from "./event-details-page";

const fakeEvent = createFakeEvent({
	id: "test-event-id",
	event: "prefect.flow-run.Completed",
	occurred: "2024-06-15T14:30:45.000Z",
	resource: {
		"prefect.resource.id": "prefect.flow-run.abc-123",
		"prefect.resource.name": "my-flow-run",
	},
	related: [
		{
			"prefect.resource.id": "prefect.flow.flow-123",
			"prefect.resource.role": "flow",
			"prefect.resource.name": "my-flow",
		},
		{
			"prefect.resource.id": "prefect.tag.production",
			"prefect.resource.role": "tag",
		},
	],
});

const meta = {
	title: "Components/Events/EventDetailsPage",
	component: EventDetailsPage,
	decorators: [reactQueryDecorator, routerDecorator, toastDecorator],
	args: {
		eventId: "test-event-id",
		eventDate: new Date("2024-06-15T14:30:45.000Z"),
	},
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/events/filter"), () => {
					return HttpResponse.json({
						events: [fakeEvent],
						total: 1,
						next_page: null,
					});
				}),
			],
		},
	},
} satisfies Meta<typeof EventDetailsPage>;

export default meta;

export const Default: StoryObj<typeof EventDetailsPage> = {
	name: "EventDetailsPage",
};
