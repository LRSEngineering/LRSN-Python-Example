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
import socket
import select
import sys
import xml.etree.ElementTree as ET
import errno
import os

def read(sock):
    """Reads through data in buffer and stops when
    there is no more data or a new line is received."""
    buf = ''
    while True:
        try:
            chunk = sock.recv(1024)
            buf += chunk

            if chunk == "" or "\n" in buf:
                # Ignore trailing newline
                return buf[:-1]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK and e.errno != errno.EAGAIN:
                print("Error reading from socket: {}".format(os.strerror(e.errno)))
                return None

# Create a socket for transmitter connection
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Connect to transmitter at LRSN port 3700
sock.connect((sys.argv[1], 3700))

# At this point, we should get an intro message from the transmitter.
# On the transmitter's LCD, you should see the client count increase
# from 0 to 1.
print("Got: {}".format(read(sock)))

# The payload should look like this:
# <LRSN services="NetPage:2.0;Config:1.0;Heartbeat:1.0;Inputs:1.0;PocsagRX:1.0;LrsRX:1.0;TableMan:1.0" device="T7470" swver="8.3.0.13" serno="20384" login="none" />
# It's now going to wait for a Login message. Here, you will want to
# define which services you are interested in. For majority use, NetPage
# and Heartbeat is what you'll want. NetPage provides paging access and
# Heartbeat provides pinging to help determine connection loss.
sock.sendall('<Login services="NetPage;Heartbeat" />\n')

# ! Don't forget to append a newline at the end. If you use a XML library
# ! to parse and compile XML nodes to send, ensure the resulting buffer
# ! has a newline at the end.

# If everything works out, a LoginAck XML node will be sent with a attribute "ret".
out = read(sock)

print("Got: {}".format(out))

# We'll parse the XML node to check to return code.
root = ET.fromstring(out)

logged_in = False

if root.tag == "LoginAck":
    # Get return code from attribute "ret". It will be a string, so the code should
    # be converted into an integer.
    return_code = int(root.attrib["ret"])

    # For all return codes, see
    # https://paging-systems.readme.io/docs/result-codes
    # For the purpose of logging in, we're only checking
    # to see if it's successful or not.
    if return_code == 0:
        # We have logged in.
        logged_in = True


# Set connection to non-blocking
sock.setblocking(0)

# We'll now enter a loop to expect heartbeats and status
# message to our paging requests.
while logged_in:
    pass

# Close connection
sock.close()
