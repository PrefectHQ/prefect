import type { Meta, StoryObj } from "@storybook/react";
import { useDeferredValue, useMemo, useState } from "react";
import type { Automation } from "@/api/automations";
import { createFakeAutomation } from "@/mocks";
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

const UNASSIGNED = "UNASSIGNED";

const INFER_AUTOMATION = {
	value: UNASSIGNED,
	name: "Infer Automation" as const,
} as const;

const MOCK_DATA = Array.from({ length: 5 }, createFakeAutomation);

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

function ComboboxStory() {
	const [search, setSearch] = useState("");
	const [selectedAutomationId, setSelectedAutomationId] = useState<
		typeof UNASSIGNED | (string & {})
	>(INFER_AUTOMATION.value);

	const deferredSearch = useDeferredValue(search);

	const filteredData = useMemo(() => {
		return MOCK_DATA.filter((automation) =>
			automation.name.toLowerCase().includes(deferredSearch.toLowerCase()),
		);
	}, [deferredSearch]);

	const isInferredOptionFiltered = INFER_AUTOMATION.name
		.toLowerCase()
		.includes(deferredSearch.toLowerCase());

	const buttonLabel = getButtonLabel(MOCK_DATA, selectedAutomationId);

	return (
		<Combobox>
			<ComboboxTrigger selected={Boolean(buttonLabel)}>
				{buttonLabel ?? "Select automation"}
			</ComboboxTrigger>
			<ComboboxContent>
				<ComboboxCommandInput
					value={search}
					onValueChange={setSearch}
					placeholder="Search for an automation..."
				/>
				<ComboboxCommandEmtpy>No automation found</ComboboxCommandEmtpy>
				<ComboboxCommandList>
					<ComboboxCommandGroup>
						{isInferredOptionFiltered && (
							<ComboboxCommandItem
								selected={selectedAutomationId === INFER_AUTOMATION.value}
								onSelect={(value) => {
									setSelectedAutomationId(value);
									setSearch("");
								}}
								value={INFER_AUTOMATION.value}
							>
								{INFER_AUTOMATION.name}
							</ComboboxCommandItem>
						)}
						{filteredData.map((automation) => (
							<ComboboxCommandItem
								key={automation.id}
								selected={selectedAutomationId === automation.id}
								onSelect={(value) => {
									setSelectedAutomationId(value);
									setSearch("");
								}}
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
