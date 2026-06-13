import {
	createMemoryHistory,
	createRootRoute,
	createRouter,
	Outlet,
	RouterProvider,
} from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { buildApiUrl, createWrapper, server } from "@tests/utils";
import { mockPointerEvents } from "@tests/utils/browser";
import { HttpResponse, http } from "msw";
import { createContext, type ReactNode, useContext } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { BlockDocument } from "@/api/block-documents";
import { createFakeBlockDocument } from "@/mocks";
import { DefaultResultStorageCard } from "./default-result-storage-card";

const TestChildrenContext = createContext<ReactNode>(null);

function RenderTestChildren() {
	const children = useContext(TestChildrenContext);
	return (
		<>
			{children}
			<Outlet />
		</>
	);
}

const renderWithRouter = async (ui: ReactNode) => {
	const rootRoute = createRootRoute({
		component: RenderTestChildren,
		notFoundComponent: () => null,
	});

	const router = createRouter({
		routeTree: rootRoute,
		history: createMemoryHistory({ initialEntries: ["/"] }),
	});

	const Wrapper = createWrapper();

	const result = render(
		<Wrapper>
			<TestChildrenContext.Provider value={ui}>
				<RouterProvider router={router} />
			</TestChildrenContext.Provider>
		</Wrapper>,
	);

	await waitFor(() => {
		expect(router.state.status).toBe("idle");
	});

	return result;
};

const createStorageBlockDocument = (
	overrides?: Partial<BlockDocument>,
): BlockDocument =>
	createFakeBlockDocument({
		id: "block-1",
		name: "s3-results",
		block_type_name: "S3 Bucket",
		block_type: {
			id: "block-type-1",
			created: "2026-05-03T00:00:00Z",
			updated: "2026-05-03T00:00:00Z",
			name: "S3 Bucket",
			slug: "s3-bucket",
			logo_url: null,
			documentation_url: null,
			description: null,
			code_example: null,
			is_protected: false,
		},
		...overrides,
	});

const mockStorageBlockDocumentsAPI = (blockDocuments: Array<BlockDocument>) => {
	server.use(
		http.post(buildApiUrl("/block_documents/filter"), () => {
			return HttpResponse.json(blockDocuments);
		}),
	);
};

describe("DefaultResultStorageCard", () => {
	beforeEach(() => {
		mockPointerEvents();
		mockStorageBlockDocumentsAPI([]);
	});

	it("renders the configured default result storage block", async () => {
		const blockDocument = createStorageBlockDocument();
		mockStorageBlockDocumentsAPI([blockDocument]);

		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId={blockDocument.id}
				defaultResultStorageBlock={blockDocument}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		expect(screen.getByText("Default result storage")).toBeVisible();
		expect(screen.getByText("Configured")).toBeVisible();
		expect(screen.getAllByText("s3-results")[0]).toBeVisible();
		expect(screen.getByText("S3 Bucket")).toBeVisible();
		expect(
			screen.queryByRole("img", { name: "S3 Bucket logo" }),
		).not.toBeInTheDocument();
	});

	it("renders the unconfigured state", async () => {
		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId={undefined}
				defaultResultStorageBlock={undefined}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		expect(screen.getByText("Not configured")).toBeVisible();
		expect(
			screen.getByText("No default storage block is configured."),
		).toBeVisible();
		expect(
			screen.getByRole("link", { name: /new storage block/i }),
		).toBeVisible();
		expect(
			screen.queryByRole("button", { name: /clear/i }),
		).not.toBeInTheDocument();
	});

	it("renders a loading state while the configured block is being resolved", async () => {
		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId="block-1"
				defaultResultStorageBlock={undefined}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={true}
			/>,
		);

		expect(screen.getByText("Configured")).toBeVisible();
		expect(
			screen.getByText("Loading configured storage block..."),
		).toBeVisible();
		expect(
			screen.queryByText(
				"The configured default storage block could not be found.",
			),
		).not.toBeInTheDocument();
	});

	it("does not surface stale configured-block recovery UI", async () => {
		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId="block-1"
				defaultResultStorageBlock={undefined}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		expect(screen.getByText("Not configured")).toBeVisible();
		expect(
			screen.getByText("No default storage block is configured."),
		).toBeVisible();
		expect(
			screen.queryByText("Default storage block not found"),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: /remove stale default/i }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: /clear/i }),
		).not.toBeInTheDocument();
	});

	it("calls update when a storage block is selected from the combobox", async () => {
		const user = userEvent.setup();
		const onUpdateDefaultResultStorage = vi.fn();
		const blockDocument = createStorageBlockDocument();
		mockStorageBlockDocumentsAPI([blockDocument]);

		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId={undefined}
				defaultResultStorageBlock={undefined}
				onUpdateDefaultResultStorage={onUpdateDefaultResultStorage}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		await waitFor(() =>
			expect(
				screen.getByRole("button", {
					name: /default result storage block/i,
				}),
			).toBeVisible(),
		);

		await user.click(
			screen.getByRole("button", { name: /default result storage block/i }),
		);

		await waitFor(() =>
			expect(screen.getByRole("option", { name: "s3-results" })).toBeVisible(),
		);

		await user.click(screen.getByRole("option", { name: "s3-results" }));

		expect(onUpdateDefaultResultStorage).toHaveBeenCalledWith(blockDocument.id);
	});

	it("calls clear when the clear button is clicked", async () => {
		const user = userEvent.setup();
		const onClearDefaultResultStorage = vi.fn();
		const blockDocument = createStorageBlockDocument();
		mockStorageBlockDocumentsAPI([blockDocument]);

		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId={blockDocument.id}
				defaultResultStorageBlock={blockDocument}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={onClearDefaultResultStorage}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		await user.click(screen.getByRole("button", { name: /clear/i }));

		expect(onClearDefaultResultStorage).toHaveBeenCalledOnce();
	});

	it("displays search input in the combobox dropdown", async () => {
		const user = userEvent.setup();
		const blockDocuments = [
			createStorageBlockDocument({ id: "block-1", name: "s3-results" }),
			createStorageBlockDocument({ id: "block-2", name: "gcs-results" }),
		];
		mockStorageBlockDocumentsAPI(blockDocuments);

		await renderWithRouter(
			<DefaultResultStorageCard
				defaultResultStorageBlockId={undefined}
				defaultResultStorageBlock={undefined}
				onUpdateDefaultResultStorage={vi.fn()}
				onClearDefaultResultStorage={vi.fn()}
				isUpdatingDefaultResultStorage={false}
				isClearingDefaultResultStorage={false}
				isLoadingDefaultResultStorageBlock={false}
			/>,
		);

		await waitFor(() =>
			expect(
				screen.getByRole("button", {
					name: /default result storage block/i,
				}),
			).toBeVisible(),
		);

		await user.click(
			screen.getByRole("button", { name: /default result storage block/i }),
		);

		expect(
			screen.getByPlaceholderText("Search storage blocks..."),
		).toBeVisible();
		expect(screen.getByRole("option", { name: "s3-results" })).toBeVisible();
		expect(screen.getByRole("option", { name: "gcs-results" })).toBeVisible();
	});
});
