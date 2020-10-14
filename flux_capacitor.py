#!/usr/bin/env -S python3 -u
import RPi.GPIO as GPIO
import sys, signal
import time
import subprocess
import json



def set_config():
    ##INFO
    # BCM    <=> BOARD 'usage'
    # gpio17 <=> pin11 'pwm_output'
    # gpio24 <=> pin18 'HIGH/low output'
    # gpio25 <=> pin22 'button/relais input'
    # program uses BOARD mode
    GPIO.setmode(GPIO.BOARD)
    globals()['gpio_pwm']               = 11
    globals()['gpio_output']            = 18
    globals()['gpio_input']             = 22

    globals()['gpio_frequency']         = 1000
    globals()['kostal_start_value']     = 500
    globals()['kostal_max_value']       = 4500
    globals()['plenticore_instance']    = 0
    globals()['debug']                  = True

    globals()['pollinterval']           = get_pollinterval()

def signal_handler(signal, frame):
    my_pwm.stop()
    GPIO.cleanup()
    print("\nprogram exiting gracefully")
    sys.exit(0)

def get_togrid_p():
    val = float(subprocess.run(["iobroker", "state", "getvalue", "plenticore." + str(plenticore_instance) + ".devices.local.ToGrid_P"],
            stdout=subprocess.PIPE).stdout)
    if debug:
        print("{}W ToGrid_P".format(val))
    return 0 if val < kostal_start_value else val

def get_pollinterval():
    data = json.loads(subprocess.run(["iobroker", "object", "get", "system.adapter.plenticore." + str(plenticore_instance)],
            stdout=subprocess.PIPE).stdout)
    poll = data['native']['pollinterval']

    return int(poll)
    
def main(w):

    if debug:
        print("{}% PWM-Signal".format(w))
    my_pwm.ChangeDutyCycle(w)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    set_config()
    GPIO.setup([gpio_pwm,gpio_output],GPIO.OUT)
    GPIO.setup(gpio_input,GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    my_pwm=GPIO.PWM(gpio_pwm,gpio_frequency)
    my_pwm.start(0)
    while True:
        if GPIO.input(gpio_input):
            GPIO.output(gpio_output, 1)
            if debug:
                print("Manual mode")
            main(100)
        else:
            if debug:
                print("Pollinterval: ", pollinterval)
            GPIO.output(gpio_output, 0)
            togrid_p=get_togrid_p()
            main(float(round((togrid_p/kostal_max_value*100), 3)))

        time.sleep(pollinterval/1000)
