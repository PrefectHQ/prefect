type ServerSettingsProps = {
	settings: Record<string, unknown>;
};

export const ServerSettings = ({ settings }: ServerSettingsProps) => {
	return (
		<div className="flex flex-col gap-1">
			<label htmlFor="server-settings">Server Settings</label>
			<div id="server-settings" className="p-2 bg-slate-100 rounded-sm">
				TODO: {JSON.stringify(settings)}
			</div>
		</div>
	);
};
