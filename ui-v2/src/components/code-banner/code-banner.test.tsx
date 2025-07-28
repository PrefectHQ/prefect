import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CodeBanner } from "./code-banner";

describe("CodeBanner", () => {
	const defaultProps = {
		command: 'prefect worker start --pool "test-pool"',
		title: "Your work pool is almost ready!",
		subtitle: "Run this command to start.",
	};

	it("renders with correct title and subtitle", () => {
		render(<CodeBanner {...defaultProps} />);

		expect(
			screen.getByText("Your work pool is almost ready!"),
		).toBeInTheDocument();
		expect(screen.getByText("Run this command to start.")).toBeInTheDocument();
	});

	it("displays command text correctly", () => {
		render(<CodeBanner {...defaultProps} />);

		expect(
			screen.getByText('prefect worker start --pool "test-pool"'),
		).toBeInTheDocument();
	});

	it("renders copy button", () => {
		render(<CodeBanner {...defaultProps} />);

		const copyButton = screen.getByRole("button");
		expect(copyButton).toBeInTheDocument();
	});

	it("handles long commands gracefully", () => {
		const longCommand = `prefect worker start --pool ${"very-long-pool-name".repeat(10)}`;
		render(<CodeBanner {...defaultProps} command={longCommand} />);

		expect(screen.getByText(longCommand)).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<CodeBanner {...defaultProps} className="custom-class" />,
		);

		expect(container.firstChild).toHaveClass("custom-class");
	});
});
