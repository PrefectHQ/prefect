import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import {
	createFakeAutomation,
	createFakeBlockDocument,
	createFakeDeployment,
	createFakeFlow,
	createFakeWorkPool,
	createFakeWorkQueue,
} from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { EventsResourceFilter } from "./events-resource-filter";

const MOCK_AUTOMATIONS = Array.from({ length: 3 }, createFakeAutomation);
const MOCK_BLOCKS = Array.from({ length: 3 }, createFakeBlockDocument);
const MOCK_DEPLOYMENTS = Array.from({ length: 3 }, createFakeDeployment);
const MOCK_FLOWS = Array.from({ length: 3 }, createFakeFlow);
const MOCK_WORK_POOLS = Array.from({ length: 2 }, createFakeWorkPool);
const MOCK_WORK_QUEUES = Array.from({ length: 2 }, createFakeWorkQueue);

const meta = {
	title: "Components/Events/EventsResourceFilter",
	component: EventsResourceFilterStory,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/automations/filter"), () => {
					return HttpResponse.json(MOCK_AUTOMATIONS);
				}),
				http.post(buildApiUrl("/block_documents/filter"), () => {
					return HttpResponse.json(MOCK_BLOCKS);
				}),
				http.post(buildApiUrl("/deployments/filter"), () => {
					return HttpResponse.json(MOCK_DEPLOYMENTS);
				}),
				http.post(buildApiUrl("/flows/filter"), () => {
					return HttpResponse.json(MOCK_FLOWS);
				}),
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(MOCK_WORK_POOLS);
				}),
				http.post(buildApiUrl("/work_queues/filter"), () => {
					return HttpResponse.json(MOCK_WORK_QUEUES);
				}),
			],
		},
	},
} satisfies Meta<typeof EventsResourceFilter>;

export default meta;

export const Default: StoryObj = {
	name: "Default",
};

export const WithSelections: StoryObj = {
	name: "With Selections",
	render: () => <EventsResourceFilterWithSelectionsStory />,
};

function EventsResourceFilterStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([]);

	return (
		<div className="w-80">
			<EventsResourceFilter
				selectedResourceIds={selectedResourceIds}
				onResourceIdsChange={setSelectedResourceIds}
			/>
		</div>
	);
}

function EventsResourceFilterWithSelectionsStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([
		`prefect.automation.${MOCK_AUTOMATIONS[0].id}`,
		`prefect.flow.${MOCK_FLOWS[0].id}`,
		`prefect.deployment.${MOCK_DEPLOYMENTS[0].id}`,
	]);

	return (
		<div className="w-80">
			<EventsResourceFilter
				selectedResourceIds={selectedResourceIds}
				onResourceIdsChange={setSelectedResourceIds}
			/>
		</div>
	);
}
