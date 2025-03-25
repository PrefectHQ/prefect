import { JsonInput } from "@/components/ui/json-input";

type ServerSettingsProps = {
	settings: Record<string, unknown>;
};

export const ServerSettings = ({ settings }: ServerSettingsProps) => {
	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="server-settings">Server Settings</label>
			<JsonInput
				id="server-settings"
				className="p-2 rounded-sm"
				value={JSON.stringify(settings, null, 2)}
				disabled
				hideLineNumbers
			/>
		</div>
	);
};
