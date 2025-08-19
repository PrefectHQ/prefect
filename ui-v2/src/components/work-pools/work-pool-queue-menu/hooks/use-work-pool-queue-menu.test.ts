import { act, renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";
import { createFakeWorkPoolQueue } from "@/mocks";
import { useWorkPoolQueueMenu } from "./use-work-pool-queue-menu";

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

// Mock console.log since the hook has TODO console logs
vi.spyOn(console, "log").mockImplementation(() => {});

describe("useWorkPoolQueueMenu", () => {
	const defaultQueue = createFakeWorkPoolQueue({
		id: "test-id",
		name: "test-queue",
		work_pool_name: "test-pool",
	});

	it("returns correct menu structure", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		expect(result.current.menuItems).toHaveLength(4);
		expect(result.current.showDeleteDialog).toBe(false);
		expect(result.current.setShowDeleteDialog).toBeInstanceOf(Function);
		expect(result.current.triggerIcon).toBeDefined();
	});

	it("includes copy ID menu item", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const copyItem = result.current.menuItems.find(
			(item) => item.label === "Copy ID",
		);
		expect(copyItem).toBeDefined();
		expect(copyItem?.show).toBe(true);
	});

	it("includes edit menu item", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const editItem = result.current.menuItems.find(
			(item) => item.label === "Edit",
		);
		expect(editItem).toBeDefined();
		expect(editItem?.show).toBe(true);
	});

	it("includes automate menu item", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const automateItem = result.current.menuItems.find(
			(item) => item.label === "Automate",
		);
		expect(automateItem).toBeDefined();
		expect(automateItem?.show).toBe(true);
	});

	it("includes delete menu item for non-default queue", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const deleteItem = result.current.menuItems.find(
			(item) => item.label === "Delete",
		);
		expect(deleteItem).toBeDefined();
		expect(deleteItem?.show).toBe(true);
		expect(deleteItem?.variant).toBe("destructive");
	});

	it("hides delete menu item for default queue", () => {
		const defaultQueue = createFakeWorkPoolQueue({
			name: "default",
			work_pool_name: "test-pool",
		});

		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const deleteItem = result.current.menuItems.find(
			(item) => item.label === "Delete",
		);
		expect(deleteItem).toBeUndefined();
	});

	it("copies ID to clipboard and shows toast", () => {
		// Mock clipboard API
		const mockClipboard = {
			writeText: vi.fn().mockResolvedValue(undefined),
		};
		Object.assign(navigator, { clipboard: mockClipboard });
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const copyItem = result.current.menuItems.find(
			(item) => item.label === "Copy ID",
		);

		act(() => {
			if (copyItem) {
				copyItem.action();
			}
		});

		expect(mockClipboard.writeText).toHaveBeenCalledWith("test-id");
		expect(toast.success).toHaveBeenCalledWith("ID copied to clipboard");
	});

	it("handles edit action", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const editItem = result.current.menuItems.find(
			(item) => item.label === "Edit",
		);

		act(() => {
			editItem?.action();
		});

		expect(console.log).toHaveBeenCalledWith("Edit queue:", "test-queue");
	});

	it("navigates to automation creation on automate action", async () => {
		const mockNavigate = vi.fn();
		const { useNavigate } = await import("@tanstack/react-router");
		vi.mocked(useNavigate).mockReturnValue(mockNavigate);

		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

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
		});
	});

	it("opens delete dialog when delete action is triggered", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		const deleteItem = result.current.menuItems.find(
			(item) => item.label === "Delete",
		);

		act(() => {
			deleteItem?.action();
		});

		expect(result.current.showDeleteDialog).toBe(true);
	});

	it("can close delete dialog", () => {
		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		// First open the dialog
		act(() => {
			const deleteItem = result.current.menuItems.find(
				(item) => item.label === "Delete",
			);
			deleteItem?.action();
		});

		expect(result.current.showDeleteDialog).toBe(true);

		// Then close it
		act(() => {
			result.current.setShowDeleteDialog(false);
		});

		expect(result.current.showDeleteDialog).toBe(false);
	});

	it("filters out hidden menu items", () => {
		const defaultQueue = createFakeWorkPoolQueue({
			name: "default", // This will hide the delete item
			work_pool_name: "test-pool",
		});

		const { result } = renderHook(() => useWorkPoolQueueMenu(defaultQueue));

		// Should have 3 items (Copy ID, Edit, Automate) but not Delete
		expect(result.current.menuItems).toHaveLength(3);
		expect(result.current.menuItems.map((item) => item.label)).toEqual([
			"Copy ID",
			"Edit",
			"Automate",
		]);
	});

	it("handles different queue names correctly", () => {
		// Mock clipboard API
		const mockClipboard = {
			writeText: vi.fn().mockResolvedValue(undefined),
		};
		Object.assign(navigator, { clipboard: mockClipboard });

		const customQueue = createFakeWorkPoolQueue({
			id: "custom-id",
			name: "my-custom-queue",
			work_pool_name: "my-pool",
		});

		const { result } = renderHook(() => useWorkPoolQueueMenu(customQueue));

		const copyItem = result.current.menuItems.find(
			(item) => item.label === "Copy ID",
		);

		act(() => {
			if (copyItem) {
				copyItem.action();
			}
		});

		expect(mockClipboard.writeText).toHaveBeenCalledWith("custom-id");

		const editItem = result.current.menuItems.find(
			(item) => item.label === "Edit",
		);

		act(() => {
			editItem?.action();
		});

		expect(console.log).toHaveBeenCalledWith("Edit queue:", "my-custom-queue");
	});
});
