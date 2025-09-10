import os
import uuid
import socket

def setup_trace_id(logger):
    """
    Generate a trace ID in Node.js style and set it in the logger.
    Returns the trace ID string.
    """
    pid = os.getpid()
    hostname = socket.gethostname()
    guid = str(uuid.uuid4())
    zero_pad = '0'.zfill(16)
    trace_id = f"{pid}@{hostname}/{guid}-{zero_pad}"
    logger.set_trace_id(trace_id)
    return trace_id
