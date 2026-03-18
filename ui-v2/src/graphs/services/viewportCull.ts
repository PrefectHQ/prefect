import type { Container, Rectangle } from "pixi.js";

type CullToggle = "visible" | "renderable";

type CullOptions = {
	recursive?: boolean;
	toggle?: CullToggle;
};

/**
 * Simple viewport culling for pixi.js v8.
 *
 * Replaces @pixi-essentials/cull which is incompatible with pixi.js v8's
 * rewritten bounds/transform system.
 */
export class ViewportCull {
	private readonly recursive: boolean;
	private readonly toggle: CullToggle;
	private readonly targets = new Set<Container>();

	constructor(options: CullOptions = {}) {
		this.recursive = options.recursive ?? true;
		this.toggle = options.toggle ?? "visible";
	}

	add(target: Container): this {
		this.targets.add(target);
		return this;
	}

	addAll(targets: Container[]): this {
		for (const target of targets) {
			this.targets.add(target);
		}
		return this;
	}

	remove(target: Container): this {
		this.targets.delete(target);
		return this;
	}

	clear(): this {
		this.targets.clear();
		return this;
	}

	cull(rect: Rectangle): this {
		this.uncull();

		for (const target of this.targets) {
			if (this.recursive) {
				this.cullRecursive(rect, target);
			} else {
				const bounds = target.getBounds();
				target[this.toggle] = this.intersects(bounds, rect);
			}
		}

		return this;
	}

	uncull(): this {
		for (const target of this.targets) {
			if (this.recursive) {
				this.uncullRecursive(target);
			} else {
				target[this.toggle] = true;
			}
		}
		return this;
	}

	private cullRecursive(rect: Rectangle, container: Container): void {
		const bounds = container.getBounds();
		const visible = this.intersects(bounds, rect);
		container[this.toggle] = visible;

		const fullyVisible =
			bounds.x >= rect.x &&
			bounds.y >= rect.y &&
			bounds.x + bounds.width <= rect.x + rect.width &&
			bounds.y + bounds.height <= rect.y + rect.height;

		if (!fullyVisible && visible && container.children?.length) {
			for (const child of container.children) {
				this.cullRecursive(rect, child);
			}
		}
	}

	private uncullRecursive(container: Container): void {
		container[this.toggle] = true;

		if (container.children?.length) {
			for (const child of container.children) {
				this.uncullRecursive(child);
			}
		}
	}

	private intersects(
		bounds: { x: number; y: number; width: number; height: number },
		rect: Rectangle,
	): boolean {
		return (
			bounds.x + bounds.width > rect.x &&
			bounds.x < rect.x + rect.width &&
			bounds.y + bounds.height > rect.y &&
			bounds.y < rect.y + rect.height
		);
	}
}
