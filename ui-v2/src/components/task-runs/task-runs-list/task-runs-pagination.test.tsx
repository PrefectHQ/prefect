import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
	type PaginationState,
	TaskRunsPagination,
} from "./task-runs-pagination";

type TaskRunsPaginationProps = ComponentProps<typeof TaskRunsPagination>;

describe("TaskRunsPagination", () => {
	beforeEach(() => {
		mockPointerEvents();
	});

	const createDefaultProps = (
		overrides: Partial<TaskRunsPaginationProps> = {},
	): TaskRunsPaginationProps => ({
		count: 100,
		pages: 10,
		pagination: { limit: 10, page: 1 },
		onChangePagination: vi.fn<(pagination: PaginationState) => void>(),
		onPrefetchPage: vi.fn<(page: number) => void>(),
		...overrides,
	});

	describe("page display", () => {
		it("displays current page and total pages", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 3 } });
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Page 3 of 10")).toBeVisible();
		});

		it("displays 'Page 0 of 0' when pages is zero", () => {
			const props = createDefaultProps({
				count: 0,
				pages: 0,
				pagination: { limit: 10, page: 1 },
			});
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Page 0 of 0")).toBeVisible();
		});

		it("displays correct page info for single page", () => {
			const props = createDefaultProps({
				count: 5,
				pages: 1,
				pagination: { limit: 10, page: 1 },
			});
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Page 1 of 1")).toBeVisible();
		});
	});

	describe("navigation button disabled states", () => {
		it("disables First and Previous buttons on first page", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 1 } });
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to first page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to previous page/i }),
			).toBeDisabled();
		});

		it("enables Next and Last buttons on first page when multiple pages exist", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 1 } });
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to next page/i }),
			).toBeEnabled();
			expect(
				screen.getByRole("button", { name: /go to last page/i }),
			).toBeEnabled();
		});

		it("disables Next and Last buttons on last page", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 10 } });
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to next page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to last page/i }),
			).toBeDisabled();
		});

		it("enables First and Previous buttons on last page", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 10 } });
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to first page/i }),
			).toBeEnabled();
			expect(
				screen.getByRole("button", { name: /go to previous page/i }),
			).toBeEnabled();
		});

		it("enables all navigation buttons on middle page", () => {
			const props = createDefaultProps({ pagination: { limit: 10, page: 5 } });
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to first page/i }),
			).toBeEnabled();
			expect(
				screen.getByRole("button", { name: /go to previous page/i }),
			).toBeEnabled();
			expect(
				screen.getByRole("button", { name: /go to next page/i }),
			).toBeEnabled();
			expect(
				screen.getByRole("button", { name: /go to last page/i }),
			).toBeEnabled();
		});

		it("disables all navigation buttons when there is only one page", () => {
			const props = createDefaultProps({
				count: 5,
				pages: 1,
				pagination: { limit: 10, page: 1 },
			});
			render(<TaskRunsPagination {...props} />);

			expect(
				screen.getByRole("button", { name: /go to first page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to previous page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to next page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to last page/i }),
			).toBeDisabled();
		});
	});

	describe("navigation button clicks", () => {
		it("calls onChangePagination with page 1 when First button is clicked", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("button", { name: /go to first page/i }),
			);

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 10, page: 1 });
		});

		it("calls onChangePagination with previous page when Previous button is clicked", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("button", { name: /go to previous page/i }),
			);

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 10, page: 4 });
		});

		it("calls onChangePagination with next page when Next button is clicked", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("button", { name: /go to next page/i }),
			);

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 10, page: 6 });
		});

		it("calls onChangePagination with last page when Last button is clicked", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("button", { name: /go to last page/i }),
			);

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 10, page: 10 });
		});
	});

	describe("prefetch on hover", () => {
		it("calls onPrefetchPage with page 1 when hovering First button", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to first page/i }),
			);

			expect(onPrefetchPage).toHaveBeenCalledWith(1);
		});

		it("calls onPrefetchPage with previous page when hovering Previous button", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to previous page/i }),
			);

			expect(onPrefetchPage).toHaveBeenCalledWith(4);
		});

		it("calls onPrefetchPage with next page when hovering Next button", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to next page/i }),
			);

			expect(onPrefetchPage).toHaveBeenCalledWith(6);
		});

		it("calls onPrefetchPage with last page when hovering Last button", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to last page/i }),
			);

			expect(onPrefetchPage).toHaveBeenCalledWith(10);
		});

		it("does not call onPrefetchPage when hovering First button on first page", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 1 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to first page/i }),
			);

			expect(onPrefetchPage).not.toHaveBeenCalled();
		});

		it("does not call onPrefetchPage when hovering Previous button on first page", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 1 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to previous page/i }),
			);

			expect(onPrefetchPage).not.toHaveBeenCalled();
		});

		it("does not call onPrefetchPage when hovering Next button on last page", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 10 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to next page/i }),
			);

			expect(onPrefetchPage).not.toHaveBeenCalled();
		});

		it("does not call onPrefetchPage when hovering Last button on last page", async () => {
			const user = userEvent.setup();
			const onPrefetchPage = vi.fn();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 10 },
				onPrefetchPage,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to last page/i }),
			);

			expect(onPrefetchPage).not.toHaveBeenCalled();
		});

		it("works without onPrefetchPage callback", async () => {
			const user = userEvent.setup();
			const props = createDefaultProps({
				pagination: { limit: 10, page: 5 },
				onPrefetchPage: undefined,
			});
			render(<TaskRunsPagination {...props} />);

			await user.hover(
				screen.getByRole("button", { name: /go to next page/i }),
			);
		});
	});

	describe("items per page select", () => {
		it("displays items per page select with current limit", () => {
			const props = createDefaultProps({ pagination: { limit: 25, page: 1 } });
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Items per page")).toBeVisible();
			expect(
				screen.getByRole("combobox", { name: /items per page/i }),
			).toBeVisible();
		});

		it("shows all page size options when select is opened", async () => {
			const user = userEvent.setup();
			const props = createDefaultProps();
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("combobox", { name: /items per page/i }),
			);

			expect(screen.getByRole("option", { name: "5" })).toBeVisible();
			expect(screen.getByRole("option", { name: "10" })).toBeVisible();
			expect(screen.getByRole("option", { name: "25" })).toBeVisible();
			expect(screen.getByRole("option", { name: "50" })).toBeVisible();
			expect(screen.getByRole("option", { name: "100" })).toBeVisible();
		});

		it("calls onChangePagination with new limit when page size is changed", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				count: 100,
				pages: 10,
				pagination: { limit: 10, page: 1 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("combobox", { name: /items per page/i }),
			);
			await user.click(screen.getByRole("option", { name: "25" }));

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 25, page: 1 });
		});

		it("adjusts page when changing to larger page size would exceed total pages", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				count: 100,
				pages: 10,
				pagination: { limit: 10, page: 8 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("combobox", { name: /items per page/i }),
			);
			await user.click(screen.getByRole("option", { name: "25" }));

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 25, page: 4 });
		});

		it("keeps current page when it is still valid after changing page size", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				count: 100,
				pages: 10,
				pagination: { limit: 10, page: 2 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("combobox", { name: /items per page/i }),
			);
			await user.click(screen.getByRole("option", { name: "25" }));

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 25, page: 2 });
		});

		it("sets page to 1 when changing to larger page size with small count", async () => {
			const user = userEvent.setup();
			const onChangePagination = vi.fn();
			const props = createDefaultProps({
				count: 15,
				pages: 3,
				pagination: { limit: 5, page: 3 },
				onChangePagination,
			});
			render(<TaskRunsPagination {...props} />);

			await user.click(
				screen.getByRole("combobox", { name: /items per page/i }),
			);
			await user.click(screen.getByRole("option", { name: "25" }));

			expect(onChangePagination).toHaveBeenCalledWith({ limit: 25, page: 1 });
		});
	});

	describe("edge cases", () => {
		it("handles large page counts", () => {
			const props = createDefaultProps({
				count: 10000,
				pages: 1000,
				pagination: { limit: 10, page: 500 },
			});
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Page 500 of 1000")).toBeVisible();
		});

		it("handles page 1 with zero total pages correctly", () => {
			const props = createDefaultProps({
				count: 0,
				pages: 0,
				pagination: { limit: 10, page: 1 },
			});
			render(<TaskRunsPagination {...props} />);

			expect(screen.getByText("Page 0 of 0")).toBeVisible();
			expect(
				screen.getByRole("button", { name: /go to first page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to previous page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to next page/i }),
			).toBeDisabled();
			expect(
				screen.getByRole("button", { name: /go to last page/i }),
			).toBeDisabled();
		});
	});
});
