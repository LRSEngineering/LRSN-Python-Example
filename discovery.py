"""
Copyright (c) 2017, Long Range Systems, LLC
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 - Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

 - Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

 - Neither the name of Long Range Systems, LLC nor the names of its contributors may
   be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
import socket
import select

def listen():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setblocking(0)

    try:
        # Bind to any interface
        s.bind(('', 3701))
    except socket.error as e:
        print("Unable to bind to socket to listen for transmitter!")
        return

    # Loop until we see the first LRSN broadcast service.
    while True:
        # Wait 30 seconds or until we find a broadcast message.
        rqueue, _, _ = select.select([s], [], [], 30)

        try:
            data, addr = s.recvfrom(1024)
        except socket.error as e:
            print("Socket Error", e)
            pass
        else:
            # We found a service from the transmitter!
            if data == '_lrsn-netpage._tcp':
                # We got it. Return only the address portion.
                return addr[0]

if __name__ == '__main__':
    transmitter_addr = listen()
    # Now we can connect to LRSN. Port will be 3700...
    print("Connecting to {}:{}".format(transmitter_addr, 3700))
