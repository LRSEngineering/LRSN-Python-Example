"""
Copyright (c) 2017, Long Range Systems, LLC
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of [project] nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import argparse
import socket
import select
import sys
import xml.etree.ElementTree as ET
import errno
import os
import logging
import sys
import time
from threading import Event, Thread
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s %(levelname)s - %(message)s')
fh = logging.FileHandler('lrsn.log')
# ch = logging.StreamHandler()
# ch.setLevel(logging.DEBUG)
# ch.setFormatter(formatter)
fh.setFormatter(formatter)
# log.addHandler(ch)
log.addHandler(fh)

# Quit event to set when to close socket and end thread and user input loops.
t_quit = Event()

# Reconnect event
t_reconn = Event()

def read(sock, quit_event=None, timeout=5):
    """Reads through data in buffer and stops when
    there is no more data or a new line is received."""
    buf = b''
    start = time.time()
    while quit_event is None or not quit_event.isSet():
        try:
            chunk = sock.recv(1024)
            buf += chunk
            if chunk == b"" or b"\n" in buf:
                # Ignore trailing newline
                return buf[:-1]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK and e.errno != errno.EAGAIN:
                log.error("Error reading from socket: {}".format(os.strerror(e.errno)))
                return None
            
        if time.time() - start >= timeout:
            return None

def lrsn_listener(sock, quit_event=None):
    """Listener for LRSN messages such as Heartbeat and PageRequestStatus.
    Will log messages and keep track of heartbeats and whether to disconnect.
    """
    first_heartbeat_recieved = False
    last_heartbeat = -1
    heartbeat_interval = -1

    # We'll now enter a loop to expect heartbeats and status
    # message to our paging requests.
    while (quit_event is None or not quit_event.isSet()):
        # Read and parse incoming XML
        out = read(sock, t_quit)
        
        if t_quit.isSet():
            break;
        
        if out is not None:
            root = ET.fromstring(out)
            log.info("Got: {}".format(out))
        
            if root.tag == "Heartbeat":
                # Keep track of heartbeats
                heartbeat_interval = int(root.attrib["interval"])
                last_heartbeat = time.time()
                first_heartbeat_recieved = True
        else:
            # Check heartbeat time window
            if first_heartbeat_recieved and time.time() - last_heartbeat > heartbeat_interval:
                # Did not receive a heartbeat since the last time within
                # the interval. Break out, close, and reconnect.
                log.info("Did not receive LRSN Heartbeat within {} since {}. Closing.".format(heartbeat_interval, last_heartbeat))
                t_reconn.set()
                break
            
        # Idle
        time.sleep(0.1)
    
def compat_input(msg):
    if sys.version_info[0] >= 3:
        return input(msg)
    else:
        return raw_input(msg)

def main(ip_address, system_id=None):
    # Create a socket for transmitter connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(1)

    # Connect to transmitter at LRSN port 3700
    try:
        sock.connect((ip_address, 3700))
    except socket.error as e:
        log.error("Unable to connect to {}:3700 - {}".format(ip_address, os.strerror(e.errno)))
        print("Unable to connect to {}:3700 - {}".format(ip_address, os.strerror(e.errno)))
        
        # If we're in the process of reconnecting, don't quit.
        if not t_reconn.isSet():
            t_quit.set()
        
        return

    # If this is a retry of a connection and it succeeds,
    # we can clear it.
    if t_reconn.isSet():
        t_reconn.clear()

    # At this point, we should get an intro message from the transmitter.
    # On the transmitter's LCD, you should see the client count increase
    # from 0 to 1.
    log.info("Got: {}".format(read(sock)))

    # The payload should look like this:
    # <LRSN services="NetPage:2.0;Config:1.0;Heartbeat:1.0;Inputs:1.0;PocsagRX:1.0;LrsRX:1.0;TableMan:1.0" device="T7470" swver="8.3.0.13" serno="20384" login="none" />
    # It's now going to wait for a Login message. Here, you will want to
    # define which services you are interested in. For majority use, NetPage
    # and Heartbeat is what you'll want. NetPage provides paging access and
    # Heartbeat provides pinging to help determine connection loss. When the transmitter
    # sends a heartbeat and the underlying TCP Ack is not received, then it will
    # reset the connection.
    try:
        sock.sendall(b'<Login services="NetPage;Heartbeat" />\n')
    except socket.error as e:
        log.error("Unable to send PageRequest. Attempting to reconnect.")
        t_reconn.set()
        sock.close()
        return

    # ! Don't forget to append a newline at the end. If you use a XML library
    # ! to parse and compile XML nodes to send, ensure the resulting buffer
    # ! has a newline at the end.

    # If everything works out, a LoginAck XML node will be sent with a attribute "ret".
    out = read(sock)

    log.info("Got: {}".format(out))

    # We'll parse the XML node to check to return code.
    root = ET.fromstring(out)

    logged_in = False
    if root.tag == "LoginAck":
        # Get return code from attribute "ret". It will be a num berstring,
        # so the code should be converted into an integer.
        return_code = int(root.attrib["ret"])

        # For all return codes, see
        # https://paging-systems.readme.io/docs/result-codes
        # For the purpose of logging in, we're only checking
        # to see if it's successful or not.
        if return_code == 0:
            # We have logged in.
            logged_in = True
        else:
            # Anything else, we'll print out
            log.info("Unable to log in. Received: {}".format(return_code))
            sock.close()
            t_reconn.set()
            return

    # Set connection to non-blocking
    sock.setblocking(0)


    if not logged_in:
        print("Cannot log in. Retrying...")
        # Wait 5 seconds before reattempting.
        time.sleep(5)
        t_reconn.set()
        try:
            sock.close()
        except socket.error:
            pass
        return
        
    # Start listener thread
    listener = Thread(target=lrsn_listener, args=(sock,))
    listener.start()

    page_request_id = 1

    # Start input loop. Break out if user explicitely quits or there needs to be
    # a reconnect.
    while not t_quit.isSet() and not t_reconn.isSet():
        number = compat_input("\nType a page number or type quit: ")
        
        if number == "":
            continue
        elif number == "quit":
            t_quit.set()
            break
        
        # Verify pager number
        try:
            number = int(number)
        except ValueError:
            print("Invalid number. Try again.")
            continue
            
        pager_type = compat_input("\nEnter pager type by number (e.g. 0=>AlphaPager): ")
        
        # Verify pager type
        try:
            pager_type = int(pager_type)
            
            # 0 - Alphanumeric POCSAG pager
            # 1 - Numeric POCSAG pager
            # 2 - LRS guest pager (coaster, Adverteaser, specialty)
            # 3 - Star pager (LRS staff pager)
            # 4 - Vibe-only POCSAG pager
            if pager_type < 0 or pager_type > 4:
                raise ValueError
        except ValueError:
            print("Invalid pager type. Try again.")
            continue
        
        # System ID attribute if provided.
        if system_id:
            system_id_attr = 'system_id="{}"'.format(system_id)
        else:
            system_id_attr = ''
        
        if pager_type == 0:
            message = compat_input("\nType a message: ")
        else:
            # This could be any page mode, but we'll keep it constantly as Vibe1
            # as an example.
            message = 'Vibe1'
        
        try:
            # Don't forget the newline at then end!
            sock.sendall('<PageRequest id="{}" pager="{};{}" message="{}" {} />\n'.format(page_request_id, pager_type, number, message, system_id_attr).encode('utf-8'))
        except socket.error as e:
            log.error("Unable to send PageRequest. Attempting to reconnect.")
            t_reconn.set()
            
        # Increment page request id.
        page_request_id += 1

    # Stop listener thread
    listener.join()

    # Close connection
    try:
        sock.close()
    except:
        pass
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='LRSN Python Example Client.')
    parser.add_argument('ipaddress', help='IP Address of transmitter.', type=str)
    parser.add_argument('-s', '--systemid', help='System ID to use for transmitter.', type=int)
    args = parser.parse_args()
    
    while not t_quit.isSet():
        try:
            main(args.ipaddress, system_id=args.systemid)
            
            if t_reconn.isSet():
                time.sleep(5)
                log.info("Reconnecting...")
        except KeyboardInterrupt:
            print("Closing...")
            t_quit.set()
