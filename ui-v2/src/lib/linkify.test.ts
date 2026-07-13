import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { linkify } from "./linkify";

function renderLinkified(text: string) {
	return render(createElement("div", null, linkify(text)));
}

describe("linkify", () => {
	it("should render plain text without links", () => {
		renderLinkified("Hello, world!");

		expect(screen.queryByRole("link")).not.toBeInTheDocument();
		expect(screen.getByText("Hello, world!")).toBeVisible();
	});

	it("should linkify http and https URLs", () => {
		renderLinkified("Visit https://example.com for details");

		const link = screen.getByRole("link", { name: "https://example.com" });
		expect(link).toBeVisible();
		expect(link).toHaveAttribute("href", "https://example.com");
		expect(link).toHaveAttribute("target", "_blank");
		expect(link).toHaveAttribute("rel", "noopener noreferrer");
	});

	it("should not linkify ftp URLs", () => {
		renderLinkified("ftp://example.com/file");

		expect(screen.queryByRole("link")).not.toBeInTheDocument();
	});

	it("should strip trailing punctuation from linkified URLs", () => {
		renderLinkified(
			"Visit https://example.com. Then, see https://example.com, for more!",
		);

		const links = screen.getAllByRole("link");
		expect(links).toHaveLength(2);
		expect(links[0]).toHaveAttribute("href", "https://example.com");
		expect(links[1]).toHaveAttribute("href", "https://example.com");
	});

	it("should preserve punctuation in query strings", () => {
		renderLinkified("https://example.com?foo=bar&baz=qux");

		const link = screen.getByRole("link");
		expect(link).toHaveAttribute("href", "https://example.com?foo=bar&baz=qux");
	});

	it("should trim only trailing punctuation from a query string followed by a comma", () => {
		const { container } = renderLinkified(
			"Check https://example.com?foo=bar, for details",
		);

		const link = screen.getByRole("link");
		expect(link).toHaveAttribute("href", "https://example.com?foo=bar");
		expect(container.textContent).toBe(
			"Check https://example.com?foo=bar, for details",
		);
	});

	it("should keep brackets balanced for IPv6 URLs", () => {
		renderLinkified("https://[::1]");

		const link = screen.getByRole("link");
		expect(link).toHaveAttribute("href", "https://[::1]");
	});

	it("should strip an unbalanced trailing bracket", () => {
		renderLinkified("See https://example.com] for details");

		const link = screen.getByRole("link");
		expect(link).toHaveAttribute("href", "https://example.com");
	});
});
