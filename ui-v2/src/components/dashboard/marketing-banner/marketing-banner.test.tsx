import { render, screen, waitFor } from "@testing-library/react";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";
import { createFakeServerSettings } from "@/mocks";
import { DashboardMarketingBanner } from "./marketing-banner";

const defaultProps = {
	title: "Ready to scale?",
	subtitle:
		"Webhooks, role and object-level security, and serverless push work pools on Prefect Cloud",
	actions: <Button>Upgrade to Cloud</Button>,
};

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

describe("DashboardMarketingBanner", () => {
	it("renders banner content when show_promotional_content is true", async () => {
		server.use(
			http.get(buildApiUrl("/admin/settings"), () => {
				return HttpResponse.json(mockSettings(true));
			}),
		);

		render(<DashboardMarketingBanner {...defaultProps} />, {
			wrapper: createWrapper(),
		});

		await waitFor(() => {
			expect(screen.getByText("Ready to scale?")).toBeInTheDocument();
		});
		expect(
			screen.getByText(
				"Webhooks, role and object-level security, and serverless push work pools on Prefect Cloud",
			),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: "Upgrade to Cloud" }),
		).toBeInTheDocument();
	});

	it("hides banner when show_promotional_content is false", async () => {
		server.use(
			http.get(buildApiUrl("/admin/settings"), () => {
				return HttpResponse.json(mockSettings(false));
			}),
		);

		const { container } = render(
			<DashboardMarketingBanner {...defaultProps} />,
			{ wrapper: createWrapper() },
		);

		await waitFor(() => {
			expect(container.firstChild).toBeNull();
		});
		expect(screen.queryByText("Ready to scale?")).not.toBeInTheDocument();
	});

	it("renders nothing while settings are loading", () => {
		server.use(
			http.get(buildApiUrl("/admin/settings"), async () => {
				await new Promise((resolve) => setTimeout(resolve, 100));
				return HttpResponse.json(mockSettings(false));
			}),
		);

		const { container } = render(
			<DashboardMarketingBanner {...defaultProps} />,
			{ wrapper: createWrapper() },
		);

		expect(container.firstChild).toBeNull();
		expect(screen.queryByText("Ready to scale?")).not.toBeInTheDocument();
	});
});
