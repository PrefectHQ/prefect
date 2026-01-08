import type { Meta, StoryObj } from "@storybook/react";
import { reactQueryDecorator } from "@/storybook/utils";
import { LoginPage } from "./login-page";

const meta = {
	title: "Components/Auth/LoginPage",
	component: LoginPage,
	decorators: [reactQueryDecorator],
	parameters: {
		layout: "fullscreen",
	},
} satisfies Meta<typeof LoginPage>;

export default meta;

type Story = StoryObj<typeof LoginPage>;

export const Default: Story = {
	name: "Default",
};

export const WithCustomRedirect: Story = {
	name: "With Custom Redirect",
	args: {
		redirectTo: "/flows",
	},
};
