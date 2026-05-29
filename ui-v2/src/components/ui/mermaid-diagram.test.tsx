import { render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MermaidDiagram } from "./mermaid-diagram";

vi.mock("mermaid", () => ({
	default: {
		initialize: vi.fn(),
		render: vi.fn(),
	},
}));

const mermaidMock = await import("mermaid");
const renderMock = mermaidMock.default.render as ReturnType<typeof vi.fn>;
const initializeMock = mermaidMock.default.initialize as ReturnType<
	typeof vi.fn
>;

const renderWithTheme = (ui: React.ReactElement) =>
	render(
		<ThemeProvider attribute="class" defaultTheme="light">
			{ui}
		</ThemeProvider>,
	);

afterEach(() => {
	renderMock.mockReset();
	initializeMock.mockReset();
});

describe("MermaidDiagram", () => {
	it("renders the SVG returned by mermaid", async () => {
		renderMock.mockResolvedValueOnce({
			svg: "<svg data-testid='mermaid-svg'></svg>",
		});

		renderWithTheme(<MermaidDiagram source="graph TD; A-->B" />);

		await waitFor(() => {
			expect(screen.getByTestId("mermaid-svg")).toBeInTheDocument();
		});
		expect(initializeMock).toHaveBeenCalled();
		expect(renderMock).toHaveBeenCalledWith(
			expect.stringContaining("mermaid-"),
			"graph TD; A-->B",
		);
	});

	it("renders an error fallback with the source when mermaid fails", async () => {
		renderMock.mockRejectedValueOnce(new Error("bad syntax"));

		renderWithTheme(<MermaidDiagram source="not valid mermaid" />);

		await waitFor(() => {
			expect(
				screen.getByText("Failed to render mermaid diagram"),
			).toBeInTheDocument();
		});
		expect(screen.getByText("bad syntax")).toBeInTheDocument();
		expect(screen.getByText("not valid mermaid")).toBeInTheDocument();
	});
});
