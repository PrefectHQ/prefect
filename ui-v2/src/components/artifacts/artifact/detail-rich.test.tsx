import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DetailRich } from "./detail-rich";

describe("ArtifactDetailRich", () => {
	it("renders rich artifact HTML in a sandboxed iframe", () => {
		render(
			<DetailRich
				richData={{
					html: "<h1>Rich Content</h1>",
					sandbox: ["allow-scripts"],
				}}
			/>,
		);

		expect(screen.getByTestId("rich-display")).toBeInTheDocument();
		expect(screen.getByTestId("rich-artifact-iframe")).toHaveAttribute(
			"sandbox",
			"allow-scripts",
		);
		expect(screen.getByTestId("rich-artifact-iframe")).toHaveAttribute(
			"srcdoc",
			"<h1>Rich Content</h1>",
		);
	});

	it("strips allow-same-origin when allow-scripts is present", () => {
		render(
			<DetailRich
				richData={{
					html: "<h1>Content</h1>",
					sandbox: ["allow-scripts", "allow-same-origin"],
				}}
			/>,
		);

		expect(screen.getByTestId("rich-artifact-iframe")).toHaveAttribute(
			"sandbox",
			"allow-scripts",
		);
	});

	it("keeps allow-same-origin when allow-scripts is absent", () => {
		render(
			<DetailRich
				richData={{
					html: "<h1>Content</h1>",
					sandbox: ["allow-same-origin"],
				}}
			/>,
		);

		expect(screen.getByTestId("rich-artifact-iframe")).toHaveAttribute(
			"sandbox",
			"allow-same-origin",
		);
	});

	it("injects CSP metadata when csp is provided", () => {
		render(
			<DetailRich
				richData={{
					html: "<html><head></head><body>hello</body></html>",
					sandbox: ["allow-scripts"],
					csp: "default-src 'none'; style-src 'unsafe-inline'",
				}}
			/>,
		);

		expect(screen.getByTestId("rich-artifact-iframe")).toHaveAttribute(
			"srcdoc",
			expect.stringContaining(
				`<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`,
			),
		);
	});

	it("shows fallback for invalid rich payload", () => {
		render(<DetailRich richData="not-a-rich-payload" />);

		expect(screen.getByTestId("rich-display-invalid")).toBeInTheDocument();
		expect(
			screen.queryByTestId("rich-artifact-iframe"),
		).not.toBeInTheDocument();
	});
});
