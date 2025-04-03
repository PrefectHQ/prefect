import { Toaster } from "@/components/ui/sonner";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createWrapper } from "@tests/utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BlocksRowCount } from "./blocks-row-count";

describe("BlocksRowCount", () => {
	beforeEach(() => {
		// Mocks away getRouteApi dependency in `useDeleteDeploymentConfirmationDialog`
		// @ts-expect-error Ignoring error until @tanstack/react-router has better testing documentation. Ref: https://vitest.dev/api/vi.html#vi-mock
		vi.mock(import("@tanstack/react-router"), async (importOriginal) => {
			const mod = await importOriginal();
			return {
				...mod,
				getRouteApi: () => ({
					useNavigate: vi.fn,
				}),
			};
		});
	});

	it("renders total count when there is no selected values", () => {
		// ------------ Setup
		render(
			<BlocksRowCount
				count={101}
				setRowSelection={vi.fn()}
				rowSelection={{}}
			/>,
			{ wrapper: createWrapper() },
		);
		// ------------ Assert
		expect(screen.getByText("101 Blocks")).toBeVisible();
	});

	it("able to delete selected rows", async () => {
		const user = userEvent.setup();
		const mockSetRowSelection = vi.fn();
		// ------------ Setup
		render(
			<>
				<Toaster />
				<BlocksRowCount
					count={1}
					setRowSelection={mockSetRowSelection}
					rowSelection={{ "1": true, "2": true }}
				/>
			</>,
			{ wrapper: createWrapper() },
		);

		// ------------ Act
		expect(screen.getByText("2 selected")).toBeVisible();
		await user.click(screen.getByRole("button", { name: /Delete rows/i }));
		expect(
			screen.getByText(
				"Are you sure you want to delete these 2 selected blocks?",
			),
		).toBeVisible();
		await user.click(screen.getByRole("button", { name: /Delete/i }));

		// ------------ Assert
		await waitFor(() =>
			expect(screen.getByText(/blocks deleted/i)).toBeVisible(),
		);
		expect(mockSetRowSelection).toHaveBeenLastCalledWith({});
	});
});
