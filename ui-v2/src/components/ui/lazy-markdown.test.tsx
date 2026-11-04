import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LazyMarkdown } from "./lazy-markdown";

describe("LazyMarkdown", () => {
	it("renders markdown", async () => {
		render(<LazyMarkdown># Hello World</LazyMarkdown>);

		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: "Hello World" }),
			).toBeInTheDocument();
		});
	});

	it("renders embedded html as markup", async () => {
		render(
			<LazyMarkdown>
				{`<!-- format: markdown --> <table><tr><td width="84px"><img src="https://example.com/icon.png" alt="icon"/></td><td>This deployment allows...</td></tr></table>`}
			</LazyMarkdown>,
		);

		await waitFor(() => {
			expect(screen.getByRole("table")).toBeInTheDocument();
		});

		expect(screen.getByRole("img", { name: "icon" })).toHaveAttribute(
			"src",
			"https://example.com/icon.png",
		);
		expect(screen.getByRole("cell", { name: "This deployment allows..." }));
	});

	it("keeps footnote links pointing at their footnote", async () => {
		const { container } = render(
			<LazyMarkdown>{"note[^1]\n\n[^1]: the footnote"}</LazyMarkdown>,
		);

		await waitFor(() => {
			expect(screen.getByText("note")).toBeInTheDocument();
		});

		const reference = screen.getByRole("link", { name: "1" });
		const href = reference.getAttribute("href") ?? "";
		expect(href).toMatch(/^#\S+$/);
		expect(container.querySelector(href)).toHaveTextContent("the footnote");
	});

	it("renders inline data: images", async () => {
		const png =
			"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
		render(
			<LazyMarkdown>
				{`![My figure](${png})\n\n<img src="${png}" alt="Raw figure" />`}
			</LazyMarkdown>,
		);

		expect(
			await screen.findByRole("img", { name: "My figure" }),
		).toHaveAttribute("src", png);
		expect(screen.getByRole("img", { name: "Raw figure" })).toHaveAttribute(
			"src",
			png,
		);
	});

	it("strips non-image data: urls", async () => {
		const html = "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==";
		render(
			<LazyMarkdown>
				{`[link](${html})\n\n<img src="${html}" alt="not an image" />`}
			</LazyMarkdown>,
		);

		expect(await screen.findByText("link")).not.toHaveAttribute("href");
		expect(
			screen.getByRole("img", { name: "not an image" }),
		).not.toHaveAttribute("src");
	});

	it("strips unsafe html", async () => {
		const { container } = render(
			<LazyMarkdown>
				{`<p>safe</p><script>window.pwned = true;</script><img src="x" onerror="window.pwned = true" alt="unsafe" />`}
			</LazyMarkdown>,
		);

		await waitFor(() => {
			expect(screen.getByText("safe")).toBeInTheDocument();
		});

		expect(container.querySelector("script")).toBeNull();
		expect(screen.getByRole("img", { name: "unsafe" })).not.toHaveAttribute(
			"onerror",
		);
	});
});
