import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeWorkQueue } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { WorkQueueSelect } from "./work-queue-select";

const MOCK_WORK_QUEUES_DATA = Array.from({ length: 5 }, () =>
	createFakeWorkQueue({ work_pool_name: "my-work-pool" }),
);
const PRESET_OPTIONS = [{ label: "None", value: undefined }];
const meta = {
	title: "Components/WorkQueues/WorkQueueSelect",
	render: () => <WorkQueueSelectStory />,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(
					buildApiUrl("/work_pools/:work_pool_name/queues/filter"),
					() => {
						return HttpResponse.json(MOCK_WORK_QUEUES_DATA);
					},
				),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "WorkQueueSelect" };

const WorkQueueSelectStory = () => {
	const [selected, setSelected] = useState<string | undefined | null>();

	return (
		<WorkQueueSelect
			workPoolName="my-work-pool"
			selected={selected}
			onSelect={setSelected}
			presetOptions={PRESET_OPTIONS}
		/>
	);
};
