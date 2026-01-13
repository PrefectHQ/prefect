import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { useState } from "react";
import { createFakeVariable } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { SchemaFormInputPrefectKindWorkspaceVariable } from "../schema-form-input-prefect-kind-workspace-variable";
import type { PrefectKindValueWorkspaceVariable } from "../types/prefect-kind-value";

const MOCK_VARIABLES_DATA = Array.from({ length: 5 }, () =>
	createFakeVariable(),
);

const meta = {
	title: "Components/Schemas/SchemaFormInputPrefectKindWorkspaceVariable",
	render: () => <SchemaFormInputPrefectKindWorkspaceVariableStory />,
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

export const story: StoryObj = {
	name: "SchemaFormInputPrefectKindWorkspaceVariable",
};

const SchemaFormInputPrefectKindWorkspaceVariableStory = () => {
	const [value, setValue] = useState<PrefectKindValueWorkspaceVariable>({
		__prefect_kind: "workspace_variable",
		variable_name: undefined,
	});

	return (
		<SchemaFormInputPrefectKindWorkspaceVariable
			value={value}
			onValueChange={setValue}
			id="story-id"
		/>
	);
};
