import logging

import sdk_reforge
from sdk_reforge import Options


def on_starting(server):
    logging.warning("Starting server")
    sdk_reforge.set_options(Options(collect_sync_interval=5))
    logging.warning(
        f"current value of 'foobar' is {sdk_reforge.get_client().get('foobar')}"
    )


def post_worker_init(worker):
    # Initialize the client for each worker
    sdk_reforge.reset_instance()


def on_exit(server):
    logging.warning("shutting down reforge")
    sdk_reforge.reset_instance()
