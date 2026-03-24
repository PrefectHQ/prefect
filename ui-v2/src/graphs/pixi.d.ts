import { RunGraphData } from "@/graphs/models";

declare module "pixi.js" {
	interface ContainerEvents {
		resized: [{ height: number; width: number }];
		rendered: [];
		fetched: [RunGraphData];
	}
}
