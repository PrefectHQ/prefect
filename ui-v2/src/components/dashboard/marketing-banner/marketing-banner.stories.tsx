import type { Meta, StoryObj } from "@storybook/react";
import { buildApiUrl } from "@tests/utils/handlers";
import { HttpResponse, http } from "msw";
import { Button } from "@/components/ui/button";
import { createFakeServerSettings } from "@/mocks";
import { reactQueryDecorator } from "@/storybook/utils";
import { DashboardMarketingBanner } from "./marketing-banner";

const upgradeUrl =
	"https://prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss&utm_term=none&utm_content=none";

const mockSettings = (showPromotionalContent: boolean) => {
	const base = createFakeServerSettings();
	const baseServer = base.server as Record<string, unknown>;
	const baseUi = baseServer.ui as Record<string, unknown>;
	return {
		...base,
		server: {
			...baseServer,
			ui: { ...baseUi, show_promotional_content: showPromotionalContent },
		},
	};
};

const meta: Meta<typeof DashboardMarketingBanner> = {
	title: "Components/Dashboard/DashboardMarketingBanner",
	component: DashboardMarketingBanner,
	decorators: [reactQueryDecorator],
	parameters: {
		layout: "padded",
	},
	args: {
		title: "Ready to scale?",
		subtitle:
			"Webhooks, role and object-level security, and serverless push work pools on Prefect Cloud",
		actions: (
			<a href={upgradeUrl} target="_blank" rel="noreferrer">
				<Button>Upgrade to Cloud</Button>
			</a>
		),
	},
};

export default meta;
type Story = StoryObj<typeof DashboardMarketingBanner>;

export const PromotionalContentEnabled: Story = {
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/admin/settings"), () => {
					return HttpResponse.json(mockSettings(true));
				}),
			],
		},
	},
};

export const PromotionalContentDisabled: Story = {
	parameters: {
		msw: {
			handlers: [
				http.get(buildApiUrl("/admin/settings"), () => {
					return HttpResponse.json(mockSettings(false));
				}),
			],
		},
	},
};
