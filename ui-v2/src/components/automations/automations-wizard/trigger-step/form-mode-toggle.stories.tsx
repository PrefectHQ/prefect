import type { Meta, StoryObj } from "@storybook/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { reactQueryDecorator, routerDecorator } from "@/storybook/utils";
import { FormModeToggle } from "./form-mode-toggle";

const meta = {
	title: "Components/Automations/Wizard/FormModeToggle",
	component: FormModeToggle,
	decorators: [reactQueryDecorator, routerDecorator],
} satisfies Meta<typeof FormModeToggle>;

export default meta;

type Story = StoryObj<typeof meta>;

const SampleFormContent = (
	<Card>
		<CardHeader>
			<CardTitle>Form Mode</CardTitle>
		</CardHeader>
		<CardContent>
			<p>This is the form-based editing interface.</p>
		</CardContent>
	</Card>
);

const SampleJsonContent = (
	<Card>
		<CardHeader>
			<CardTitle>JSON Mode</CardTitle>
		</CardHeader>
		<CardContent>
			<pre className="bg-muted p-4 rounded">
				{JSON.stringify({ example: "json content" }, null, 2)}
			</pre>
		</CardContent>
	</Card>
);

export const FormSelected: Story = {
	args: {
		formContent: SampleFormContent,
		jsonContent: SampleJsonContent,
	},
};

export const JSONSelected: Story = {
	args: {
		defaultValue: "JSON",
		formContent: SampleFormContent,
		jsonContent: SampleJsonContent,
	},
};

export const Interactive: Story = {
	args: {
		formContent: SampleFormContent,
		jsonContent: SampleJsonContent,
	},
};
