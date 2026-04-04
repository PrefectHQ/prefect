import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useQuickRun } from "@/components/deployments/use-quick-run";

const createDeploymentFlowRun = vi.fn();

vi.mock("@/api/flow-runs", () => ({
	useDeploymentCreateFlowRun: () => ({
		createDeploymentFlowRun,
		isPending: false,
	}),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
	},
}));

describe("useQuickRun", () => {
	beforeEach(() => {
		createDeploymentFlowRun.mockReset();
		vi.mocked(toast.success).mockReset();
	});

	it("calls provided onSuccess callback with flow run id", () => {
		const callback = vi.fn();
		createDeploymentFlowRun.mockImplementation(
			(
				_payload: unknown,
				options?: { onSuccess?: (res: { id: string; name: string }) => void },
			) => {
				options?.onSuccess?.({ id: "flow-run-id", name: "test-run" });
			},
		);

		const { result } = renderHook(() => useQuickRun({ onSuccess: callback }));
		result.current.onQuickRun("deployment-id");

		expect(callback).toHaveBeenCalledWith("flow-run-id");
		expect(toast.success).toHaveBeenCalledOnce();
	});
});
