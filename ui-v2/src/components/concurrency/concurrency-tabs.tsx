import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TAB_OPTIONS, TabOptions } from "./concurrency-constants";

type Props = {
	globalView: React.ReactNode;
	onValueChange: (value: TabOptions) => void;
	taskRunView: React.ReactNode;
	value: TabOptions;
};

// TODO: Move Tabs for navigation to a generic styled component

export const ConcurrencyTabs = ({
	globalView,
	onValueChange,
	taskRunView,
	value,
}: Props): JSX.Element => {
	return (
		<Tabs
			defaultValue="Global"
			className="w-[400px]"
			value={value}
			onValueChange={(value) => onValueChange(value as TabOptions)}
		>
			<TabsList className="grid w-full grid-cols-2">
				<TabsTrigger value="Global">{TAB_OPTIONS.Global}</TabsTrigger>
				<TabsTrigger value="Task Run">{TAB_OPTIONS["Task Run"]}</TabsTrigger>
			</TabsList>
			<TabsContent value={TAB_OPTIONS.Global}>{globalView}</TabsContent>
			<TabsContent value={TAB_OPTIONS["Task Run"]}>{taskRunView}</TabsContent>
		</Tabs>
	);
};
