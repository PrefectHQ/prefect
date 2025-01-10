import { createFakeAutomation } from "@/mocks";
import { ActionStep } from "./action-step";

import { Automation } from "@/api/automations";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { http, HttpResponse } from "msw";
import { beforeAll, describe, expect, it, vi } from "vitest";

describe("ActionStep", () => {
	const mockListAutomationAPI = (automations: Array<Automation>) => {
		server.use(
			http.post(buildApiUrl("/automations/filter"), () => {
				return HttpResponse.json(automations);
			}),
		);
	};

	beforeAll(() => {
		/**
		 * JSDOM doesn't implement PointerEvent so we need to mock our own implementation
		 * Default to mouse left click interaction
		 * https://github.com/radix-ui/primitives/issues/1822
		 * https://github.com/jsdom/jsdom/pull/2666
		 */
		class MockPointerEvent extends Event {
			button: number;
			ctrlKey: boolean;
			pointerType: string;

			constructor(type: string, props: PointerEventInit) {
				super(type, props);
				this.button = props.button || 0;
				this.ctrlKey = props.ctrlKey || false;
				this.pointerType = props.pointerType || "mouse";
			}
		}
		window.PointerEvent = MockPointerEvent as never;
		window.HTMLElement.prototype.scrollIntoView = vi.fn();
		window.HTMLElement.prototype.releasePointerCapture = vi.fn();
		window.HTMLElement.prototype.hasPointerCapture = vi.fn();
	});

	describe("action type -- basic action", () => {
		it("able to select a basic action", async () => {
			const user = userEvent.setup();

			// ------------ Setup
			const mockOnSubmitFn = vi.fn();
			render(<ActionStep onSubmit={mockOnSubmitFn} />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Cancel a flow run" }),
			);

			// ------------ Assert
			expect(screen.getAllByText("Cancel a flow run")).toBeTruthy();
		});
	});

	describe("action type -- change flow run state ", () => {
		it("able to configure change flow run's state action", async () => {
			const user = userEvent.setup();

			// ------------ Setup
			const mockOnSubmitFn = vi.fn();
			render(<ActionStep onSubmit={mockOnSubmitFn} />);

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Change flow run's state" }),
			);

			await user.click(screen.getByRole("combobox", { name: /select state/i }));
			await user.click(screen.getByRole("option", { name: "Failed" }));
			await user.type(screen.getByPlaceholderText("Failed"), "test name");
			await user.type(screen.getByLabelText("Message"), "test message");

			// ------------ Assert
			expect(screen.getAllByText("Change flow run's state")).toBeTruthy();
			expect(screen.getAllByText("Failed")).toBeTruthy();
			expect(screen.getByLabelText("Name")).toHaveValue("test name");
			expect(screen.getByLabelText("Message")).toHaveValue("test message");
		});
	});

	describe("action type -- automation", () => {
		it("able to configure pause an automation action type", async () => {
			mockListAutomationAPI([
				createFakeAutomation({ name: "my automation 0" }),
				createFakeAutomation({ name: "my automation 1" }),
			]);

			const user = userEvent.setup();

			// ------------ Setup
			const mockOnSubmitFn = vi.fn();
			render(<ActionStep onSubmit={mockOnSubmitFn} />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Pause an automation" }),
			);

			expect(screen.getAllByText("Infer Automation")).toBeTruthy();
			await user.click(
				screen.getByRole("combobox", { name: /select automation to pause/i }),
			);

			await user.click(screen.getByRole("option", { name: "my automation 0" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause an automation")).toBeTruthy();
			expect(screen.getAllByText("my automation 0")).toBeTruthy();
		});

		it("able to configure resume an automation action type", async () => {
			mockListAutomationAPI([
				createFakeAutomation({ name: "my automation 0" }),
				createFakeAutomation({ name: "my automation 1" }),
			]);
			const user = userEvent.setup();

			// ------------ Setup
			const mockOnSubmitFn = vi.fn();
			render(<ActionStep onSubmit={mockOnSubmitFn} />, {
				wrapper: createWrapper(),
			});

			// ------------ Act
			await user.click(
				screen.getByRole("combobox", { name: /select action/i }),
			);
			await user.click(
				screen.getByRole("option", { name: "Resume an automation" }),
			);

			expect(screen.getAllByText("Infer Automation")).toBeTruthy();
			await user.click(
				screen.getByRole("combobox", { name: /select automation to resume/i }),
			);

			await user.click(screen.getByRole("option", { name: "my automation 1" }));

			// ------------ Assert
			expect(screen.getAllByText("Pause an automation")).toBeTruthy();
			expect(screen.getAllByText("my automation 1")).toBeTruthy();
		});
	});
});
