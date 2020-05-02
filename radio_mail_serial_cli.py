import time
import board
import busio
import digitalio
import adafruit_rfm9x
import supervisor

STATE_IDLE = 0
STATE_WAITING_FOR_SEND_CONTENT = 1

state = STATE_IDLE

# Define radio parameters.
RADIO_FREQ_MHZ = 915.0  # Frequency of the radio in Mhz. Must match your
# module! Can be a value like 915.0, 433.0, etc.

# Define pins connected to the chip.
# set GPIO pins as necessary - this example is for Featherwing using D10 and D11
CS = digitalio.DigitalInOut(board.D10)
RESET = digitalio.DigitalInOut(board.D11)

# Initialize SPI bus.
spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)
# Initialze RFM radio
rfm9x = adafruit_rfm9x.RFM9x(spi, CS, RESET, RADIO_FREQ_MHZ)

# enable CRC checking
rfm9x.enable_crc = True
# set delay before transmitting ACK (seconds)
rfm9x.ack_delay = 0.1
# set starting node addresses
rfm9x.node = 2

rfm9x.destination = 1

# list for received incoming messages.
inbox = []

# list for undelivered outgoing messages.
undelivered_messages = []


def send(to_address=None):
    global state
    if to_address == None:
        print("Must pass to_addres e.g. 'send 2' run 'help' for more.")
        return
    rfm9x.destination = int(to_address)
    print("Enter message: ")
    state = STATE_WAITING_FOR_SEND_CONTENT


def list_msgs():
    print("Index | From | Message ID")
    print("=" * 30)
    for i, msg in enumerate(inbox):
        print("{} | {} | {}".format(i, msg['from'], msg['message_id']))
    print()


def read(index=None):
    if index == None:
        print("Must pass index e.g. 'read 0' run 'list' to see indexes. Run 'help' for more.")
        print()
        return
    index = int(index)
    if index < len(inbox):
        print("From: {}".format(inbox[index]['from']))
        data_string = ''.join([chr(b) for b in inbox[index]['content']])
        print("Message: {}".format(data_string))
        print()
    else:
        print("index {} out of bounds. run 'list' to see indexes. run 'help' for more.".format(index))
        print()


def delete(index):
    if index == None:
        print("Must pass index e.g. 'delete 0' run 'list' to see indexes. Run 'help' for more.")
        print()
        return
    index = int(index)
    if index < len(inbox):
        print("Deleting Message {}".format(index))
        del inbox[index]
        print()
    else:
        print("index {} out of bounds. Run 'list' to see indexes. Run 'help' for more.".format(index))
        print()


def undelivered():
    print("Index | To | Message Content")
    print("=" * 30)
    for i, msg in enumerate(undelivered_messages):
        print("{} | {} | {}".format(i, msg['to'], msg['content']))
    print()


def resend(undelivered_index=None):
    if undelivered_index == None:
        print("Must pass undelivered_index e.g. 'resend 0' run 'help' for more.")
        print()
        return
    undelivered_index = int(undelivered_index)
    msg_obj = undelivered_messages[undelivered_index]
    del undelivered_messages[undelivered_index]
    rfm9x.destination = int(msg_obj['to'])
    if not rfm9x.send_with_ack(
            bytes(msg_obj['content'], "UTF-8")
    ):
        print("Did not receive ACK. Messaged marked as undelivered.")
        undelivered_messages.append({"to": rfm9x.destination, "content": msg_obj['content']})
    else:
        print("Recevied ACK")
    print("")


def node(new_node=None):
    if new_node == None:
        print("Node Address: {}".format(rfm9x.node))
        print()
        return
    else:
        rfm9x.node = int(new_node)
        print("Node Address Set To: {}".format(new_node))
        print()
        return


def mail_help():
    print("CLI Mail System Help:\n")
    print("read [index] - e.g. 'read 0' Print the contents the message with index specified\n")
    print("list - Print all messages from the inbox.\n")
    print(
        "send [address] - e.g. 'send 8' Initiate a new message to the specified address. You will be prompted for the message contenets.\n")
    print("help - Print this help message.\n")
    print("delete [index] - e.g. 'delete 0' Delete the message with the index specified from the inbox.\n")
    print(
        "address [optional_new_address] e.g. 'address' or 'address 3' Print the current address, or set the address to the one specified.\n")
    print("undelivered - Print all undelivered messages. Shows indexes used with resend.\n")
    print(
        "resend [undelivered_index] - e.g. 'resend 0' Attempt to resend the undelivered message with the specified index. Run 'undelivered' to see indexes.\n")


COMMAND_MAP = {
    "read": read,
    "send": send,
    "list": list_msgs,
    "undelivered": undelivered,
    "delete": delete,
    "resend": resend,
    "address": node,
    "help": mail_help
}


def serial_command_read():
    if supervisor.runtime.serial_bytes_available:
        value = input()
        # print("you sent: %s" % value)
        parts = value.split(" ")
        if parts[0] in COMMAND_MAP.keys():
            try:
                if len(parts) > 1:
                    COMMAND_MAP[parts[0]](parts[1])
                else:
                    COMMAND_MAP[parts[0]]()
            except Exception as e:
                print(e)
                print("Command failed: '%s' try 'help'" % value)
                print()
        else:
            print("Command not fount: '%s' try 'help'" % parts[0])
            print()


def serail_send_content_read():
    global state
    if supervisor.runtime.serial_bytes_available:
        value = input()
        # send message with value as body
        print("sending: {} - {}".format(rfm9x.destination, value))
        if not rfm9x.send_with_ack(
                bytes(value, "UTF-8")
        ):
            print("Did not receive ACK. Messaged marked as undelivered.")
            undelivered_messages.append({"to": rfm9x.destination, "content": value})
        else:
            print("Recevied ACK")
        print()
        state = STATE_IDLE


print("Welcome to CLI Mail System. Currently listening on address {}".format(rfm9x.node))
print("Run 'address [new_address]' to change to a different address. Run 'help' for more.")
while True:
    packet = rfm9x.receive(with_ack=True, with_header=True)
    # If no packet was received during the timeout then None is returned.
    if packet is not None:
        # handle incoming packet
        from_address = hex(packet[1])
        message_id = hex(packet[2])
        content = packet[4:]
        inbox.append({
            "from": from_address,
            "content": content,
            "message_id": message_id
        })
        print("New Message Arrived!")
        print()

    if state == STATE_IDLE:
        serial_command_read()
    elif state == STATE_WAITING_FOR_SEND_CONTENT:
        serail_send_content_read()
