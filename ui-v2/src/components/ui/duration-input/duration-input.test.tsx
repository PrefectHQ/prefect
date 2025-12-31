import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockPointerEvents } from "@tests/utils/browser";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { DurationInput } from "./index";

describe("DurationInput", () => {
	beforeAll(() => {
		mockPointerEvents();
	});
	it("renders with initial value in seconds", () => {
		render(<DurationInput value={30} onChange={vi.fn()} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(30);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Seconds");
	});

	it("renders with initial value in minutes when divisible by 60", () => {
		render(<DurationInput value={120} onChange={vi.fn()} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(2);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Minutes");
	});

	it("renders with initial value in hours when divisible by 3600", () => {
		render(<DurationInput value={7200} onChange={vi.fn()} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(2);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Hours");
	});

	it("renders with initial value in days when divisible by 86400", () => {
		render(<DurationInput value={172800} onChange={vi.fn()} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(2);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Days");
	});

	it("calls onChange with correct seconds when quantity changes", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<DurationInput value={0} onChange={onChange} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		await user.type(quantityInput, "5");

		expect(onChange).toHaveBeenLastCalledWith(5);
	});

	it("calls onChange with converted seconds when unit changes", async () => {
		const user = userEvent.setup();
		const onChange = vi.fn();

		render(<DurationInput value={60} onChange={onChange} />);

		const unitSelect = screen.getByLabelText("Duration unit");
		await user.click(unitSelect);
		await user.click(screen.getByRole("option", { name: "Hours" }));

		expect(onChange).toHaveBeenLastCalledWith(3600);
	});

	it("filters available units based on min prop", () => {
		render(<DurationInput value={3600} onChange={vi.fn()} min={60} />);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Hours");
	});

	it("disables inputs when disabled prop is true", () => {
		render(<DurationInput value={30} onChange={vi.fn()} disabled />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		const unitSelect = screen.getByLabelText("Duration unit");

		expect(quantityInput).toBeDisabled();
		expect(unitSelect).toBeDisabled();
	});

	it("handles zero value correctly", () => {
		render(<DurationInput value={0} onChange={vi.fn()} />);

		const quantityInput = screen.getByLabelText("Duration quantity");
		expect(quantityInput).toHaveValue(0);

		const unitSelect = screen.getByLabelText("Duration unit");
		expect(unitSelect).toHaveTextContent("Seconds");
	});
});
