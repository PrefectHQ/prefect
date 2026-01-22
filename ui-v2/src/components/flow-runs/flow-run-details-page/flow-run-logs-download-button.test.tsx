import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createFakeFlowRun } from "@/mocks";
import { FlowRunLogsDownloadButton } from "./flow-run-logs-download-button";

vi.mock("@/api/service", () => ({
	getQueryService: vi.fn(() =>
		Promise.resolve({
			GET: vi.fn(() =>
				Promise.resolve({
					data: new Blob(["test,data"], { type: "text/csv" }),
				}),
			),
		}),
	),
}));

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
