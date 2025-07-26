import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CodeBanner } from "./code-banner";

// Mock clipboard API
const mockWriteText = vi.fn();
Object.assign(navigator, {
	clipboard: {
		writeText: mockWriteText,
	},
});

// Mock toast
vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
	},
}));

describe("CodeBanner", () => {
	const defaultProps = {
		command: 'prefect worker start --pool "test-pool"',
		title: "Your work pool is almost ready!",
		subtitle: "Run this command to start.",
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

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

	it("copies command to clipboard when copy button is clicked", async () => {
		const user = userEvent.setup();
		mockWriteText.mockResolvedValueOnce(undefined);

		render(<CodeBanner {...defaultProps} />);

		const copyButton = screen.getByRole("button");
		await user.click(copyButton);

		expect(mockWriteText).toHaveBeenCalledWith(
			'prefect worker start --pool "test-pool"',
		);
		expect(toast.success).toHaveBeenCalledWith("Command copied to clipboard");
	});

	it("shows error toast when clipboard fails", async () => {
		const user = userEvent.setup();
		mockWriteText.mockRejectedValueOnce(new Error("Clipboard failed"));

		render(<CodeBanner {...defaultProps} />);

		const copyButton = screen.getByRole("button");
		await user.click(copyButton);

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Failed to copy command");
		});
	});

	it("disables copy button while copying", async () => {
		const user = userEvent.setup();
		let resolveClipboard: (value: unknown) => void = () => {};
		mockWriteText.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveClipboard = resolve;
			}),
		);

		render(<CodeBanner {...defaultProps} />);

		const copyButton = screen.getByRole("button");
		await user.click(copyButton);

		expect(copyButton).toBeDisabled();

		resolveClipboard(undefined);
		await waitFor(() => {
			expect(copyButton).not.toBeDisabled();
		});
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
