import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { type ComponentProps, useState } from "react";
import { createFakeDeployment } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { DeploymentTagsSelect } from "./deployment-tags-select";

const MOCK_DEPLOYMENTS = [
	createFakeDeployment({ tags: ["production", "team-a"] }),
	createFakeDeployment({ tags: ["staging", "team-b"] }),
	createFakeDeployment({ tags: ["nightly", "production"] }),
];

export default {
	title: "Components/Deployments/DeploymentTagsSelect",
	component: DeploymentTagsSelect,
	decorators: [reactQueryDecorator],
	args: { value: [] },
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/deployments/filter"), () =>
					HttpResponse.json(MOCK_DEPLOYMENTS),
				),
			],
		},
	},
	// To control the selected tags in Stories via useState()
	render: function Render({
		value,
		...args
	}: ComponentProps<typeof DeploymentTagsSelect>) {
		const [tags, setTags] = useState<string[]>(value ?? []);
		return (
			<div className="w-72">
				<DeploymentTagsSelect {...args} value={tags} onChange={setTags} />
			</div>
		);
	},
} satisfies Meta<typeof DeploymentTagsSelect>;

type Story = StoryObj<typeof DeploymentTagsSelect>;

export const Default: Story = {};

export const WithSelectedTags: Story = {
	args: { value: ["production"] },
};
