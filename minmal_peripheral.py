from bluezero import peripheral

def main():
    periph = peripheral.Peripheral(adapter_addr='xx:xx:xx:xx:xx:xx',
                                   local_name='TestPeripheral')
    periph.publish()

if __name__ == '__main__':
    main()
