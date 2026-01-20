import type { Meta, StoryObj } from "@storybook/react";
import { ColorModeSelect } from "./color-mode-select";

const meta = {
	title: "Components/Settings/ColorModeSelect",
	component: ColorModeSelect,
} satisfies Meta<typeof ColorModeSelect>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
