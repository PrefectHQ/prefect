import { ServerOff } from "lucide-react";

const NoConnection = () => {
  return (
    <div className="flex flex-col items-center h-full gap-4 p-8 text-center justify-center">
      <ServerOff className="w-12 h-12 text-gray-400" />
      <h2 className="text-xl font-semibold">Cannot Reach Prefect Server</h2>
      <p className="text-gray-600">
        Unable to connect to your Prefect server. Please check your server status and connection settings.
      </p>
    </div>
  );
};

export default NoConnection;
