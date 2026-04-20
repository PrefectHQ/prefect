import type { Meta, StoryObj } from "@storybook/react";
import { PrefectLoading } from "./index";

const meta: Meta<typeof PrefectLoading> = {
	title: "UI/PrefectLoading",
	component: PrefectLoading,
	parameters: {
		docs: {
			description: {
				component:
					"Full-page loading component with animated Prefect logo. Use this for route-level loading states like auth initialization.",
			},
		},
		layout: "fullscreen",
	},
};
export default meta;

export const Default: StoryObj<typeof PrefectLoading> = {
	name: "PrefectLoading",
};
