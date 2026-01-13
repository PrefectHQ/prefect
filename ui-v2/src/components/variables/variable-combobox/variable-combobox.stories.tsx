import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeVariable } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { VariableCombobox } from "./variable-combobox";

const MOCK_VARIABLES_DATA = Array.from({ length: 5 }, () =>
	createFakeVariable(),
);

const meta = {
	title: "Components/Variables/VariableCombobox",
	render: () => <VariableComboboxStory />,
	decorators: [reactQueryDecorator],
	parameters: {
		msw: {
			handlers: [
				http.post(buildApiUrl("/variables/filter"), () => {
					return HttpResponse.json(MOCK_VARIABLES_DATA);
				}),
			],
		},
	},
} satisfies Meta;

export default meta;

export const story: StoryObj = { name: "VariableCombobox" };

const VariableComboboxStory = () => {
	const [selected, setSelected] = useState<string | undefined>();

	return (
		<VariableCombobox selectedVariableName={selected} onSelect={setSelected} />
	);
};
