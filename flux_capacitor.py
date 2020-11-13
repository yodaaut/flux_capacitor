#!/usr/bin/env -S python3 -u
import pigpio as GPIO
import sys, signal
import time
import subprocess
import json

# NOTE
# get current Home_P and HomePv_P and calculate PWM-Output-Signal
# consider that PWM will be added to Home_P in the next round
# plenticore.X.devices.local.Home_P - the current total home power used
# plenticore.X.devices.local.HomePv_P - the current home power directly provided by the plant
# Formula:
# if(ABS(Home_P - current_PWM) < HomePV_P:
#    new_PWM = HomePV_P - ABS(Home_P - current_PWM)
# else:
#    new_PWM = 0
#
# basic example
# Sun - abs(PWM - House) =          = expected PWM
# 100 - abs( 0  -    10) = 100 - 10 = 90
# 100 - abs(90  -   100) = 100 - 10 = 90
# 100 - abs(90  -   110) = 100 - 20 = 80


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

# NOTE
# plenticore.X.devices.local.Home_P - the current total home power used
# plenticore.X.devices.local.HomePv_P - the current home power directly provided by the plant
# plenticore.X.devices.local.HomeGrid_P - the current home power provided by the grid
# plenticore.X.devices.local.ToGrid_P - the current power sent to the grid. This value is calculated by the adapter and may not be 100% acurate.
def get_power_value(power_item):
    val = float(subprocess.run(["iobroker", "state", "getvalue", "plenticore." + str(plenticore_instance) + ".devices.local." + str(power_item)],
            stdout=subprocess.PIPE).stdout)
    if debug:
        print("{}W {}".format(val, power_item))
    return val

def get_pollinterval():
    data = json.loads(subprocess.run(["iobroker", "object", "get", "system.adapter.plenticore." + str(plenticore_instance)],
            stdout=subprocess.PIPE).stdout)
    poll = data['native']['pollinterval']
    if debug:
        print("Pollinterval: ", poll)

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

def calc_duty(duty):

    if debug:
        print("{}W Delta of HomePv_P - Home_P".format(round(duty,3)))
    # expected value between 0-kostal_max_value
    # needed value in %
    return float(round((duty/kostal_max_value*100), 3))


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
    my_duty=0
    while True:
        if my_gpios.read(gpio_input):
            my_gpios.write(gpio_output, 1)
            if debug:
                print("\nManual mode")
            change_dutycycle(gpio_pwm, gpio_frequency, 100)
        else:
            if debug:
                print("\nAuto mode")
            homepv_p=get_power_value("HomePv_P") # expected value between 0.000 and kostal_max_value
            home_p=get_power_value("Home_P")     # expected value between 0.000 and ∞ (plus duty if enabled)
            if (abs(home_p - my_duty) < (homepv_p - kostal_start_value)):
                my_gpios.write(gpio_output, 1)
                # TODO
                # decide how to use kostal_start_value
                # if kostal_start_value is subtracted, PWM-Output-Signal will be between 0% and 100%
                my_duty= (homepv_p - kostal_start_value) - abs(home_p - my_duty)
                # if kostal_start_value is not subtracted, PWM-Output-Signal will be between 11.11112 and 100%
                #my_duty= homepv_p - abs(home_p - my_duty)
            else:
                my_duty=0
                my_gpios.write(gpio_output, 0)
            change_dutycycle(gpio_pwm, gpio_frequency, calc_duty(my_duty))

        time.sleep(pollinterval/1000)
