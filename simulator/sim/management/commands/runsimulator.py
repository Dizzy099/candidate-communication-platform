"""Run the SimuText simulator: HTTP API + webhook dispatcher in one process.

    python manage.py runsimulator --port 8001
"""

import logging
import os
import socketserver
import threading
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.core.wsgi import get_wsgi_application

from sim.dispatcher import run_dispatcher

logger = logging.getLogger(__name__)


class ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - signature from the stdlib
        logger.info("%s %s", self.address_string(), format % args)


class Command(BaseCommand):
    help = "Run the SimuText provider simulator (API + webhook dispatcher)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default=os.getenv("SIM_HOST", "127.0.0.1"))
        parser.add_argument("--port", type=int, default=int(os.getenv("SIM_PORT", "8001")))
        parser.add_argument("--migrate", action="store_true", help="Apply migrations before starting.")

    def handle(self, *args, **options):
        if options["migrate"]:
            call_command("migrate", interactive=False, verbosity=0)
        stop = threading.Event()
        dispatcher = threading.Thread(target=run_dispatcher, args=(stop,), name="dispatcher", daemon=True)
        dispatcher.start()
        server = make_server(
            options["host"], options["port"], get_wsgi_application(),
            server_class=ThreadingWSGIServer, handler_class=QuietHandler,
        )
        self.stdout.write(f"SimuText simulator listening on http://{options['host']}:{options['port']}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            server.server_close()
            self.stdout.write("SimuText simulator stopped.")
