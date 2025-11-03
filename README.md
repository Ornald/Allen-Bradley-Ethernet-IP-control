# Allen-Bradley-Ethernet-IP-control
Script allows to make a recon of the Allan Bradely PLCs with Ethernet/IP to figure out tags. With such tags it is possible to flood PLC with new values affecting the PLC control process.

### Requirements
- Python 3.8 or newer (3.10 recommended)
- External libraries:
  - argparse
  - pylogix
  - pandas
  - openpyxl

### Manual

The script has two operating modes:

**recon** – retrieves tags from specified PLCs. Example usage:
'''
python AllenBradley_CounterHack.py recon --ip_list 10.10.10.10,10.10.10.11,10.10.10.12 -o output.xlsx
'''

**Parameters:**
- recon (required) – mode of operation
- --ip_list (required) – specifies a comma-separated list of IP addresses from which tags will be fetched
- -o (required) – path to the file where tags will be saved. Required format: xlsx. If the file does not exist it will be created. If it exists it will be overwritten!

**_If any IP address is unresponsive the user will be informed and that address will be skipped_**.

**flood** – floods the specified PLCs with tags from a file. Example usage:
'''
python AllenBradley_CounterHack.py flood -f tags.xlsx
'''

**Parameters**:
- flood (required) – mode of operation
- -f (required) – path to the file that contains the tags

**_After selecting the flood option the script will prompt for the time interval (in seconds) between consecutive executions!_**


### Disclaimers
- The script does not work with PLC drivers: PLC5, SLC, MicroLogix, Micro8xx (they handle tags differently and the libraries used in the script cannot read them).
- The script supports primitive types and the types: TIMER, COUNTER, PID (it reads raw bytes and converts them into variables).
Note: only variables that can be safely overwritten are written to the xlsx file. For example, the Acc (accumulator) from a timer or counter is not printed to the file.
- For PID, TIMER and COUNTER tags I recommend also checking the documentation: https://literature.rockwellautomation.com/idc/groups/literature/documents/rm/1756-rm003_-en-p.pdf
- The script does not yet support Array data types. Currently it overwrites only the first value of an array. This is on the roadmap.
- **_!!!!The script fetches all tags. The user must manually verify which tags they want to overwrite and with what value.!!!!_**
