import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeWorkPool } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { WorkPoolSelect } from "./work-pool-select";

const MOCK_WORK_POOLS_DATA = Array.from({ length: 5 }, createFakeWorkPool);
const PRESET_OPTIONS = [{ label: "None", value: undefined }];
const meta = {
	title: "Components/WorkPools/WorkPoolSelect",
	render: () => <WorkPoolSelectStory />,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/work_pools/filter"), () => {
					return HttpResponse.json(MOCK_WORK_POOLS_DATA);
				}),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "WorkPoolSelect" };

const WorkPoolSelectStory = () => {
	const [selected, setSelected] = useState<string | undefined | null>();

	return (
		<WorkPoolSelect
			selected={selected}
			onSelect={setSelected}
			presetOptions={PRESET_OPTIONS}
		/>
	);
};
