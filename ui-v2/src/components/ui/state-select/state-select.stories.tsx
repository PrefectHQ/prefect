import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import type { components } from "@/api/prefect";
import { StateSelect } from ".";

type StateType = components["schemas"]["StateType"];

const meta: Meta<typeof StateSelect> = {
	title: "UI/StateSelect",
	component: StateSelect,
};
export default meta;

type Story = StoryObj<typeof StateSelect>;

const StateSelectDefault = () => {
	const [value, setValue] = useState<StateType | undefined>(undefined);
	return <StateSelect value={value} onValueChange={setValue} />;
};

export const Default: Story = {
	name: "Default (All States)",
	render: () => <StateSelectDefault />,
};

const StateSelectTerminalOnly = () => {
	const [value, setValue] = useState<StateType | undefined>(undefined);
	return <StateSelect value={value} onValueChange={setValue} terminalOnly />;
};

export const TerminalOnly: Story = {
	name: "Terminal States Only",
	render: () => <StateSelectTerminalOnly />,
};

const StateSelectWithValue = () => {
	const [value, setValue] = useState<StateType | undefined>("COMPLETED");
	return <StateSelect value={value} onValueChange={setValue} />;
};

export const WithSelectedValue: Story = {
	name: "With Pre-selected Value",
	render: () => <StateSelectWithValue />,
};

const StateSelectWithExclude = () => {
	const [value, setValue] = useState<StateType | undefined>(undefined);
	return (
		<StateSelect
			value={value}
			onValueChange={setValue}
			excludeState="RUNNING"
		/>
	);
};

export const WithExcludedState: Story = {
	name: "With Excluded State (Running)",
	render: () => <StateSelectWithExclude />,
};
