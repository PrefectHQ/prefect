import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
	LayoutWell,
	LayoutWellContent,
	LayoutWellHeader,
	LayoutWellSidebar,
} from "./layout-well";

describe("LayoutWell", () => {
	it("renders children correctly", () => {
		render(
			<LayoutWell>
				<div data-testid="test-content">Test Content</div>
			</LayoutWell>,
		);

		expect(screen.getByTestId("test-content")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<LayoutWell className="custom-class">Content</LayoutWell>,
		);

		expect(container.firstChild).toHaveClass("custom-class");
		expect(container.firstChild).toHaveClass("min-h-screen");
	});
});

describe("LayoutWellHeader", () => {
	it("renders header content", () => {
		render(
			<LayoutWellHeader>
				<h1>Header Title</h1>
			</LayoutWellHeader>,
		);

		expect(screen.getByText("Header Title")).toBeInTheDocument();
	});

	it("applies custom className", () => {
		const { container } = render(
			<LayoutWellHeader className="custom-header">Header</LayoutWellHeader>,
		);

		expect(container.firstChild).toHaveClass("custom-header");
		expect(container.firstChild).toHaveClass("w-full");
	});
});

describe("LayoutWellContent", () => {
	it("renders content correctly", () => {
		render(
			<LayoutWellContent>
				<div data-testid="main-content">Main Content</div>
			</LayoutWellContent>,
		);

		expect(screen.getByTestId("main-content")).toBeInTheDocument();
	});

	it("applies flex-1 class for proper layout", () => {
		const { container } = render(
			<LayoutWellContent>Content</LayoutWellContent>,
		);

		expect(container.firstChild).toHaveClass("flex-1");
		expect(container.firstChild).toHaveClass("w-full");
	});
});

describe("LayoutWellSidebar", () => {
	it("renders sidebar content", () => {
		render(
			<LayoutWellSidebar>
				<nav>Sidebar Navigation</nav>
			</LayoutWellSidebar>,
		);

		expect(screen.getByText("Sidebar Navigation")).toBeInTheDocument();
	});

	it("applies responsive classes", () => {
		const { container } = render(
			<LayoutWellSidebar>Sidebar</LayoutWellSidebar>,
		);

		const sidebar = container.firstChild;
		expect(sidebar).toHaveClass("lg:block");
		expect(sidebar).toHaveClass("hidden");
		expect(sidebar).toHaveClass("lg:w-80");
	});

	it("has sticky positioning", () => {
		render(
			<LayoutWellSidebar>
				<div data-testid="sidebar-content">Content</div>
			</LayoutWellSidebar>,
		);

		const stickyWrapper = screen.getByTestId("sidebar-content").parentElement;
		expect(stickyWrapper).toHaveClass("sticky");
		expect(stickyWrapper).toHaveClass("top-8");
	});
});
