import type { Meta, StoryObj } from "@storybook/react";
import { DetailRich } from "./detail-rich";

const meta: Meta<typeof DetailRich> = {
	title: "Components/Artifacts/DetailRich",
	component: DetailRich,
};

export default meta;
type Story = StoryObj<typeof DetailRich>;

export const Default: Story = {
	args: {
		richData: {
			html: `<html><head><style>body { font-family: sans-serif; padding: 16px; } .tag { color: #0070f3; }</style></head><body><h2>Rich Artifact</h2><p>This is a <span class="tag">sandboxed</span> rich artifact preview.</p></body></html>`,
			sandbox: ["allow-scripts"],
		},
	},
};

export const WithCsp: Story = {
	args: {
		richData: {
			html: "<html><head></head><body><h3>CSP enabled preview</h3></body></html>",
			sandbox: ["allow-scripts"],
			csp: "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
		},
	},
};

export const InvalidPayload: Story = {
	args: {
		richData: {
			message: "invalid payload shape",
		},
	},
};
