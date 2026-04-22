import { act, renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPool } from "@/mocks";
import { useWorkPoolMenu } from "./use-work-pool-menu";

// Mock dependencies
vi.mock("@tanstack/react-router", () => ({
	useNavigate: vi.fn(() => vi.fn()),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
	},
}));

// Mock clipboard API
Object.assign(navigator, {
	clipboard: {
		writeText: vi.fn().mockResolvedValue(undefined),
	},
});

describe("useWorkPoolMenu", () => {
	const defaultWorkPool = createFakeWorkPool({
		id: "test-pool-id",
		name: "test-pool",
	});

	it("returns correct menu structure", () => {
		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		expect(result.current.menuItems).toHaveLength(4);
		expect(result.current.showDeleteDialog).toBe(false);
		expect(result.current.setShowDeleteDialog).toBeInstanceOf(Function);
		expect(result.current.triggerIcon).toBeDefined();
	});

	it("includes copy ID menu item", () => {
		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const copyItem = result.current.menuItems.find(
			(item) => item.label === "Copy ID",
		);
		expect(copyItem).toBeDefined();
		expect(copyItem?.show).toBe(true);
	});

	it("includes automate menu item", () => {
		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const automateItem = result.current.menuItems.find(
			(item) => item.label === "Automate",
		);
		expect(automateItem).toBeDefined();
		expect(automateItem?.show).toBe(true);
	});

	it("copies ID to clipboard and shows toast", () => {
		const mockClipboard = {
			writeText: vi.fn().mockResolvedValue(undefined),
		};
		Object.assign(navigator, { clipboard: mockClipboard });
		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const copyItem = result.current.menuItems.find(
			(item) => item.label === "Copy ID",
		);

		act(() => {
			if (copyItem) {
				copyItem.action();
			}
		});

		expect(mockClipboard.writeText).toHaveBeenCalledWith("test-pool-id");
		expect(toast.success).toHaveBeenCalledWith("ID copied to clipboard");
	});

	it("navigates to automation creation with trigger search params", async () => {
		const mockNavigate = vi.fn();
		const { useNavigate } = await import("@tanstack/react-router");
		vi.mocked(useNavigate).mockReturnValue(mockNavigate);

		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const automateItem = result.current.menuItems.find(
			(item) => item.label === "Automate",
		);

		act(() => {
			if (automateItem) {
				automateItem.action();
			}
		});

		expect(mockNavigate).toHaveBeenCalledWith({
			to: "/automations/create",
			search: {
				trigger: {
					type: "event",
					posture: "Reactive",
					match: {
						"prefect.resource.id": `prefect.work-pool.${defaultWorkPool.id}`,
					},
					for_each: ["prefect.resource.id"],
					expect: ["prefect.work-pool.not-ready"],
					threshold: 1,
					within: 0,
				},
			},
		});
	});

	it("opens delete dialog when delete action is triggered", () => {
		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const deleteItem = result.current.menuItems.find(
			(item) => item.label === "Delete",
		);

		act(() => {
			deleteItem?.action();
		});

		expect(result.current.showDeleteDialog).toBe(true);
	});

	it("navigates to edit page when edit action is triggered", async () => {
		const mockNavigate = vi.fn();
		const { useNavigate } = await import("@tanstack/react-router");
		vi.mocked(useNavigate).mockReturnValue(mockNavigate);

		const { result } = renderHook(() => useWorkPoolMenu(defaultWorkPool));

		const editItem = result.current.menuItems.find(
			(item) => item.label === "Edit",
		);

		act(() => {
			editItem?.action();
		});

		expect(mockNavigate).toHaveBeenCalledWith({
			to: "/work-pools/work-pool/$workPoolName/edit",
			params: { workPoolName: defaultWorkPool.name },
		});
	});
});
