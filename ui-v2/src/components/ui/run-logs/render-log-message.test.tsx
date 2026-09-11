import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { renderLogMessage } from "./render-log-message";

const ESC = String.fromCharCode(27);

function renderMessage(text: string) {
	return render(createElement("div", null, renderLogMessage(text)));
}

describe("renderLogMessage", () => {
	it("should render plain text unchanged", () => {
		renderMessage("Hello, world!");

		expect(screen.getByText("Hello, world!")).toBeVisible();
	});

	it("should not render raw ANSI escape sequences", () => {
		const { container } = renderMessage(
			`${ESC}[32mgreen${ESC}[0m ${ESC}[31mred${ESC}[0m plain`,
		);

		expect(container.textContent).toBe("green red plain");
		expect(container.textContent).not.toContain(ESC);
	});

	it("should apply the mapped color class to colored text", () => {
		renderMessage(`${ESC}[32mgreen${ESC}[0m`);

		const span = screen.getByText("green");
		expect(span).toHaveClass("text-green-600", "dark:text-green-500");
	});

	it("should reset active classes on the reset code", () => {
		renderMessage(`${ESC}[31mred${ESC}[0m plain`);

		expect(screen.getByText("red")).toHaveClass("text-red-600");
		const plain = screen.getByText("plain");
		expect(plain).not.toHaveClass("text-red-600");
	});

	it("should combine styling codes onto the same segment", () => {
		renderMessage(`${ESC}[1m${ESC}[4mbold underline${ESC}[0m`);

		const span = screen.getByText("bold underline");
		expect(span).toHaveClass("font-bold", "underline");
	});

	it("should strip unrecognized escape codes without styling", () => {
		const { container } = renderMessage(`${ESC}[38mtext`);

		expect(container.textContent).toBe("text");
		const span = screen.getByText("text");
		expect(span.className).toBe("");
	});

	it("should parse semicolon-separated SGR parameters", () => {
		renderMessage(`${ESC}[1;32mbold green${ESC}[0m`);

		const span = screen.getByText("bold green");
		expect(span).toHaveClass("font-bold", "text-green-600");
	});

	it("should strip 256-color sequences without misapplying styling", () => {
		const { container } = renderMessage(`${ESC}[38;5;196mred256${ESC}[0m`);

		expect(container.textContent).toBe("red256");
		expect(screen.getByText("red256").className).toBe("");
	});

	it("should strip truecolor sequences without misapplying styling", () => {
		const { container } = renderMessage(
			`${ESC}[38;2;255;0;0mtruecolor${ESC}[0m`,
		);

		expect(container.textContent).toBe("truecolor");
		expect(screen.getByText("truecolor").className).toBe("");
	});

	it("should treat an empty parameter list as a reset", () => {
		renderMessage(`${ESC}[31mred${ESC}[mplain`);

		expect(screen.getByText("red")).toHaveClass("text-red-600");
		expect(screen.getByText("plain")).not.toHaveClass("text-red-600");
	});

	it("should linkify URLs inside colored segments", () => {
		renderMessage(`${ESC}[34mVisit https://example.com now${ESC}[0m`);

		const link = screen.getByRole("link", { name: "https://example.com" });
		expect(link).toHaveAttribute("href", "https://example.com");
		expect(link).toHaveAttribute("target", "_blank");
	});
});
