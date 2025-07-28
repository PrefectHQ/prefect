import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KeyValueDisplay } from "./key-value-display";

describe("KeyValueDisplay", () => {
	it("renders key-value pairs correctly", () => {
		const items = [
			{ key: "Name", value: "Test Work Pool" },
			{ key: "Type", value: "docker" },
			{ key: "Status", value: "active" },
		];

		render(<KeyValueDisplay items={items} />);

		expect(screen.getByText("Name")).toBeInTheDocument();
		expect(screen.getByText("Test Work Pool")).toBeInTheDocument();
		expect(screen.getByText("Type")).toBeInTheDocument();
		expect(screen.getByText("docker")).toBeInTheDocument();
		expect(screen.getByText("Status")).toBeInTheDocument();
		expect(screen.getByText("active")).toBeInTheDocument();
	});

	it("handles React node values", () => {
		const items = [
			{
				key: "Status",
				value: <span className="text-green-500">Active</span>,
			},
			{
				key: "Actions",
				value: <button type="button">Edit</button>,
			},
		];

		render(<KeyValueDisplay items={items} />);

		expect(screen.getByText("Status")).toBeInTheDocument();
		expect(screen.getByText("Active")).toBeInTheDocument();
		expect(screen.getByText("Actions")).toBeInTheDocument();
		expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
	});

	it("hides items when hidden property is true", () => {
		const items = [
			{ key: "Visible", value: "This should be visible" },
			{ key: "Hidden", value: "This should be hidden", hidden: true },
		];

		render(<KeyValueDisplay items={items} />);

		expect(screen.getByText("Visible")).toBeInTheDocument();
		expect(screen.getByText("This should be visible")).toBeInTheDocument();
		expect(screen.queryByText("Hidden")).not.toBeInTheDocument();
		expect(screen.queryByText("This should be hidden")).not.toBeInTheDocument();
	});

	it("applies compact variant styling", () => {
		const items = [{ key: "Test", value: "Value" }];

		const { container } = render(
			<KeyValueDisplay items={items} variant="compact" />,
		);

		expect(container.firstChild).toHaveClass("space-y-2");
	});

	it("applies default variant styling", () => {
		const items = [{ key: "Test", value: "Value" }];

		const { container } = render(
			<KeyValueDisplay items={items} variant="default" />,
		);

		expect(container.firstChild).toHaveClass("space-y-4");
	});

	it("applies custom className", () => {
		const items = [{ key: "Test", value: "Value" }];

		const { container } = render(
			<KeyValueDisplay items={items} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
