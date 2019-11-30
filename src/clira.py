#
# Start with a command, such as:
# jupyter console --KernelManager.kernel_cmd="['python', 'src/clira.py',
#                                              '{connection_file}']"

import sys
import json
import hmac
import uuid
import errno
import hashlib
import datetime
import time
import threading
from pprint import pformat

# zmq specific imports:
import zmq
from zmq.eventloop import ioloop, zmqstream
from zmq.error import ZMQError

# Globals:
DELIM = b"<IDS|MSG>"
data_ident = 1

debug_level = 3  # 0 (none) to 3 (all) for various levels of detail

exiting = False
engine_id = str(uuid.uuid4())

# Utility functions:


def shutdown():
    global exiting
    exiting = True
    ioloop.IOLoop.instance().stop()


def dprint(level, *args, **kwargs):
    """ Show debug information """

    if level <= debug_level:
        print("DEBUG:", *args, **kwargs)
        sys.stdout.flush()


def msg_id():
    """ Return a new uuid for message id """

    return str(uuid.uuid4())


def str_to_bytes(s):
    return s.encode('ascii')


def decode(msg):
    return json.loads(msg.decode('ascii'))


def sign(msg_lst):
    """
    Sign a message with a secure signature.
    """

    h = auth.copy()
    for m in msg_lst:
        h.update(m)
    return str_to_bytes(h.hexdigest())


def new_header(msg_type):
    """make a new header"""

    return {
        "date": datetime.datetime.now().isoformat(),
        "msg_id": msg_id(),
        "username": "kernel",
        "session": engine_id,
        "msg_type": msg_type,
        "version": "5.0",
    }


def send(stream, msg_type, content=None,
        parent_header=None, metadata=None, identities=None):

    header = new_header(msg_type)
    if content is None:
        content = {}
    if parent_header is None:
        parent_header = {}
    if metadata is None:
        metadata = {}

    def encode(msg):
        return str_to_bytes(json.dumps(msg))

    msg_lst = [
        encode(header),
        encode(parent_header),
        encode(metadata),
        encode(content),
    ]
    signature = sign(msg_lst)
    parts = [DELIM,
             signature,
             msg_lst[0],
             msg_lst[1],
             msg_lst[2],
             msg_lst[3]]
    if identities:
        parts = identities + parts
    dprint(3, "send parts:", parts)
    stream.send_multipart(parts)
    stream.flush()


def run_thread(loop, name):
    dprint(2, "Starting loop for '%s'..." % name)
    while not exiting:
        dprint(2, "%s Loop!" % name)
        try:
            loop.start()
        except ZMQError as e:
            dprint(2, "%s ZMQError!" % name)
            if e.errno == errno.EINTR:
                continue
            else:
                raise
        except Exception:
            dprint(2, "%s Exception!" % name)
            if exiting:
                break
            else:
                raise
        else:
            dprint(2, "%s Break!" % name)
            break


def heartbeat_loop():
    dprint(2, "Starting loop for 'Heartbeat'...")
    while not exiting:
        dprint(3, ".", end="")
        try:
            zmq.device(zmq.FORWARDER, heartbeat_socket, heartbeat_socket)
        except zmq.ZMQError as e:
            if e.errno == errno.EINTR:
                continue
            else:
                raise
        else:
            break


# Socket Handlers:
def shell_handler(msg):
    global execution_count
    dprint(1, "shell received:", msg)
    position = 0
    identities, msg = deserialize_wire_msg(msg)

    # process request:

    if msg['header']["msg_type"] == "execute_request":
        dprint(1, "clira_kernel Executing:", pformat(msg['content']["code"]))
        content = {
            'execution_state': "busy",
        }
        send(iopub_stream, 'status', content, parent_header=msg['header'])
        #######################################################################
        content = {
            'execution_count': execution_count,
            'code': msg['content']["code"],
        }
        send(iopub_stream, 'execute_input',
             content, parent_header=msg['header'])
        #######################################################################
        content = {
            'name': "stdout",
            'text': "hello, world",
        }
        send(iopub_stream, 'stream', content, parent_header=msg['header'])

        global data_ident
        data_ident += 1

        html = "<p>this <i>is</i> a second test...</p>"
        content = {
            'data': {
                "text/html": html,
            },
            'metadata': {},
            'transient': {
                'display_id': data_ident,
            },
        }
        send(iopub_stream, 'display_data',
             content, parent_header=msg['header'])

        time.sleep(10)
        html += "<p>more <s>data</s></data>"
        content['data']['text/html'] = html
        send(iopub_stream, 'update_display_data',
             content, parent_header=msg['header'])

        #######################################################################
        content = {
            'execution_count': execution_count,
            'data': {"text/plain": "result!"},
            'metadata': {}
        }
        send(iopub_stream, 'execute_result',
             content, parent_header=msg['header'])
        #######################################################################
        content = {
            'execution_state': "idle",
        }
        send(iopub_stream, 'status', content, parent_header=msg['header'])
        #######################################################################
        metadata = {
            "dependencies_met": True,
            "engine": engine_id,
            "status": "ok",
            "started": datetime.datetime.now().isoformat(),
        }
        content = {
            "status": "ok",
            "execution_count": execution_count,
            "user_variables": {},
            "payload": [],
            "user_expressions": {},
        }
        send(shell_stream, 'execute_reply', content, metadata=metadata,
             parent_header=msg['header'], identities=identities)
        execution_count += 1
    elif msg['header']["msg_type"] == "kernel_info_request":
        content = {
            "protocol_version": "5.0",
            "ipython_version": [1, 1, 0, ""],
            "language_version": [0, 0, 1],
            "language": "clira",
            "implementation": "clira",
            "implementation_version": "1.1",
            "language_info": {
                "name": "clira",
                "version": "1.0",
                'mimetype': "",
                'file_extension': ".py",
                'pygments_lexer': "",
                'codemirror_mode': "",
                'nbconvert_exporter': "",
            },
            "banner": ""
        }
        send(shell_stream, 'kernel_info_reply', content,
             parent_header=msg['header'], identities=identities)
    elif msg['header']["msg_type"] == "history_request":
        dprint(1, "unhandled history request")
    else:
        dprint(1, "unknown msg_type:", msg['header']["msg_type"])


