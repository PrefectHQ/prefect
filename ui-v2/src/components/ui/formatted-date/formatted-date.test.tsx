import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FormattedDate } from "./formatted-date";

// Mock date-fns to have predictable output
vi.mock("date-fns", async () => {
	const actual = await vi.importActual("date-fns");
	return {
		...actual,
		formatDistanceToNow: vi.fn(() => "2 hours ago"),
		format: vi.fn(() => "Jan 15, 2024 at 2:30 PM"),
	};
});

describe("FormattedDate", () => {
	const testDate = "2024-01-15T14:30:00Z";

	it("renders relative time by default", () => {
		render(<FormattedDate date={testDate} />);

		expect(screen.getByText("2 hours ago")).toBeInTheDocument();
	});

	it("renders absolute time when format is absolute", () => {
		render(<FormattedDate date={testDate} format="absolute" />);

		expect(screen.getByText("Jan 15, 2024 at 2:30 PM")).toBeInTheDocument();
	});

	it("renders relative time with tooltip when format is both", async () => {
		const user = userEvent.setup();
		render(<FormattedDate date={testDate} format="both" />);

		expect(screen.getByText("2 hours ago")).toBeInTheDocument();

		// Should show tooltip on hover
		const dateElement = document.querySelector("[data-slot='tooltip-trigger']");
		expect(dateElement).toBeInTheDocument();
		if (dateElement) {
			await user.hover(dateElement);
			expect(await screen.findByRole("tooltip")).toBeInTheDocument();
		}
	});

	it("shows tooltip for relative dates by default", async () => {
		const user = userEvent.setup();
		render(<FormattedDate date={testDate} format="relative" />);

		const dateElement = document.querySelector("[data-slot='tooltip-trigger']");
		expect(dateElement).toBeInTheDocument();
		if (dateElement) {
			await user.hover(dateElement);
			expect(await screen.findByRole("tooltip")).toBeInTheDocument();
		}
	});

	it("does not show tooltip when showTooltip is false", () => {
		render(<FormattedDate date={testDate} showTooltip={false} />);

		expect(screen.getByText("2 hours ago")).toBeInTheDocument();
		expect(
			document.querySelector("[data-slot='tooltip-trigger']"),
		).not.toBeInTheDocument();
	});

	it("does not show tooltip for absolute format by default", () => {
		render(<FormattedDate date={testDate} format="absolute" />);

		expect(screen.getByText("Jan 15, 2024 at 2:30 PM")).toBeInTheDocument();
		expect(
			document.querySelector("[data-slot='tooltip-trigger']"),
		).not.toBeInTheDocument();
	});

	it("handles null date", () => {
		render(<FormattedDate date={null} />);

		expect(screen.getByText("Never")).toBeInTheDocument();
	});

	it("handles undefined date", () => {
		render(<FormattedDate date={undefined} />);

		expect(screen.getByText("Never")).toBeInTheDocument();
	});

	it("handles invalid date string", () => {
		render(<FormattedDate date="invalid-date" />);

		expect(screen.getByText("Invalid date")).toBeInTheDocument();
	});

	it("handles Date object", () => {
		const dateObj = new Date("2024-01-15T14:30:00Z");
		render(<FormattedDate date={dateObj} />);

		expect(screen.getByText("2 hours ago")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		render(
			<FormattedDate
				date={testDate}
				className="custom-class"
				showTooltip={false}
			/>,
		);

		const dateElement = screen.getByText("2 hours ago");
		expect(dateElement).toHaveClass("custom-class");
	});

	it("applies muted text style to null dates", () => {
		render(<FormattedDate date={null} />);

		const neverElement = screen.getByText("Never");
		expect(neverElement).toHaveClass("text-muted-foreground");
	});
});
