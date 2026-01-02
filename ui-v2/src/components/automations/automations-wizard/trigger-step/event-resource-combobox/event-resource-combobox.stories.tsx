import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeAutomation } from "@/mocks/create-fake-automation";
import { createFakeBlockDocument } from "@/mocks/create-fake-block-document";
import { createFakeDeployment } from "@/mocks/create-fake-deployment";
import { createFakeFlow } from "@/mocks/create-fake-flow";
import { createFakeWorkPool } from "@/mocks/create-fake-work-pool";
import { createFakeWorkQueue } from "@/mocks/create-fake-work-queue";
import { reactQueryDecorator } from "@/storybook/utils";
import { EventResourceCombobox } from "./event-resource-combobox";

const MOCK_AUTOMATIONS = [
	createFakeAutomation({ id: "automation-1", name: "Daily ETL Pipeline" }),
	createFakeAutomation({ id: "automation-2", name: "Weekly Report Generator" }),
	createFakeAutomation({ id: "automation-3", name: "Error Alert Handler" }),
];

const MOCK_BLOCKS = [
	createFakeBlockDocument({ id: "block-1", name: "S3 Storage" }),
	createFakeBlockDocument({ id: "block-2", name: "Slack Webhook" }),
];

const MOCK_DEPLOYMENTS = [
	createFakeDeployment({ id: "deployment-1", name: "prod-etl" }),
	createFakeDeployment({ id: "deployment-2", name: "staging-etl" }),
	createFakeDeployment({ id: "deployment-3", name: "dev-etl" }),
];

const MOCK_FLOWS = [
	createFakeFlow({ id: "flow-1", name: "data-pipeline" }),
	createFakeFlow({ id: "flow-2", name: "ml-training" }),
];

const MOCK_WORK_POOLS = [
	createFakeWorkPool({ name: "kubernetes-pool" }),
	createFakeWorkPool({ name: "docker-pool" }),
];

const MOCK_WORK_QUEUES = [
	createFakeWorkQueue({ id: "work-queue-1", name: "high-priority" }),
	createFakeWorkQueue({ id: "work-queue-2", name: "low-priority" }),
];

const meta = {
	title: "Components/Automations/EventResourceCombobox",
	component: EventResourceComboboxStory,
	decorators: [reactQueryDecorator],
	parameters: {
		layout: "centered",
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
} satisfies Meta<typeof EventResourceCombobox>;

export default meta;

export const Default: StoryObj = {
	name: "Default",
};

export const WithSelectedResources: StoryObj = {
	name: "With Selected Resources",
	render: () => <EventResourceComboboxWithSelectionsStory />,
};

export const WithOverflow: StoryObj = {
	name: "With Overflow Indicator",
	render: () => <EventResourceComboboxWithOverflowStory />,
};

export const WithCustomEmptyMessage: StoryObj = {
	name: "With Custom Empty Message",
	render: () => <EventResourceComboboxWithCustomEmptyMessageStory />,
};

function EventResourceComboboxStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([]);

	const handleToggleResource = (resourceId: string) => {
		setSelectedResourceIds((prev) =>
			prev.includes(resourceId)
				? prev.filter((id) => id !== resourceId)
				: [...prev, resourceId],
		);
	};

	return (
		<div className="w-80">
			<EventResourceCombobox
				selectedResourceIds={selectedResourceIds}
				onToggleResource={handleToggleResource}
			/>
		</div>
	);
}

function EventResourceComboboxWithSelectionsStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([
		"prefect.automation.automation-1",
		"prefect.flow.flow-1",
	]);

	const handleToggleResource = (resourceId: string) => {
		setSelectedResourceIds((prev) =>
			prev.includes(resourceId)
				? prev.filter((id) => id !== resourceId)
				: [...prev, resourceId],
		);
	};

	return (
		<div className="w-80">
			<EventResourceCombobox
				selectedResourceIds={selectedResourceIds}
				onToggleResource={handleToggleResource}
			/>
		</div>
	);
}

function EventResourceComboboxWithOverflowStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([
		"prefect.automation.automation-1",
		"prefect.flow.flow-1",
		"prefect.deployment.deployment-1",
		"prefect.block-document.block-1",
	]);

	const handleToggleResource = (resourceId: string) => {
		setSelectedResourceIds((prev) =>
			prev.includes(resourceId)
				? prev.filter((id) => id !== resourceId)
				: [...prev, resourceId],
		);
	};

	return (
		<div className="w-80">
			<EventResourceCombobox
				selectedResourceIds={selectedResourceIds}
				onToggleResource={handleToggleResource}
			/>
		</div>
	);
}

function EventResourceComboboxWithCustomEmptyMessageStory() {
	const [selectedResourceIds, setSelectedResourceIds] = useState<string[]>([]);

	const handleToggleResource = (resourceId: string) => {
		setSelectedResourceIds((prev) =>
			prev.includes(resourceId)
				? prev.filter((id) => id !== resourceId)
				: [...prev, resourceId],
		);
	};

	return (
		<div className="w-80">
			<EventResourceCombobox
				selectedResourceIds={selectedResourceIds}
				onToggleResource={handleToggleResource}
				emptyMessage="Select resources to filter"
			/>
		</div>
	);
}
