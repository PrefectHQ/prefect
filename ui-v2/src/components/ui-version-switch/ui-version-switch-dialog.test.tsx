import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UiVersionSwitchDialog } from "./ui-version-switch-dialog";

describe("UiVersionSwitchDialog", () => {
	it("requires a reason before submitting", async () => {
		const user = userEvent.setup();
		const onSubmitFeedback = vi.fn();

		render(
			<UiVersionSwitchDialog
				open={true}
				onOpenChange={vi.fn()}
				onSkipFeedback={vi.fn()}
				onSubmitFeedback={onSubmitFeedback}
			/>,
		);

		await user.click(
			screen.getByRole("button", { name: "Submit feedback and switch" }),
		);

		expect(onSubmitFeedback).not.toHaveBeenCalled();
		expect(
			screen.getByText("Select a reason before switching back to V1."),
		).toBeInTheDocument();
	});

	it("submits structured feedback", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		const onSubmitFeedback = vi.fn();

		render(
			<UiVersionSwitchDialog
				open={true}
				onOpenChange={onOpenChange}
				onSkipFeedback={vi.fn()}
				onSubmitFeedback={onSubmitFeedback}
			/>,
		);

		await user.click(screen.getByRole("radio", { name: /Missing feature/i }));
		await user.type(
			screen.getByLabelText("Additional notes"),
			"Need the old flow graph.",
		);
		await user.click(screen.getByLabelText("Also open GitHub issue"));
		await user.click(
			screen.getByRole("button", { name: "Submit feedback and switch" }),
		);

		expect(onOpenChange).toHaveBeenCalledWith(false);
		expect(onSubmitFeedback).toHaveBeenCalledWith({
			reason: "missing_feature",
			notes: "Need the old flow graph.",
			openGithubIssue: true,
		});
	});

	it("supports skipping feedback", async () => {
		const user = userEvent.setup();
		const onOpenChange = vi.fn();
		const onSkipFeedback = vi.fn();

		render(
			<UiVersionSwitchDialog
				open={true}
				onOpenChange={onOpenChange}
				onSkipFeedback={onSkipFeedback}
				onSubmitFeedback={vi.fn()}
			/>,
		);

		await user.click(
			screen.getByRole("button", { name: "Skip feedback and switch" }),
		);

		expect(onOpenChange).toHaveBeenCalledWith(false);
		expect(onSkipFeedback).toHaveBeenCalledTimes(1);
	});
});
