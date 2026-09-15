import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Input } from "./input";

describe("Input", () => {
	it("blurs a focused number input on wheel so scrolling does not change the value", () => {
		render(<Input type="number" aria-label="count" />);
		const input = screen.getByLabelText("count");

		input.focus();
		expect(input).toHaveFocus();

		fireEvent.wheel(input, { deltaY: 100 });

		expect(input).not.toHaveFocus();
	});

	it("keeps focus on wheel for non-number inputs", () => {
		render(<Input type="text" aria-label="name" />);
		const input = screen.getByLabelText("name");

		input.focus();
		fireEvent.wheel(input, { deltaY: 100 });

		expect(input).toHaveFocus();
	});

	it("still calls a provided onWheel handler for number inputs", () => {
		const onWheel = vi.fn();
		render(<Input type="number" aria-label="count" onWheel={onWheel} />);

		fireEvent.wheel(screen.getByLabelText("count"), { deltaY: 100 });

		expect(onWheel).toHaveBeenCalledTimes(1);
	});
});
