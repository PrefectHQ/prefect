import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import {
	type SavedFilter,
	SavedFiltersMenu,
	type SavedFiltersMenuProps,
} from "./saved-filters-menu";

describe("SavedFiltersMenu", () => {
	beforeAll(mockPointerEvents);

	const createMockFilter = (
		overrides: Partial<SavedFilter> = {},
	): SavedFilter => ({
		id: "filter-1",
		name: "Test Filter",
		isDefault: false,
		...overrides,
	});

	const defaultProps: SavedFiltersMenuProps = {
		currentFilter: null,
		savedFilters: [],
		onSelect: vi.fn(),
		onSave: vi.fn(),
		onDelete: vi.fn(),
		onSetDefault: vi.fn(),
		onRemoveDefault: vi.fn(),
	};

	const renderComponent = (props: Partial<SavedFiltersMenuProps> = {}) => {
		return render(<SavedFiltersMenu {...defaultProps} {...props} />);
	};

	describe("trigger button", () => {
		it("displays 'Custom' when currentFilter is null", () => {
			renderComponent({ currentFilter: null });
			expect(screen.getByRole("button", { name: /custom/i })).toBeVisible();
		});

		it("displays filter name when currentFilter is provided", () => {
			const filter = createMockFilter({ name: "My Saved Filter" });
			renderComponent({ currentFilter: filter });
			expect(
				screen.getByRole("button", { name: /my saved filter/i }),
			).toBeVisible();
		});

		it("displays 'Custom' for custom filter", () => {
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({ currentFilter: filter });
			expect(screen.getByRole("button", { name: /custom/i })).toBeVisible();
		});

		it("displays 'Unsaved' for unsaved filter", () => {
			const filter = createMockFilter({ name: "Unsaved", id: null });
			renderComponent({ currentFilter: filter });
			expect(screen.getByRole("button", { name: /unsaved/i })).toBeVisible();
		});
	});

	describe("dropdown menu", () => {
		it("opens dropdown when trigger is clicked", async () => {
			const user = userEvent.setup();
			const filters = [
				createMockFilter({ id: "1", name: "Filter 1" }),
				createMockFilter({ id: "2", name: "Filter 2" }),
			];
			renderComponent({ savedFilters: filters });

			await user.click(screen.getByRole("button", { name: /custom/i }));

			expect(screen.getByRole("menuitem", { name: /filter 1/i })).toBeVisible();
			expect(screen.getByRole("menuitem", { name: /filter 2/i })).toBeVisible();
		});

		it("calls onSelect when a filter is clicked", async () => {
			const user = userEvent.setup();
			const onSelect = vi.fn();
			const filters = [createMockFilter({ id: "1", name: "Filter 1" })];
			renderComponent({ savedFilters: filters, onSelect });

			await user.click(screen.getByRole("button", { name: /custom/i }));
			await user.click(screen.getByRole("menuitem", { name: /filter 1/i }));

			expect(onSelect).toHaveBeenCalledWith(filters[0]);
		});

		it("shows default indicator for default filter", async () => {
			const user = userEvent.setup();
			const filters = [
				createMockFilter({ id: "1", name: "Default Filter", isDefault: true }),
			];
			renderComponent({ savedFilters: filters });

			await user.click(screen.getByRole("button", { name: /custom/i }));

			const menuItem = screen.getByRole("menuitem", {
				name: /default filter/i,
			});
			expect(menuItem).toBeVisible();
		});
	});

	describe("save action", () => {
		it("shows save action for custom filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /custom/i }));

			expect(
				screen.getByRole("menuitem", { name: /save current filters/i }),
			).toBeVisible();
		});

		it("shows save action for unsaved filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Unsaved", id: null });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /unsaved/i }));

			expect(
				screen.getByRole("menuitem", { name: /save current filters/i }),
			).toBeVisible();
		});

		it("hides save action for saved filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));

			expect(
				screen.queryByRole("menuitem", { name: /save current filters/i }),
			).not.toBeInTheDocument();
		});

		it("calls onSave when save action is clicked", async () => {
			const user = userEvent.setup();
			const onSave = vi.fn();
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({ currentFilter: filter, onSave });

			await user.click(screen.getByRole("button", { name: /custom/i }));
			await user.click(
				screen.getByRole("menuitem", { name: /save current filters/i }),
			);

			expect(onSave).toHaveBeenCalled();
		});

		it("hides save action when canSave permission is false", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({
				currentFilter: filter,
				permissions: { canSave: false, canDelete: true },
			});

			await user.click(screen.getByRole("button", { name: /custom/i }));

			expect(
				screen.queryByRole("menuitem", { name: /save current filters/i }),
			).not.toBeInTheDocument();
		});
	});

	describe("delete action", () => {
		it("shows delete action for saved filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));

			expect(screen.getByRole("menuitem", { name: /delete/i })).toBeVisible();
		});

		it("hides delete action for custom filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /custom/i }));

			expect(
				screen.queryByRole("menuitem", { name: /^delete$/i }),
			).not.toBeInTheDocument();
		});

		it("opens delete confirmation dialog when delete is clicked", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));
			await user.click(screen.getByRole("menuitem", { name: /delete/i }));

			await waitFor(() => {
				expect(
					screen.getByRole("alertdialog", { name: /delete saved filter/i }),
				).toBeVisible();
			});
		});

		it("calls onDelete when delete is confirmed", async () => {
			const user = userEvent.setup();
			const onDelete = vi.fn();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({ currentFilter: filter, onDelete });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));
			await user.click(screen.getByRole("menuitem", { name: /delete/i }));

			await waitFor(() => {
				expect(
					screen.getByRole("alertdialog", { name: /delete saved filter/i }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("button", { name: /^delete$/i }));

			expect(onDelete).toHaveBeenCalledWith("123");
		});

		it("closes dialog when cancel is clicked", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));
			await user.click(screen.getByRole("menuitem", { name: /delete/i }));

			await waitFor(() => {
				expect(
					screen.getByRole("alertdialog", { name: /delete saved filter/i }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("button", { name: /cancel/i }));

			await waitFor(() => {
				expect(
					screen.queryByRole("alertdialog", { name: /delete saved filter/i }),
				).not.toBeInTheDocument();
			});
		});

		it("hides delete action when canDelete permission is false", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Saved Filter", id: "123" });
			renderComponent({
				currentFilter: filter,
				permissions: { canSave: true, canDelete: false },
			});

			await user.click(screen.getByRole("button", { name: /saved filter/i }));

			expect(
				screen.queryByRole("menuitem", { name: /^delete$/i }),
			).not.toBeInTheDocument();
		});
	});

	describe("set default action", () => {
		it("shows 'Set as default' for non-default saved filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({
				name: "Saved Filter",
				id: "123",
				isDefault: false,
			});
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));

			expect(
				screen.getByRole("menuitem", { name: /set as default/i }),
			).toBeVisible();
		});

		it("shows 'Remove as default' for default filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({
				name: "Default Filter",
				id: "123",
				isDefault: true,
			});
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /default filter/i }));

			expect(
				screen.getByRole("menuitem", { name: /remove as default/i }),
			).toBeVisible();
		});

		it("hides toggle default for custom filter", async () => {
			const user = userEvent.setup();
			const filter = createMockFilter({ name: "Custom", id: null });
			renderComponent({ currentFilter: filter });

			await user.click(screen.getByRole("button", { name: /custom/i }));

			expect(
				screen.queryByRole("menuitem", { name: /set as default/i }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("menuitem", { name: /remove as default/i }),
			).not.toBeInTheDocument();
		});

		it("calls onSetDefault when 'Set as default' is clicked", async () => {
			const user = userEvent.setup();
			const onSetDefault = vi.fn();
			const filter = createMockFilter({
				name: "Saved Filter",
				id: "123",
				isDefault: false,
			});
			renderComponent({ currentFilter: filter, onSetDefault });

			await user.click(screen.getByRole("button", { name: /saved filter/i }));
			await user.click(
				screen.getByRole("menuitem", { name: /set as default/i }),
			);

			expect(onSetDefault).toHaveBeenCalledWith("123");
		});

		it("calls onRemoveDefault when 'Remove as default' is clicked", async () => {
			const user = userEvent.setup();
			const onRemoveDefault = vi.fn();
			const filter = createMockFilter({
				name: "Default Filter",
				id: "123",
				isDefault: true,
			});
			renderComponent({ currentFilter: filter, onRemoveDefault });

			await user.click(screen.getByRole("button", { name: /default filter/i }));
			await user.click(
				screen.getByRole("menuitem", { name: /remove as default/i }),
			);

			expect(onRemoveDefault).toHaveBeenCalledWith("123");
		});
	});
});
