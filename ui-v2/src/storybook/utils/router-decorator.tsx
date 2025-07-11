/* eslint-disable react-refresh/only-export-components */
import {
	createMemoryHistory,
	createRootRoute,
	createRoute,
	createRouter,
	RouterProvider,
	useRouterState,
} from "@tanstack/react-router";
import { createContext, type ReactNode, useContext } from "react";

//#region Dummy story router
function RenderStory() {
	const storyFn = useContext(CurrentStoryContext);
	if (!storyFn) {
		throw new Error("Storybook root not found");
	}
	return storyFn();
}

export const CurrentStoryContext = createContext<(() => ReactNode) | undefined>(
	undefined,
);

function NotFoundComponent() {
	const state = useRouterState();
	return (
		<div>
			<i>Warning:</i> Simulated route not found for path{" "}
			<code>{state.location.href}</code>
		</div>
	);
}

const storyPath = "/__story__";
const storyRoute = createRoute({
	path: storyPath,
	getParentRoute: () => rootRoute,
	component: RenderStory,
});

const rootRoute = createRootRoute({
	notFoundComponent: NotFoundComponent,
});
rootRoute.addChildren([storyRoute]);

export const storyRouter = createRouter({
	history: createMemoryHistory({ initialEntries: [storyPath] }),
	routeTree: rootRoute,
});
//#endregion

/**
 *
 * @example
 * ```ts
 * import { routerDecorator } from '@/storybook/utils'
 *
 * const meta: Meta<typeof MyComponent> = {
 * 	title: "UI/MyComponent",
 * 	decorators: [routerDecorator],
 * 	component: MyComponent,
 * };
 *
 * export default meta;
 */
export function routerDecorator(storyFn: () => ReactNode) {
	return (
		<CurrentStoryContext.Provider value={storyFn}>
			<RouterProvider router={storyRouter} />
		</CurrentStoryContext.Provider>
	);
}
