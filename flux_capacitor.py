#!/usr/bin/env -S python3 -u
import pigpio as GPIO
import sys, signal
import time
import subprocess
import json



def set_config():
    ##INFO
    # BCM    <=> BOARD 'usage'
    # gpio18 <=> pin12 'pwm_output'
    # gpio24 <=> pin18 'HIGH/low output'
    # gpio25 <=> pin22 'button/relay input'
    # program uses BCM mode
    globals()['gpio_pwm']               = 18
    globals()['gpio_output']            = 24
    globals()['gpio_input']             = 25

    globals()['gpio_frequency']         = 1000
    globals()['kostal_start_value']     = 500
    globals()['kostal_max_value']       = 4500
    globals()['plenticore_instance']    = 0
    globals()['debug']                  = False

    globals()['pollinterval']           = get_pollinterval()

def signal_handler(signal, frame):
    # Cleanup
    my_gpios.set_mode(gpio_input, GPIO.CLEAR)
    my_gpios.set_mode(gpio_pwm, GPIO.CLEAR)
    my_gpios.set_mode(gpio_output, GPIO.CLEAR)
    my_gpios.stop() #close connection to pigpiod
    print("\nprogram exited gracefully")
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
    
def change_dutycycle(pin,freq,duty):

    if debug:
        print("{}% PWM-Signal".format(duty))
    # expected value for duty between 0.000-100.000% float
    # needed value  for hardware_PWM between 0-1000000 (1M) integer
    duty_hard_pwm=int(duty*10000)
    if debug:
        print("{} duty_hard_pwm-Signal".format(duty_hard_pwm))
    my_gpios.hardware_PWM(pin, freq, duty_hard_pwm)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    set_config()
    my_gpios = GPIO.pi()
# NOTE
## set_PWM_range(gpio, range)
## range in 100%?
## possible values for range are: 25-40000

## PWMduty: 0-1000000 (1M)
## PWMfreq: 1-125M
## Example
#
#  pi.hardware_PWM(18, 1000, 250000) # 1000Hz 25% dutycycle
# ALT5 is pwm mode
    my_gpios.set_mode(gpio_pwm, GPIO.ALT5)
    my_gpios.set_mode(gpio_output, GPIO.OUTPUT)
    my_gpios.set_mode(gpio_input, GPIO.INPUT)
    my_gpios.set_pull_up_down(gpio_input, GPIO.PUD_DOWN)
    my_gpios.hardware_PWM(gpio_pwm, gpio_frequency, 0)
    while True:
        if my_gpios.read(gpio_input):
            my_gpios.write(gpio_output, 1)
            if debug:
                print("Manual mode")
            change_dutycycle(gpio_pwm, gpio_frequency, 100)
        else:
            if debug:
                print("Pollinterval: ", pollinterval)
            togrid_p=get_togrid_p()
            if togrid_p != 0:
                my_gpios.write(gpio_output, 1)
                my_duty= float(round((togrid_p/kostal_max_value*100), 3))
                change_dutycycle(gpio_pwm, gpio_frequency, my_duty)
            else:
                my_gpios.write(gpio_output, 0)
                change_dutycycle(gpio_pwm, gpio_frequency, 0)

        time.sleep(pollinterval/1000)
