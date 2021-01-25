import json
import threading

from RPi import GPIO
from datetime import datetime
import time
import sys
import zmq
import logging

from Constants import Button as ButtonConstant
from Constants import RightButton as RightButtonConstant
from Constants import LeftButton as LeftButtonConstant
from Constants import RearButton as RearButtonConstant
from Constants import Color as ColorConstant
from Constants import LightServer as LightServerConstant

from PhysicalButton import PhysicalButton
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

right_colors = [ColorConstant.BLACK, ColorConstant.BLACK, ColorConstant.BLACK]
left_colors = [ColorConstant.BLACK, ColorConstant.BLACK, ColorConstant.BLACK]
rear_colors = [ColorConstant.BLACK, ColorConstant.BLACK, ColorConstant.BLACK]

right_button = PhysicalButton(RightButtonConstant.NAME,
                              RightButtonConstant.RED_PIN,
                              RightButtonConstant.GREEN_PIN,
                              RightButtonConstant.BLUE_PIN,
                              RightButtonConstant.TRIGGER_PIN)

left_button = PhysicalButton(LeftButtonConstant.NAME,
                             LeftButtonConstant.RED_PIN,
                             LeftButtonConstant.GREEN_PIN,
                             LeftButtonConstant.BLUE_PIN,
                             LeftButtonConstant.TRIGGER_PIN)

rear_button = PhysicalButton(RearButtonConstant.NAME,
                             RearButtonConstant.RED_PIN,
                             RearButtonConstant.GREEN_PIN,
                             RearButtonConstant.BLUE_PIN,
                             RearButtonConstant.TRIGGER_PIN)

def run_message_server():
    while True:
        #  Wait for next request from client
        message = incoming_socket.recv()
        incoming_socket.send(b"ack")
        logging.info("Received request: %s" % message)
        data = json.loads(message.decode('utf-8'))


        global right_colors
        global left_colors
        global rear_colors

        right_colors = data['right_colors']
        left_colors = data['left_colors']
        rear_colors = data['rear_colors']

        right_button.set_button_color(right_colors[0])
        left_button.set_button_color(left_colors[0])
        rear_button.set_button_color(rear_colors[0])

        time.sleep(1)

context = zmq.Context()
incoming_socket = context.socket(zmq.REP)
incoming_socket.bind("tcp://{}:{}".format(LightServerConstant.INCOMING_ADDR, LightServerConstant.SERVER_TO_ME_PORT))
socket_thread = threading.Thread(target=run_message_server)


def on_right_button_press(channel):
    on_button_press(right_button, right_colors)


def on_left_button_press(channel):
    on_button_press(left_button, left_colors)


def on_rear_button_press(channel):
    on_button_press(rear_button, rear_colors)

def send_to_light_server(data):
    logging.info("Connecting to server…")
    client = context.socket(zmq.REQ)
    client.connect("tcp://{}:{}".format(LightServerConstant.IP_ADDR, LightServerConstant.ME_TO_SERVER_PORT))

    request = str(data).encode()
    logging.info("Sending (%s)", request)
    client.send(request)

    retries_left = LightServerConstant.REQUEST_RETRIES
    while True:
        if (client.poll(LightServerConstant.REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
            reply = client.recv()
            if reply == b"ack":
                logging.info("Server replied OK (%s)", reply)
                break
            else:
                logging.error("Malformed reply from server: %s", reply)
                continue

        retries_left -= 1
        logging.warning("No response from server")
        # Socket is confused. Close and remove it.
        client.setsockopt(zmq.LINGER, 0)
        client.close()
        if retries_left == 0:
            logging.error("Server seems to be offline, abandoning")
            return

        logging.info("Reconnecting to server…")
        # Create new connection
        client = context.socket(zmq.REQ)
        client.connect("tcp://{}:{}".format(LightServerConstant.IP_ADDR, LightServerConstant.ME_TO_SERVER_PORT))
        logging.info("Resending (%s)", request)
        client.send(request)

button_pressed = False
def on_button_press(button, colors):
    global button_pressed
    try:
        if button_pressed:
            return
        button_pressed = True
        button_start_press_time = time.time()
        button_press_time = 0
        has_long_press_been_set = False
        has_short_press_been_set = False
        time.sleep(0.01)

        while GPIO.input(button.trigger_pin) == ButtonConstant.BUTTON_PRESSED_VALUE and \
                button_press_time < ButtonConstant.EXTRA_LONG_PRESS_MIN:  # Wait for the button up

            button_press_time, has_long_press_been_set, has_short_press_been_set = \
                button.handle_button_color(button_start_press_time, has_long_press_been_set, has_short_press_been_set,
                                           colors)
        logging.info("{} Button pressed for {} seconds".format(button.name, round(button_press_time, 3)))

        send_to_light_server("%s~%f" % (button.name, button_press_time))

    except Exception:
        t, v, tb = sys.exc_info()
        logging.error("An error was encountered of type: {}".format(t))
        logging.error("Value: {}".format(v))
        logging.error(str(tb))
        raise
    finally:
        button_pressed = False

def init():
    logging.info('Starting')

    GPIO.add_event_detect(right_button.trigger_pin, GPIO.RISING, callback=on_right_button_press,
                          bouncetime=ButtonConstant.BOUNCE_TIME_MS)

    GPIO.add_event_detect(left_button.trigger_pin, GPIO.RISING, callback=on_left_button_press,
                          bouncetime=ButtonConstant.BOUNCE_TIME_MS)

    GPIO.add_event_detect(rear_button.trigger_pin, GPIO.RISING, callback=on_rear_button_press,
                          bouncetime=ButtonConstant.BOUNCE_TIME_MS)

    socket_thread.start()

if __name__ == '__main__':
    print("Hello World")
    # data = [
    #     [0,1,2],
    #     [3,4,5],
    #     [10, 345,10]
    # ]
    # res = json.dumps(data)
    # print(data)
    init()
    #
    while True:
        time.sleep(1)

    #     try:
    #         pass
    #         # for color in ColorConstant.EACH:
    #         #     right_button.set_button_color(color)
    #         #     left_button.set_button_color(color)
    #         #     rear_button.set_button_color(color)
    #         #     time.sleep(1)
    #
    #     except:
    #         print("Throwing shit from loop.")
    #         t, v, tb = sys.exc_info()
    #         logging.error("An error was encountered of type: {}".format(t))
    #         logging.error("Value: {}".format(v))
    #         logging.error(str(tb))
    #         raise