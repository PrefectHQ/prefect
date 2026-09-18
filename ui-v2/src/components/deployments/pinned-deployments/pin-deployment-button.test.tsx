import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockInMemoryLocalStorage } from "@tests/utils/browser";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toaster } from "@/components/ui/sonner";
import { PinDeploymentButton } from "./pin-deployment-button";
import { PINNED_DEPLOYMENTS_STORAGE_KEY } from "./use-pinned-deployments";

describe("PinDeploymentButton", () => {
	let restoreLocalStorage: () => void;

	beforeEach(() => {
		restoreLocalStorage = mockInMemoryLocalStorage();
	});

	afterEach(() => {
		restoreLocalStorage();
	});

	it("pins an unpinned deployment", async () => {
		const user = userEvent.setup();
		render(<PinDeploymentButton deploymentId="deployment-1" />);

		const button = screen.getByRole("button", { name: "Pin deployment" });
		expect(button).toHaveAttribute("aria-pressed", "false");

		await user.click(button);

		expect(
			screen.getByRole("button", { name: "Unpin deployment" }),
		).toHaveAttribute("aria-pressed", "true");
		expect(localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY)).toBe(
			JSON.stringify(["deployment-1"]),
		);
	});

	it("unpins a pinned deployment", async () => {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(["deployment-1", "deployment-2"]),
		);
		const user = userEvent.setup();
		render(<PinDeploymentButton deploymentId="deployment-1" />);

		await user.click(screen.getByRole("button", { name: "Unpin deployment" }));

		expect(
			screen.getByRole("button", { name: "Pin deployment" }),
		).toBeInTheDocument();
		expect(localStorage.getItem(PINNED_DEPLOYMENTS_STORAGE_KEY)).toBe(
			JSON.stringify(["deployment-2"]),
		);
	});

	it("always shows by default", () => {
		render(<PinDeploymentButton deploymentId="deployment-1" />);

		expect(
			screen.getByRole("button", { name: "Pin deployment" }),
		).not.toHaveClass("opacity-0");
	});

	it("hides until its row is hovered when revealOnRowHover is set", () => {
		render(
			<PinDeploymentButton deploymentId="deployment-1" revealOnRowHover />,
		);

		const button = screen.getByRole("button", { name: "Pin deployment" });
		expect(button).toHaveClass("opacity-0");
		expect(button).toHaveClass("[tr:hover_&]:opacity-100");
		expect(button).toHaveClass("focus-visible:opacity-100");
		expect(button).toHaveClass("[@media(hover:none)]:opacity-100");
	});

	it("always shows a pinned deployment, even with revealOnRowHover", () => {
		localStorage.setItem(
			PINNED_DEPLOYMENTS_STORAGE_KEY,
			JSON.stringify(["deployment-1"]),
		);
		render(
			<PinDeploymentButton deploymentId="deployment-1" revealOnRowHover />,
		);

		expect(
			screen.getByRole("button", { name: "Unpin deployment" }),
		).not.toHaveClass("opacity-0");
	});

	it("tells the user when the browser refuses to store the pin", async () => {
		vi.spyOn(localStorage, "setItem").mockImplementation(() => {
			throw new DOMException("quota exceeded", "QuotaExceededError");
		});
		const user = userEvent.setup();
		render(
			<>
				<Toaster />
				<PinDeploymentButton deploymentId="deployment-1" />
			</>,
		);

		await user.click(screen.getByRole("button", { name: "Pin deployment" }));

		expect(
			await screen.findByText("Could not save the pin in this browser"),
		).toBeVisible();
		expect(
			screen.getByRole("button", { name: "Pin deployment" }),
		).toHaveAttribute("aria-pressed", "false");
	});
});
