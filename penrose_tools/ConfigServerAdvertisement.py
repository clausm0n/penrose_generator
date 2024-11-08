# penrose_tools/ConfigServerAdvertisement.py

from bluezero import advertisement

class ConfigServerAdvertisement(advertisement.Advertisement):
    def __init__(self, index, service_uuids, local_name):
        super().__init__(index, 'peripheral')  # 'peripheral' is a common advertisement type
        self.service_uuids = service_uuids
        self.local_name = local_name
        self.include_tx_power = True  # Optional: Include TX power in advertisement
