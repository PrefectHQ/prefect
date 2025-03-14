import asyncio
import pdb
import queue
import sys
import threading
from io import StringIO

from prefect import get_run_logger
from prefect.context import FlowRunContext
from prefect.input.run_input import RunInput


class PDBInput(RunInput):
    command: str


class PDBResponse(RunInput):
    response: str


class RemotePDB(pdb.Pdb):
    def __init__(self, *args, **kwargs):
        flow_run_context = FlowRunContext.get()
        if not flow_run_context or not flow_run_context.flow_run:
            raise ValueError("RemotePDB must be used within a flow run")

        self.flow_run_id = flow_run_context.flow_run.id
        self.output_capture = StringIO()
        self.logger = get_run_logger()
        super().__init__(*args, stdout=self.output_capture, **kwargs)

        # Create command and response queues for async/sync bridging
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.terminate_thread = threading.Event()

        # Start background thread for async communication
        self.comm_thread = threading.Thread(target=self._handle_communication)
        self.comm_thread.daemon = True
        self.comm_thread.start()

        self.command_receiver = PDBInput.receive(
            flow_run_id=self.flow_run_id,
            key_prefix="prefect-remote-debugger-command",
            timeout=1,
        )

    def _handle_communication(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def communication_loop():
            while not self.terminate_thread.is_set():
                if not self.response_queue.empty():
                    response_text = self.response_queue.get()
                    response = PDBResponse(response=response_text)
                    await response.send_to(
                        flow_run_id=self.flow_run_id,
                        key_prefix="prefect-remote-debugger-response",
                    )
                    self.logger.info(f"Sent output to remote debugger: {response_text}")

                # Check for new commands
                try:
                    command = await self.command_receiver.next()
                    self.command_queue.put(command.command)
                    self.logger.info(
                        f"Received command from remote debugger: {command.command}"
                    )
                except TimeoutError:
                    pass

        loop.run_until_complete(communication_loop())

    def cmdloop(self):
        while True:
            self.output_capture.seek(0)
            output = self.output_capture.read()
            self.output_capture.truncate(0)
            self.output_capture.seek(0)

            self.response_queue.put(output)

            command = self.command_queue.get()

            self.onecmd(command)

    def do_continue(self, arg: str):
        """Override continue to ensure clean exit"""
        self.output_capture.seek(0)
        self.output_capture.truncate(0)
        self.output_capture.seek(0)
        self.response_queue.put("Continuing program execution...")
        return super().do_continue(arg)

    def do_quit(self, arg: str):
        """Override quit to ensure clean exit"""
        self.terminate_thread.set()
        self.response_queue.put("Quitting debugger...")
        return super().do_quit(arg)


def remote_pdb_breakpoint():
    debugger = RemotePDB()
    debugger.set_trace(sys._getframe().f_back)


def start_remote_debugger_at_exception():
    logger = get_run_logger()
    logger.error("Exception caught in, starting remote debugger")
    debugger = RemotePDB()
    _, _, exc_traceback = sys.exc_info()
    debugger.interaction(None, exc_traceback)
