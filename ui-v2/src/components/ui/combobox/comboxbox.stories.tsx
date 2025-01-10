import type { Meta, StoryObj } from "@storybook/react";

import { Automation } from "@/api/automations";
import { UNASSIGNED } from "@/components/automations/automations-wizard/action-step/action-type-schemas";
import { createFakeAutomation } from "@/mocks";
import { useState } from "react";
import {
	Combobox,
	ComboboxCommandEmtpy,
	ComboboxCommandGroup,
	ComboboxCommandInput,
	ComboboxCommandItem,
	ComboboxCommandList,
	ComboboxContent,
	ComboboxTrigger,
} from "./combobox";

const meta: Meta<typeof ComboboxStory> = {
	title: "UI/Combobox",
	component: ComboboxStory,
};
export default meta;

const INFER_AUTOMATION = {
	value: UNASSIGNED,
	name: "Infer Automation" as const,
} as const;

const MOCK_DATA = [
	createFakeAutomation(),
	createFakeAutomation(),
	createFakeAutomation(),
	createFakeAutomation(),
	createFakeAutomation(),
];

const getButtonLabel = (data: Array<Automation>, fieldValue: string) => {
	if (fieldValue === INFER_AUTOMATION.value) {
		return INFER_AUTOMATION.name;
	}
	const automation = data?.find((automation) => automation.id === fieldValue);
	if (automation?.name) {
		return automation.name;
	}
	return undefined;
};

/** Because ShadCN only filters by `value` and not by a specific field, we need to write custom logic to filter objects by id */
const filterAutomations = (
	value: string,
	search: string,
	data: Array<Automation> | undefined,
) => {
	const searchTerm = search.toLowerCase();
	const automation = data?.find((automation) => automation.id === value);
	if (!automation) {
		return 0;
	}
	const automationName = automation.name.toLowerCase();
	if (automationName.includes(searchTerm)) {
		return 1;
	}
	return 0;
};

function ComboboxStory() {
	const [selectedAutomationId, setSelectedAutomationId] = useState<
		typeof UNASSIGNED | (string & {})
	>(INFER_AUTOMATION.value);

	const buttonLabel = getButtonLabel(MOCK_DATA, selectedAutomationId);

	return (
		<Combobox>
			<ComboboxTrigger selected={Boolean(buttonLabel)}>
				{buttonLabel ?? "Select automation"}
			</ComboboxTrigger>
			<ComboboxContent
				filter={(value, search) => filterAutomations(value, search, MOCK_DATA)}
			>
				<ComboboxCommandInput placeholder="Search for an automation..." />
				<ComboboxCommandEmtpy>No automation found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						<ComboboxCommandItem
							selected={selectedAutomationId === INFER_AUTOMATION.value}
							onSelect={setSelectedAutomationId}
							value={INFER_AUTOMATION.value}
						>
							{INFER_AUTOMATION.name}
						</ComboboxCommandItem>
						{MOCK_DATA.map((automation) => (
							<ComboboxCommandItem
								key={automation.id}
								selected={selectedAutomationId === automation.id}
								onSelect={setSelectedAutomationId}
								value={automation.id}
							>
								{automation.name}
							</ComboboxCommandItem>
						))}
					</ComboboxCommandGroup>
				</ComboboxCommandList>
			</ComboboxContent>
		</Combobox>
	);
}

export const story: StoryObj = { name: "Combobox" };
