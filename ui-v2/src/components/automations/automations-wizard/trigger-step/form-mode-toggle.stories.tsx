import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FormModeToggle } from "./form-mode-toggle";

const meta = {
	title: "Components/Automations/Wizard/FormModeToggle",
	component: FormModeToggle,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof FormModeToggle>;

export default meta;

type Story = StoryObj<typeof meta>;

export const FormSelected: Story = {
	args: {
		value: "Form",
		onValueChange: () => {},
	},
};

export const JSONSelected: Story = {
	args: {
		value: "JSON",
		onValueChange: () => {},
	},
};

export const Interactive: Story = {
	args: {
		value: "Form",
		onValueChange: () => {},
	},
	render: () => <InteractiveFormModeToggle />,
};

function InteractiveFormModeToggle() {
	const [mode, setMode] = useState<"Form" | "JSON">("Form");

	return <FormModeToggle value={mode} onValueChange={setMode} />;
}
