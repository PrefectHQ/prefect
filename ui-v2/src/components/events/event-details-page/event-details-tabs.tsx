import type { Event } from "@/api/events";
import { JsonView } from "@/components/ui/json-view";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EventDetailsDisplay } from "./event-details-display";

type EventDetailsTabsProps = {
	event: Event;
	defaultTab?: "details" | "raw";
	onTabChange?: (tab: string) => void;
};

export function EventDetailsTabs({
	event,
	defaultTab = "details",
	onTabChange,
}: EventDetailsTabsProps) {
	return (
		<Tabs defaultValue={defaultTab} onValueChange={onTabChange}>
			<TabsList>
				<TabsTrigger value="details">Details</TabsTrigger>
				<TabsTrigger value="raw">Raw</TabsTrigger>
			</TabsList>
			<TabsContent value="details" className="pt-4">
				<EventDetailsDisplay event={event} />
			</TabsContent>
			<TabsContent value="raw" className="pt-4">
				<JsonView
					value={JSON.stringify(event, null, 2)}
					className="max-h-[600px] overflow-auto"
				/>
			</TabsContent>
		</Tabs>
	);
}
