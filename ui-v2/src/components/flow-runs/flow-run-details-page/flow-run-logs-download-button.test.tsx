import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunLogsDownloadButton } from "./flow-run-logs-download-button";

const mockCreateObjectURL = vi.fn(() => "blob:mock-url");
const mockRevokeObjectURL = vi.fn();
Object.defineProperty(URL, "createObjectURL", { value: mockCreateObjectURL });
Object.defineProperty(URL, "revokeObjectURL", { value: mockRevokeObjectURL });

const renderButton = (flowRunOverrides = {}) => {
	const flowRun = createFakeFlowRun(flowRunOverrides);
	return render(
		<TooltipProvider>
			<FlowRunLogsDownloadButton flowRun={flowRun} />
		</TooltipProvider>,
		{
			wrapper: createWrapper(),
		},
	);
};

describe("FlowRunLogsDownloadButton", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		server.use(
			http.get(buildApiUrl("/flow_runs/:id/logs/download"), () => {
				return new HttpResponse(
					new Blob(["timestamp,level,message\n2024-01-01,INFO,Test log"], {
						type: "text/csv",
					}),
					{
						headers: { "Content-Type": "text/csv" },
					},
				);
			}),
		);
	});

	it("renders download button", () => {
		renderButton();
		expect(
			screen.getByRole("button", { name: "Download logs" }),
		).toBeInTheDocument();
	});

	it("shows tooltip on hover", async () => {
		renderButton();
		const user = userEvent.setup();

		await user.hover(screen.getByRole("button"));
		await waitFor(() => {
			expect(screen.getByRole("tooltip")).toHaveTextContent(
				"Download all logs as CSV",
			);
		});
	});

	it("triggers download on click", async () => {
		const mockClick = vi.fn();
		HTMLAnchorElement.prototype.click = mockClick;

		renderButton({ name: "test-flow-run" });
		const user = userEvent.setup();

		await user.click(screen.getByRole("button"));

		await waitFor(() => {
			expect(mockClick).toHaveBeenCalled();
			expect(mockCreateObjectURL).toHaveBeenCalled();
			expect(mockRevokeObjectURL).toHaveBeenCalled();
		});
	});
});
