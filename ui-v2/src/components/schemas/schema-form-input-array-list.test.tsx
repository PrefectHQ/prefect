import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import type { SchemaObject } from "openapi-typescript";
import { useState } from "react";
import { beforeAll, describe, expect, test, vi } from "vitest";
import type { SchemaFormProps } from "./schema-form";
import { SchemaForm } from "./schema-form";

function TestSchemaForm({
	schema = { type: "object", properties: {} },
	kinds = [],
	errors = [],
	values = {},
	onValuesChange = () => {},
}: Partial<SchemaFormProps>) {
	return (
		<SchemaForm
			schema={schema}
			kinds={kinds}
			errors={errors}
			values={values}
			onValuesChange={onValuesChange}
		/>
	);
}

describe("SchemaFormInputArrayList", () => {
	beforeAll(mockPointerEvents);

	describe("drag handles", () => {
		test("renders drag handles for regular array items", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["foo", "bar", "baz"] }}
				/>,
			);

			const dragHandles = screen.getAllByRole("button", {
				name: "Drag to reorder",
			});
			expect(dragHandles).toHaveLength(3);
		});

		test("does not render drag handles for prefix items", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						prefixItems: [
							{ type: "string", title: "First" },
							{ type: "boolean", title: "Second" },
						],
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["prefix1", true, "regular1", "regular2"] }}
				/>,
			);

			// Only regular items (2) should have drag handles, not prefix items (2)
			const dragHandles = screen.getAllByRole("button", {
				name: "Drag to reorder",
			});
			expect(dragHandles).toHaveLength(2);
		});

		test("drag handles have correct aria-label for accessibility", () => {
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm schema={schema} values={{ items: ["foo", "bar"] }} />,
			);

			const dragHandles = screen.getAllByRole("button", {
				name: "Drag to reorder",
			});
			dragHandles.forEach((handle) => {
				expect(handle).toHaveAttribute("aria-label", "Drag to reorder");
			});
		});
	});

	describe("move up/down menu options", () => {
		test("move up and move down options are available in menu for regular items", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["foo", "bar", "baz"] }}
				/>,
			);

			// Find all menu trigger buttons (the ones with "Open menu")
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });
			expect(menuButtons.length).toBeGreaterThan(0);

			// Click the second array item's menu (index 2 - after property menu and first item menu)
			await user.click(menuButtons[2]);

			// Check that move up and move down options exist
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move up/i }),
				).toBeVisible();
			});
			expect(
				screen.getByRole("menuitem", { name: /move down/i }),
			).toBeVisible();
		});

		test("move up reorders items correctly", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					items: ["foo", "bar", "baz"],
				});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						items: {
							type: "array",
							items: { type: "string" },
						},
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the second array item's menu (index 2 - after property menu and first item menu)
			await user.click(menuButtons[2]);

			// Wait for menu to open and click move up
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move up/i }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("menuitem", { name: /move up/i }));

			// Verify the items were reordered
			await waitFor(() => {
				expect(spy).toHaveBeenCalledWith({ items: ["bar", "foo", "baz"] });
			});
		});

		test("move down reorders items correctly", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					items: ["foo", "bar", "baz"],
				});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						items: {
							type: "array",
							items: { type: "string" },
						},
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the second array item's menu (index 2 - after property menu and first item menu)
			await user.click(menuButtons[2]);

			// Wait for menu to open and click move down
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move down/i }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("menuitem", { name: /move down/i }));

			// Verify the items were reordered
			await waitFor(() => {
				expect(spy).toHaveBeenCalledWith({ items: ["foo", "baz", "bar"] });
			});
		});
	});

	describe("move to top/bottom menu options", () => {
		test("shows 'Move to top' option for non-first items", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["first", "second", "third"] }}
				/>,
			);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the second array item's menu (index 2 - after property menu and first item menu)
			await user.click(menuButtons[2]);

			// Check that move to top option exists
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move to top/i }),
				).toBeVisible();
			});
		});

		test("does not show 'Move to top' for first item", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["first", "second", "third"] }}
				/>,
			);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the first array item's menu (index 1 - after property menu)
			await user.click(menuButtons[1]);

			// Wait for menu to open
			await waitFor(() => {
				expect(screen.getByRole("menuitem", { name: /delete/i })).toBeVisible();
			});

			// Move to top should not be present for first item
			expect(
				screen.queryByRole("menuitem", { name: /move to top/i }),
			).not.toBeInTheDocument();
		});

		test("shows 'Move to bottom' option for non-last items", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["first", "second", "third"] }}
				/>,
			);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the second array item's menu (index 2 - after property menu and first item menu)
			await user.click(menuButtons[2]);

			// Check that move to bottom option exists
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move to bottom/i }),
				).toBeVisible();
			});
		});

		test("does not show 'Move to bottom' for last item", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["first", "second", "third"] }}
				/>,
			);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the last array item's menu (index 3 - after property menu and two item menus)
			await user.click(menuButtons[3]);

			// Wait for menu to open
			await waitFor(() => {
				expect(screen.getByRole("menuitem", { name: /delete/i })).toBeVisible();
			});

			// Move to bottom should not be present for last item
			expect(
				screen.queryByRole("menuitem", { name: /move to bottom/i }),
			).not.toBeInTheDocument();
		});

		test("clicking 'Move to top' moves item to first position", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					items: ["first", "second", "third"],
				});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						items: {
							type: "array",
							items: { type: "string" },
						},
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the third array item's menu (index 3 - after property menu and two item menus)
			await user.click(menuButtons[3]);

			// Wait for menu to open and click move to top
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move to top/i }),
				).toBeVisible();
			});

			await user.click(screen.getByRole("menuitem", { name: /move to top/i }));

			// Verify the items were reordered
			await waitFor(() => {
				expect(spy).toHaveBeenCalledWith({
					items: ["third", "first", "second"],
				});
			});
		});

		test("clicking 'Move to bottom' moves item to last position", async () => {
			const user = userEvent.setup();
			const spy = vi.fn();

			function Wrapper() {
				const [values, setValues] = useState<Record<string, unknown>>({
					items: ["first", "second", "third"],
				});
				spy.mockImplementation((value: Record<string, unknown>) =>
					setValues(value),
				);

				const schema: SchemaObject = {
					type: "object",
					properties: {
						items: {
							type: "array",
							items: { type: "string" },
						},
					},
				};

				return (
					<TestSchemaForm
						schema={schema}
						values={values}
						onValuesChange={spy}
					/>
				);
			}

			render(<Wrapper />);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the first array item's menu (index 1 - after property menu)
			await user.click(menuButtons[1]);

			// Wait for menu to open and click move to bottom
			await waitFor(() => {
				expect(
					screen.getByRole("menuitem", { name: /move to bottom/i }),
				).toBeVisible();
			});

			await user.click(
				screen.getByRole("menuitem", { name: /move to bottom/i }),
			);

			// Verify the items were reordered
			await waitFor(() => {
				expect(spy).toHaveBeenCalledWith({
					items: ["second", "third", "first"],
				});
			});
		});
	});

	describe("prefix items behavior", () => {
		test("prefix items cannot be moved", async () => {
			const user = userEvent.setup();
			const schema: SchemaObject = {
				type: "object",
				properties: {
					items: {
						type: "array",
						prefixItems: [
							{ type: "string", title: "First" },
							{ type: "boolean", title: "Second" },
						],
						items: { type: "string" },
					},
				},
			};

			render(
				<TestSchemaForm
					schema={schema}
					values={{ items: ["prefix1", true, "regular1"] }}
				/>,
			);

			// Find all menu trigger buttons
			const menuButtons = screen.getAllByRole("button", { name: /open menu/i });

			// Click the first array item's menu (index 1 - after property menu)
			// This is a prefix item
			await user.click(menuButtons[1]);

			// Wait for menu to open
			await waitFor(() => {
				expect(screen.getByRole("menuitem", { name: /delete/i })).toBeVisible();
			});

			// Move up and move down should not be present for prefix items
			expect(
				screen.queryByRole("menuitem", { name: /move up/i }),
			).not.toBeInTheDocument();
			expect(
				screen.queryByRole("menuitem", { name: /move down/i }),
			).not.toBeInTheDocument();
		});
	});
});