def deserialize_wire_msg(wire_msg):
    """split the routing prefix and message frames from a message on the wire"""

    delim_idx = wire_msg.index(DELIM)
    identities = wire_msg[:delim_idx]
    m_signature = wire_msg[delim_idx + 1]
    msg_frames = wire_msg[delim_idx + 2:]

    m = {}
    m['header'] = decode(msg_frames[0])
    m['parent_header'] = decode(msg_frames[1])
    m['metadata'] = decode(msg_frames[2])
    m['content'] = decode(msg_frames[3])
    check_sig = sign(msg_frames)
    if check_sig != m_signature:
        raise ValueError("Signatures do not match")

    return identities, m


def control_handler(wire_msg):
    dprint(1, "control received:", wire_msg)
    identities, msg = deserialize_wire_msg(wire_msg)
    # Control message handler:
    if msg['header']["msg_type"] == "shutdown_request":
        shutdown()


def iopub_handler(msg):
    dprint(1, "iopub received:", msg)


def stdin_handler(msg):
    dprint(1, "stdin received:", msg)


def bind(socket, connection, port):
    if port <= 0:
        return socket.bind_to_random_port(connection)
    else:
        socket.bind("%s:%s" % (connection, port))
    return port


# Initialize:
ioloop.install()

if len(sys.argv) > 1:
    dprint(1, "Loading clira_kernel with args:", sys.argv)
    dprint(1, "Reading config file '%s'..." % sys.argv[1])
    config = json.loads("".join(open(sys.argv[1]).readlines()))
else:
    dprint(1, "Starting clira kernel with default args...")
    config = {
        'control_port': 0,
        'hb_port': 0,
        'iopub_port': 0,
        'ip': '127.0.0.1',
        'key': str(uuid.uuid4()),
        'shell_port': 0,
        'signature_scheme': 'hmac-sha256',
        'stdin_port': 0,
        'transport': 'tcp'
    }

connection = config["transport"] + "://" + config["ip"]
secure_key = str_to_bytes(config["key"])
signature_schemes = {"hmac-sha256": hashlib.sha256}
auth = hmac.HMAC(
    secure_key,
    digestmod=signature_schemes[config["signature_scheme"]])
execution_count = 1

##########################################
# Heartbeat:
ctx = zmq.Context()
heartbeat_socket = ctx.socket(zmq.REP)
config["hb_port"] = bind(heartbeat_socket, connection, config["hb_port"])

##########################################
# IOPub/Sub:
# aslo called SubSocketChannel in IPython sources
iopub_socket = ctx.socket(zmq.PUB)
config["iopub_port"] = bind(iopub_socket, connection, config["iopub_port"])
iopub_stream = zmqstream.ZMQStream(iopub_socket)
iopub_stream.on_recv(iopub_handler)

##########################################
# Control:
control_socket = ctx.socket(zmq.ROUTER)
config["control_port"] = bind(
    control_socket, connection, config["control_port"])
control_stream = zmqstream.ZMQStream(control_socket)
control_stream.on_recv(control_handler)

##########################################
# Stdin:
stdin_socket = ctx.socket(zmq.ROUTER)
config["stdin_port"] = bind(stdin_socket, connection, config["stdin_port"])
stdin_stream = zmqstream.ZMQStream(stdin_socket)
stdin_stream.on_recv(stdin_handler)

##########################################
# Shell:
shell_socket = ctx.socket(zmq.ROUTER)
config["shell_port"] = bind(shell_socket, connection, config["shell_port"])
shell_stream = zmqstream.ZMQStream(shell_socket)
shell_stream.on_recv(shell_handler)

dprint(1, "Config:", json.dumps(config))
dprint(1, "Starting loops...")

hb_thread = threading.Thread(target=heartbeat_loop)
hb_thread.daemon = True
hb_thread.start()

dprint(1, "Ready! Listening...")

ioloop.IOLoop.instance().start()