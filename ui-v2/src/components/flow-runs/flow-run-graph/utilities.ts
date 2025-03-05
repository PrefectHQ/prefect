export function isEventTargetInput(target: EventTarget | null): boolean {
	if (!target || !(target instanceof HTMLElement)) {
		return false;
	}
	return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}
