import type { DisplayObject } from "pixi.js";

type CullStatus = "hidden" | "visible";

// This culler intentionally uses the `visible` property to show and hide graphics
// this is because the viewport edge culling uses the `renderable` property and will
// interfere if the same property is used
export class VisibilityCull {
	private status: CullStatus = "visible";
	private readonly labels = new Set<DisplayObject>();

	private get visible(): boolean {
		return this.status === "visible";
	}

	public show(): void {
		if (this.status === "visible") {
			return;
		}

		for (const label of this.labels) {
			label.visible = true;
		}

		this.status = "visible";
	}

	public hide(): void {
		if (this.status === "hidden") {
			return;
		}

		for (const label of this.labels) {
			label.visible = false;
		}

		this.status = "hidden";
	}

	public toggle(visible: boolean): void {
		if (visible) {
			this.show();
		} else {
			this.hide();
		}
	}

	public add(label: DisplayObject): void {
		this.labels.add(label);

		label.visible = this.visible;
	}

	public clear(): void {
		this.labels.clear();
	}
}
