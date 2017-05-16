# LRS Python LRSN Example Script
This is a example script used to demonstrate using the LRSN API for integrators wishing
to send page requests programatically.

Currently, the example script only focuses on NetPage and Heartbeat which are the two expected
services to use when using the API. For more information, please refer to
[LRSN ReadMe.io](https://paging-systems.readme.io/docs/welcome-to-the-lrsn-protocol)

## Usage
This script can be run from Python 2 or 3. If there are any issues, please log an issue
under this GitHub repo.

```
python lrsn-example.py [-h] [-s SYSTEMID] [IP ADDRESS]
```

You must know the IP address of the transmitter. You can find it by going into Setup -> Diagnostics -> System Status, hitting MORE until you see "Host IP:". If you do not see a valid IP, Network may not be enabled on
the transmitter. You can enable it by going into Setup -> Other -> (Down) -> Network -> Config Network, then ffollow the prompts to enable/disable network connectivity.
