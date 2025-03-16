import { QueryClient } from "@tanstack/react-query";
import { createRouter, createRouteMask } from "@tanstack/react-router";
// Import the generated route tree
import { routeTree } from "./routeTree.gen";
import {
	parseSearchWith,
	stringifySearchWith,
  } from '@tanstack/react-router'

export const queryClient = new QueryClient();

function decodeFromBinary(str: string): string {
	const decoded = decodeURIComponent(
	  Array.prototype.map
		.call(atob(str), function (c) {
		  return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
		})
		.join(''),
	)
	console.log("decoded", JSON.stringify(decoded, null, 2));
	return decoded;
  }
  
  function encodeToBinary(str: string): string {
	return btoa(
	  encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, function (_, p1) {
		return String.fromCharCode(parseInt(p1, 16))
	  }),
	)
  }

export const router = createRouter({
	routeTree,
	context: {
		queryClient: queryClient,
	},
	defaultPreload: "intent",
	parseSearch: parseSearchWith((value) => JSON.parse(decodeFromBinary(value))),
	stringifySearch: stringifySearchWith((value) =>
	  encodeToBinary(JSON.stringify(value)),
	),
	// Since we're using React Query, we don't want loader calls to ever be stale
	// This will ensure that the loader is always called when the route is preloaded or visited
	defaultPreloadStaleTime: 0,
	unmaskOnReload: true,
	routeMasks: [
		createRouteMask({
			routeTree,
			from: "/events",
			to: "/events",
			search: (prev) => ({limit: prev.limit}),
			unmaskOnReload: true,
		})
	],
});

declare module "@tanstack/react-router" {
	interface Register {
		router: typeof router;
	}
}
